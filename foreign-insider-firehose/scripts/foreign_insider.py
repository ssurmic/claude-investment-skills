#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
foreign_insider.py — Insider buys for FOREIGN issuers (the EU/non-US gap).

外国发行人内部人买入扫描 —— 填补 Form 4 看不到的欧洲/外国空白.

═══════════════════════════════════════════════════════════════════════
  WHY THIS EXISTS / 为什么要这个
═══════════════════════════════════════════════════════════════════════

openinsider / SEC Form 4 / insider_ratio.py are US-ONLY. Foreign private
issuers (Nokia, ASML, SAP, Ericsson, TSMC, Tower...) are EXEMPT from Section
16 / Form 4, so US insider tools NEVER see them. Their managerial trades are
disclosed under EU MAR Article 19 ("Managers' Transactions" / PDMR), UK
Directors' Dealings, etc. — and US-listed ADRs FURNISH those notifications to
the SEC on Form 6-K.

This scanner watches each foreign-issuer's recent 6-Ks, detects the PDMR /
"Managers' transactions" ones, and classifies them with the SAME discipline we
use for US Form 4: a genuine OPEN-MARKET BUY is signal; a share AWARD (board
fee paid in stock, LTI/co-investment, RSU/vesting) is NOT. (e.g. it would have
caught Nokia's 2026-05-25 Owczarek ~$500K open-market buy, while excluding the
2026-05-04 board-fee share allocations.)

  BUY (signal)   = "acquisition / acquired / purchased / subscribed" AND
                   no award/plan keyword.
  AWARD (noise)  = annual fee / incentive / co-investment / remuneration /
                   matching / vesting / RSU / long-term incentive.
  SELL           = disposal / disposed / sold.

Lag: 6-K furnishing trails the trade 1-2 business days (and skips US holidays).
That's fine for an insider signal — same as Form 4 filings trailing the trade.

Watchlist: foreign_watchlist.json (public default = obvious foreign large-caps).
The PRIVATE repo can ship a fuller personal list + route to its own bot.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TEST_MODE, MIN_BUY_USD (default 0),
     WATCHLIST (path override), INCLUDE_SELLS ("1" to also alert disposals)
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "foreign_insider_state.json"
WATCHLIST_FILE = Path(os.environ.get("WATCHLIST", SCRIPT_DIR / "foreign_watchlist.json"))

HEADERS = {
    "User-Agent": os.environ.get(
        "EDGAR_USER_AGENT", "ssurmiczizhao@gmail.com foreign-insider-firehose/1.0"),
    "Accept": "*/*",
}
HTTP_DELAY = 0.18
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
INCLUDE_SELLS = os.environ.get("INCLUDE_SELLS", "") == "1"
MIN_BUY_USD = float(os.environ.get("MIN_BUY_USD", "25000"))  # micro-filter, like US

# How many recent 6-Ks per name to scan each run (incremental dedup handles repeats)
MAX_6K_PER_NAME = int(os.environ.get("MAX_6K_PER_NAME", "12"))

# ── Classification keyword sets ─────────────────────────────────────────
_PDMR_RX = re.compile(r"managerial responsibilit|managers.{0,3} transaction|"
                      r"directors.{0,3} dealings|persons closely associated", re.I)
# Award / plan = NOT a conviction open-market buy (the EU "code-P" exclusion).
_AWARD_RX = re.compile(
    r"annual fee|incentive plan|long[- ]term incentive|\bLTI\b|co[- ]investment|"
    r"remuneration|matching shares|reward shares|restricted share|\bRSU\b|"
    r"vesting|granted|share-based|equity plan|performance share", re.I)
_BUY_RX = re.compile(r"\bacquisition\b|\bacquired\b|\bpurchas|\bbought\b|\bsubscrib", re.I)
_SELL_RX = re.compile(r"\bdisposal\b|\bdisposed\b|\bsold\b|\bsale of\b", re.I)


# ── EDGAR helpers ───────────────────────────────────────────────────────
_CIK_MAP: dict[str, str] = {}


def resolve_cik(ticker: str) -> str:
    if not _CIK_MAP:
        try:
            r = requests.get("https://www.sec.gov/files/company_tickers.json",
                             headers=HEADERS, timeout=30)
            for row in r.json().values():
                _CIK_MAP[str(row["ticker"]).upper()] = str(row["cik_str"]).zfill(10)
        except Exception as e:
            print(f"[WARN] cik map load failed: {e}", file=sys.stderr)
    return _CIK_MAP.get(ticker.upper(), "")


def recent_6ks(cik: str) -> list[dict]:
    """Most-recent 6-K filings for a CIK (newest first)."""
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=HEADERS, timeout=30)
        rec = r.json()["filings"]["recent"]
        out = []
        for i in range(len(rec["form"])):
            if rec["form"][i] != "6-K":
                continue
            acc = rec["accessionNumber"][i]
            out.append({
                "accession": acc,
                "date": rec["filingDate"][i],
                "index_url": (f"https://www.sec.gov/Archives/edgar/data/"
                              f"{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm"),
            })
            if len(out) >= MAX_6K_PER_NAME:
                break
        return out
    except Exception as e:
        print(f"[WARN] submissions failed {cik}: {e}", file=sys.stderr)
        return []


def fetch_text(index_url: str) -> str:
    """Fetch cover + exhibits of a filing, stripped to text (PDMR table lives in ex99)."""
    try:
        r = requests.get(index_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception:
        return ""
    cands = re.findall(r'href="([^"]+\.(?:htm|html))"', r.text)
    cands = [re.sub(r"^/ix\?doc=", "", c) for c in cands]
    docs = [c for c in cands if "/archives/" in c.lower()
            and "index" not in c.lower() and "/xsl" not in c.lower()]
    combined = []
    for doc in docs[:4]:
        url = doc if doc.startswith("http") else "https://www.sec.gov" + doc
        try:
            time.sleep(HTTP_DELAY)
            dr = requests.get(url, headers=HEADERS, timeout=30)
            if dr.ok:
                t = re.sub(r"<[^>]+>", " ", dr.text)
                combined.append(re.sub(r"\s+", " ", html.unescape(t).replace("\xa0", " ")))
        except Exception:
            continue
    return "\n".join(combined)


# ── Parse + classify one PDMR filing ────────────────────────────────────

def classify(body: str) -> dict | None:
    if not _PDMR_RX.search(body):
        return None
    is_award = bool(_AWARD_RX.search(body))
    is_buy = bool(_BUY_RX.search(body))
    is_sell = bool(_SELL_RX.search(body))

    if is_award:
        verdict = "AWARD"          # board fee / LTI / RSU — NOT a conviction buy
    elif is_buy and not is_sell:
        verdict = "BUY"            # genuine open-market acquisition
    elif is_sell and not is_buy:
        verdict = "SELL"
    elif is_buy and is_sell:
        verdict = "MIXED"
    else:
        verdict = "UNVERIFIED"     # detected PDMR but couldn't read direction

    # person + position (best-effort)
    names = re.findall(r"Name\s*:?\s*([A-Z][A-Za-z .'\-]{3,35})", body)
    pos = re.search(r"(Chief [A-Za-z ]+Officer|President[A-Za-z ]*|"
                    r"[Ss]enior manager|Member of the Board|Chair[A-Za-z]*|"
                    r"Director|CEO|CFO)", body)
    # value (best-effort): "<vol> shares ... <price>" or MAR Volume/Price
    val = 0.0
    pv = re.search(r"([\d][\d,]{2,})\s*(?:Nokia |ordinary |common )?shares?.{0,80}?"
                   r"(?:price|@|at)\D{0,8}([\d]+(?:\.\d+)?)", body, re.I)
    if not pv:
        vol = re.search(r"Volume\D{0,8}([\d][\d,]{2,})", body, re.I)
        prc = re.search(r"(?:unit )?[Pp]rice\D{0,8}([\d]+(?:\.\d+)?)", body)
        if vol and prc:
            pv = (None,)  # signal we have separate
            try:
                val = float(vol.group(1).replace(",", "")) * float(prc.group(1))
            except Exception:
                val = 0.0
    else:
        try:
            val = float(pv.group(1).replace(",", "")) * float(pv.group(2))
        except Exception:
            val = 0.0

    return {
        "verdict": verdict,
        "names": list(dict.fromkeys(names))[:4],
        "position": pos.group(1) if pos else "",
        "value_usd": val,
        "is_award": is_award,
    }


def send_telegram(msg: str) -> bool:
    if TEST_MODE:
        print("─── TEST_MODE: would send ───\n" + msg + "\n─── end ───", file=sys.stderr)
        return True
    token = os.environ.get("TELEGRAM_BOT_TOKEN"); chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[WARN] no creds; not sent:\n{msg}", file=sys.stderr); return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat, "text": msg,
                      "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=20)
    if r.status_code == 200:
        return True
    r2 = requests.post(url, json={"chat_id": chat, "text": msg,
                       "disable_web_page_preview": True}, timeout=20)
    return r2.status_code == 200


def fmt(ticker: str, name: str, f: dict, link: str, date: str) -> str:
    who = ", ".join(f["names"]) or "(see filing)"
    val = f" · ~${f['value_usd']:,.0f}" if f["value_usd"] else ""
    head = {"BUY": "🟢🇪🇺 *FOREIGN INSIDER BUY*",
            "SELL": "🔴 *Foreign insider SELL*",
            "AWARD": "▫️ Foreign insider (AWARD — not a buy)",
            "MIXED": "🟡 Foreign insider (mixed)",
            "UNVERIFIED": "⚪ Foreign insider (direction unread — check filing)"}[f["verdict"]]
    return "\n".join([
        f"{head} — `{ticker}`",
        f"*{name}*",
        f"👤 {who}" + (f" · _{f['position']}_" if f["position"] else "") + val,
        f"📅 filed {date}",
        f"[SEC 6-K ›]({link})",
        "" if f["verdict"] != "AWARD" else "_(board fee / incentive plan — excluded from buy signal)_",
    ])


def fmt_agg(ticker: str, company: str, insider: str, tranches: list, total: float) -> str:
    """Aggregated per-insider buy alert (sums multi-day tranches → running total)."""
    n = len(tranches)
    latest = tranches[-1]
    lines = [
        f"🟢🇪🇺 *FOREIGN INSIDER BUY — {ticker}*" + (f" · {n} tranches" if n > 1 else ""),
        f"*{company}*",
        f"👤 {insider}" + (f" · _{latest['position']}_" if latest.get("position") else ""),
        f"💰 *running total ~${total:,.0f}* across {n} buy{'s' if n > 1 else ''}",
    ]
    if n > 1:
        for t in tranches:
            lines.append(f"   • {t['date']}: ~${t['value']:,.0f}")
    lines.append(f"📅 latest {latest['date']}")
    lines.append(f"[SEC 6-K ›]({latest['link']})")
    return "\n".join(lines)


def main() -> int:
    try:
        wl = json.loads(WATCHLIST_FILE.read_text())
    except Exception as e:
        print(f"[ERROR] watchlist load failed: {e}", file=sys.stderr); return 1
    names = wl.get("tickers", wl) if isinstance(wl, dict) else wl

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"seen": []}
    seen = set(state.get("seen", []))
    alerts = 0

    for entry in names:
        ticker = entry["ticker"] if isinstance(entry, dict) else entry
        company = entry.get("name", ticker) if isinstance(entry, dict) else ticker
        cik = (entry.get("cik") if isinstance(entry, dict) else "") or resolve_cik(ticker)
        if not cik:
            print(f"[WARN] no CIK for {ticker}", file=sys.stderr); continue
        cik = str(cik).zfill(10)
        # Fetch + classify all recent PDMR filings, then AGGREGATE buys per
        # insider (so multi-day tranches sum into one running-total alert —
        # this is why we previously undercounted Owczarek's 70k/$1.1M as 32k/$500k).
        buys_by_insider: dict = {}
        for f6 in recent_6ks(cik):
            time.sleep(HTTP_DELAY)
            res = classify(fetch_text(f6["index_url"]))
            if not res:
                continue
            v = res["verdict"]
            insider = res["names"][0] if res["names"] else "?"
            if v == "BUY":
                buys_by_insider.setdefault(insider, []).append({
                    "date": f6["date"], "acc": f6["accession"], "link": f6["index_url"],
                    "value": res["value_usd"], "position": res["position"]})
            elif (v == "SELL" and INCLUDE_SELLS) or v in ("MIXED", "UNVERIFIED"):
                if f6["accession"] not in seen:
                    if send_telegram(fmt(ticker, company, res, f6["index_url"], f6["date"])):
                        alerts += 1
                        time.sleep(0.5)
                seen.add(f6["accession"])
            else:
                seen.add(f6["accession"])  # AWARD / non-signal

        # Per-insider aggregation: alert (with running total) only if a tranche is NEW.
        for insider, tranches in buys_by_insider.items():
            tranches.sort(key=lambda x: x["date"])
            total = sum(t["value"] for t in tranches)
            has_new = any(t["acc"] not in seen for t in tranches)
            for t in tranches:
                seen.add(t["acc"])
            if not has_new:
                continue
            if total and total < MIN_BUY_USD:
                continue
            print(f"[ALERT-AGG] {ticker} {insider}: {len(tranches)} buys "
                  f"total ${total:,.0f}", file=sys.stderr)
            if send_telegram(fmt_agg(ticker, company, insider, tranches, total)):
                alerts += 1
                time.sleep(0.5)

    if not TEST_MODE:
        state["seen"] = sorted(seen)[-8000:]
        state["updated"] = datetime.now(timezone.utc).isoformat()
        STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    print(f"[DONE] alerts={alerts} seen={len(seen)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
