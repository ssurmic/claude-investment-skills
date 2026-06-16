#!/usr/bin/env python3
"""
form4_firehose.py — Real-time SEC Form 4 aggregator with Telegram alerts.

v2.1 (2026-05): adds Tier-2 enrichment — every alert is augmented with
company one-liner, P/E + market cap + net cash, 52W price context, and a
0-10 Smart Money Score. Enrichment is optional + non-fatal: if yfinance
fails or the user disabled enrichment, alerts fall back to the v2.0 basic
format. Toggle via:
    python scripts/firehose_cli.py --enrich-on  | --enrich-off
or env var:  ENRICH=0  (off)  /  ENRICH=1  (on)

Pulls the SEC EDGAR Form 4 "current filings" atom feed every cron tick,
parses each new filing's XML, filters for OPEN-MARKET PURCHASES (code "P")
above a configurable USD threshold, and pushes a Telegram alert for each
qualifying buy.

Why this matters:
  - SEC EDGAR is the authoritative source for Form 4 (insider transactions).
    Filings appear in EDGAR 2-5 minutes after submission. openinsider.com
    re-scrapes EDGAR but with a 12-24 hour lag. This script gives us the
    SAME data with much lower latency.
  - We filter to transactionCode = "P" (open-market purchase) only. Codes
    A/M/F/G/D/C are compensation flows (RSU vest, option exercise, tax
    withholding, gift, distribution, conversion) — they look like "buys"
    in some aggregators but reveal NOTHING about insider conviction.
  - Threshold (default $200k) cuts noise: small ESPP-style buys, director
    qualifying purchases, etc.

State management:
  We keep a JSON file of seen accession numbers so cron re-runs don't
  re-alert on filings we already processed. The state file is committed
  back to the repo by GitHub Actions, capped at 5000 entries.

Env vars:
  TELEGRAM_BOT_TOKEN    Bot token (skip Telegram send if missing → stderr only)
  TELEGRAM_CHAT_ID      Target chat
  FORM4_MIN_VALUE       Min USD value to trigger alert (default 200000)
  FORM4_INCLUDE_SELLS   "1" to also alert on sells of equal magnitude (default off)
  EDGAR_USER_AGENT      Required by SEC: "<email> <product>/<version>"
                        Default: "ssurmiczizhao@gmail.com form4-firehose/1.0"
  TEST_MODE             "1" prints alerts to stdout instead of sending Telegram
  ENRICH                "0"/"off" disables v2.1 enrichment (Tier-2 valuation +
                        score). "1"/"on" forces enable. Unset = use config file.
"""

from __future__ import annotations
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

# v2.1: enrichment is optional + non-fatal. Import lazily-safe.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from enrichment import enrich, is_enabled as enrichment_enabled
    from enrichment.format import render_enriched
    _ENRICH_AVAILABLE = True
except Exception as _imp_err:
    _ENRICH_AVAILABLE = False
    print(f"[INFO] enrichment package not available: {_imp_err}", file=sys.stderr)

# v2.3: composite-signal cross-firehose detection (non-fatal)
# v2.3: 跨 firehose 复合信号 (非致命)
_COMPOSITE_AVAILABLE = False
try:
    # composite.py lives in strategic-partner-firehose; add its scripts to path
    _strategic_scripts = (
        Path(__file__).resolve().parent.parent.parent /
        "strategic-partner-firehose" / "scripts"
    )
    if _strategic_scripts.exists():
        sys.path.insert(0, str(_strategic_scripts))
        from composite import (  # type: ignore
            log_alert as _comp_log_alert,
            check_composite as _comp_check,
            is_composite_already_sent as _comp_sent,
            mark_composite_sent as _comp_mark,
            format_composite_alert as _comp_format,
        )
        _COMPOSITE_AVAILABLE = True
except Exception as _ce:
    print(f"[INFO] composite-signal unavailable: {_ce}", file=sys.stderr)

# ─── Constants ────────────────────────────────────────────────────────────
EDGAR_RSS_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=4&output=atom&count=100"
)
USER_AGENT = os.environ.get(
    "EDGAR_USER_AGENT", "ssurmiczizhao@gmail.com form4-firehose/1.0"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept": "*/*"}

# Form 4 transaction codes
CODE_PURCHASE = "P"  # Open market or private purchase — TRUE insider buy
CODE_SALE = "S"      # Open market or private sale — TRUE insider sell
# A=Grant/Award, M=Option exercise, F=Tax withholding, G=Gift, D=Distribution,
# C=Conversion → all compensation flows, NOT insider conviction signals.

MIN_VALUE_USD = int(os.environ.get("FORM4_MIN_VALUE", "200000"))
INCLUDE_SELLS = os.environ.get("FORM4_INCLUDE_SELLS", "") == "1"
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"

STATE_FILE = Path(__file__).parent / "form4_state.json"
VIP_FILE   = Path(__file__).parent / "vip_watchlist.json"

# Polite throttle: SEC asks for ≤10 req/sec
HTTP_DELAY = 0.15  # seconds between requests

# ─── VIP watchlist ────────────────────────────────────────────────────────

# ── Centralized Telegram fan-out (DM + Channel) ───────────────────────
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__)))))
import _tg
# ──────────────────────────────────────────────────────────────────────

def load_vip_watchlist() -> list[dict]:
    """Load VIP persons who bypass normal threshold + sell filter.

    Format: [{"name_contains": "Andreessen", "tickers": ["META"], "include_sells": true}]
    tickers=null means any ticker triggers an alert.
    """
    if not VIP_FILE.exists():
        return []
    try:
        return json.loads(VIP_FILE.read_text()).get("persons", [])
    except Exception:
        return []


def vip_match(filing: dict, vip_list: list[dict]) -> dict | None:
    """Return the matching VIP entry, or None if no match."""
    owner = (filing.get("owner") or "").lower()
    ticker = (filing.get("ticker") or "").upper()
    for entry in vip_list:
        if entry.get("name_contains", "").lower() not in owner:
            continue
        tickers = entry.get("tickers")
        if tickers is None or ticker in [t.upper() for t in tickers]:
            return entry
    return None


_VIP_LIST = load_vip_watchlist()

# ─── State helpers ────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"seen_accessions": [], "last_run_iso": None}


def save_state(state: dict) -> None:
    # Cap seen list at 5000 (a few days at typical Form 4 volume)
    accs = state.get("seen_accessions", [])
    if len(accs) > 5000:
        state["seen_accessions"] = accs[-5000:]
    state["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


# ─── EDGAR fetch & parse ──────────────────────────────────────────────────
def fetch_rss() -> str:
    """Pull the EDGAR atom feed listing the most recent Form 4 filings."""
    r = requests.get(EDGAR_RSS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_rss(xml_text: str) -> list:
    """Return list of {accession, link, title, updated} dicts."""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    out = []
    for entry in root.findall("a:entry", ns):
        title_el = entry.find("a:title", ns)
        link_el = entry.find("a:link", ns)
        id_el = entry.find("a:id", ns)
        updated_el = entry.find("a:updated", ns)
        if any(el is None for el in (title_el, link_el, id_el)):
            continue
        # id format: urn:tag:sec.gov,2008:accession-number=0001209191-26-...
        accession = id_el.text.split("=")[-1] if id_el.text else None
        if not accession:
            continue
        out.append({
            "accession": accession,
            "link": link_el.get("href"),
            "title": title_el.text or "",
            "updated": updated_el.text if updated_el is not None else "",
        })
    return out


def find_form4_xml_url(filing_index_url: str) -> str | None:
    """Given a filing's index page URL, find the RAW Form 4 XML.

    Each Form 4 filing on EDGAR ships TWO .xml URLs:
      - .../xslF345X06/ownership.xml  ← XSL-rendered HTML (looks like XML but isn't)
      - .../ownership.xml             ← the actual raw Form 4 XML we want

    We must pick the path WITHOUT "xsl" in it.
    """
    r = requests.get(filing_index_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    candidates = re.findall(r'href="([^"]+\.xml)"', r.text)
    if not candidates:
        return None
    # Exclude XSL-rendered HTML view (path contains "xsl" segment)
    raw = [c for c in candidates if "/xsl" not in c.lower()
           and "primary_doc" not in c.lower()
           and "index" not in c.lower()]
    if not raw:
        return None
    pick = raw[0]
    if not pick.startswith("http"):
        pick = "https://www.sec.gov" + pick
    return pick


def _text(el) -> str:
    return el.text.strip() if el is not None and el.text else ""


def parse_form4(xml_text: str) -> dict:
    """Extract issuer, owner, role, and qualifying transactions from a Form 4."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}

    ticker = _text(root.find(".//issuerTradingSymbol"))
    company = _text(root.find(".//issuerName"))
    owner = _text(root.find(".//reportingOwner/reportingOwnerId/rptOwnerName"))

    rel = root.find(".//reportingOwner/reportingOwnerRelationship")
    role_parts = []
    title_txt = ""
    if rel is not None:
        if _text(rel.find("isDirector")) == "1":
            role_parts.append("Dir")
        if _text(rel.find("isOfficer")) == "1":
            title_txt = _text(rel.find("officerTitle"))
            role_parts.append(f"Officer/{title_txt}" if title_txt else "Officer")
        if _text(rel.find("isTenPercentOwner")) == "1":
            role_parts.append("10%")

    transactions = []
    for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(txn.find(".//transactionCoding/transactionCode"))
        if code not in (CODE_PURCHASE, CODE_SALE):
            continue
        try:
            shares = float(_text(txn.find(".//transactionAmounts/transactionShares/value")))
            price = float(_text(txn.find(".//transactionAmounts/transactionPricePerShare/value")) or 0)
        except (ValueError, TypeError):
            continue
        ad = _text(txn.find(".//transactionAmounts/transactionAcquiredDisposedCode/value"))
        date = _text(txn.find(".//transactionDate/value"))
        transactions.append({
            "code": code,
            "ad": ad,  # A=acquired, D=disposed
            "shares": shares,
            "price": price,
            "value": shares * price,
            "date": date,
        })

    return {
        "ticker": ticker.upper() if ticker else "",
        "company": company,
        "owner": owner,
        "role": ", ".join(role_parts) if role_parts else "Unknown",
        "title": title_txt,
        "transactions": transactions,
        "is_10pct_only": role_parts == ["10%"],
    }


# ─── Alert formatting ─────────────────────────────────────────────────────
def role_emoji(role: str, title: str) -> str:
    """Pick an emoji + weight based on role seniority."""
    t = (title or "").lower()
    if "ceo" in t or "chairman" in t or "chief executive" in t:
        return "👑"  # CEO/Chairman — strongest signal
    if "cfo" in t or "chief financial" in t:
        return "💼"  # CFO — strong signal
    if "president" in t or "coo" in t or "chief operating" in t:
        return "🏛"
    if "Officer" in role:
        return "🧑‍💼"
    if "Dir" in role:
        return "🪑"  # Director
    if "10%" in role:
        return "🐳"  # 10% holder
    return "❓"


def format_alert(filing: dict, side: str = "BUY") -> str | None:
    """Build a Markdown alert message. Returns None if no qualifying txn."""
    txns = filing["transactions"]
    target_code = CODE_PURCHASE if side == "BUY" else CODE_SALE
    relevant = [t for t in txns if t["code"] == target_code]
    if not relevant:
        return None

    total_value = sum(t["value"] for t in relevant)
    total_shares = sum(t["shares"] for t in relevant)
    avg_price = total_value / total_shares if total_shares > 0 else 0

    icon = "🚨🟢" if side == "BUY" else "🚨🔴"
    label = "INSIDER BUY" if side == "BUY" else "INSIDER SELL"
    role_icon = role_emoji(filing["role"], filing["title"])

    ticker = filing["ticker"] or "?"
    company = filing["company"] or "Unknown Issuer"
    owner = filing["owner"] or "Unknown"
    role = filing["role"] or "Unknown"

    sec_url = (
        f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        f"&CIK={ticker}&type=4&dateb=&owner=include&count=10"
    )

    lines = [
        f"{icon} *{label}* — ${total_value:,.0f}",
        "",
        f"*Ticker*: `{ticker}`  ({company})",
        f"{role_icon} *{owner}*",
        f"_{role}_",
        "",
        f"*{total_shares:,.0f} shares @ ${avg_price:,.2f}*",
    ]
    if len(relevant) > 1:
        lines.append(f"({len(relevant)} transactions same filing)")
    lines.extend([
        "",
        f"[SEC EDGAR ›]({sec_url})",
    ])
    return "\n".join(lines)


# ─── Verdict suppression ──────────────────────────────────────────────────
# Verdict tags to drop entirely: do NOT push to Telegram. The accession is
# still recorded as seen (added to new_accessions before the send), so a
# suppressed filing will not re-alert on the next cron run.
#   AVOID = ≥3 risk flags / deep-cold sector / chasing-top (story stock).
# The user does not want these pushed; everything else keeps the full
# (wordy) enriched format unchanged.
SUPPRESS_VERDICTS = {"AVOID"}


def _verdict_tag(enriched) -> str:
    """Safely pull the enrichment verdict tag (BUY/WATCH/AVOID/SKIP), or ''."""
    try:
        return ((enriched or {}).get("verdict") or {}).get("tag", "") or ""
    except Exception:
        return ""


# ─── Telegram ─────────────────────────────────────────────────────────────
def send_telegram(msg, *args, **kwargs) -> bool:
    """Delegates to _tg.send so every alert fans out to BOTH the
    @DuckyduckyTradeBot DM (TELEGRAM_CHAT_ID) and the duckyduckyChannel
    (TELEGRAM_CHAT_ID_CHANNEL).  Same bot, two routes."""
    tm = globals().get("TEST_MODE", False)
    if isinstance(tm, str):
        tm = tm == "1"
    return _tg.send(msg, test_mode=bool(tm))


def main() -> int:
    state = load_state()
    seen = set(state.get("seen_accessions", []))

    enrich_status = (
        "ON" if (_ENRICH_AVAILABLE and enrichment_enabled())
        else ("DISABLED" if _ENRICH_AVAILABLE else "UNAVAILABLE")
    )
    print(f"[INFO] Pulling EDGAR Form 4 feed... "
          f"(min_value=${MIN_VALUE_USD:,}, enrich={enrich_status})",
          file=sys.stderr)
    try:
        rss = fetch_rss()
    except Exception as e:
        print(f"[FATAL] EDGAR fetch failed: {e}", file=sys.stderr)
        return 1

    filings = parse_rss(rss)
    print(f"[INFO] Feed has {len(filings)} filings", file=sys.stderr)

    new_accessions = []
    alerts_sent = 0
    processed = 0
    skipped_below_threshold = 0
    skipped_10pct_only = 0

    for f in filings:
        acc = f["accession"]
        if acc in seen:
            continue
        new_accessions.append(acc)
        processed += 1

        try:
            time.sleep(HTTP_DELAY)
            xml_url = find_form4_xml_url(f["link"])
            if not xml_url:
                continue
            time.sleep(HTTP_DELAY)
            r = requests.get(xml_url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            filing = parse_form4(r.text)
        except Exception as e:
            print(f"[WARN] Failed parse {acc}: {e}", file=sys.stderr)
            continue

        if not filing or not filing["ticker"]:
            continue

        # Process BUYS
        vip = vip_match(filing, _VIP_LIST)
        purchases = [t for t in filing["transactions"] if t["code"] == CODE_PURCHASE]
        if purchases:
            total = sum(t["value"] for t in purchases)
            if total < MIN_VALUE_USD and not vip:
                skipped_below_threshold += 1
            elif filing["is_10pct_only"] and not vip:
                # Pure 10% holder buys (e.g. Saba Capital activist position) —
                # different signal than officer/director conviction. Skip by
                # default; revisit in v2.1 if user wants these too.
                skipped_10pct_only += 1
                print(f"[SKIP-10%]  {filing['ticker']:6s}  ${total:>12,.0f}  "
                      f"{filing['owner']}", file=sys.stderr)
            else:
                msg = format_alert(filing, side="BUY")
                enriched = None
                # v2.1: append enrichment (P/E, score, etc.) if available + enabled
                if msg and _ENRICH_AVAILABLE and enrichment_enabled():
                    try:
                        enriched = enrich(filing["ticker"], filing, total)
                        if enriched:
                            msg = render_enriched(msg, enriched)
                    except Exception as ee:
                        # Never let enrichment kill the alert
                        print(f"[ENRICH-FAIL] {filing['ticker']}: {ee}",
                              file=sys.stderr)
                # v2.4: drop AVOID verdicts (story-stock red flags) — don't push.
                _vtag = _verdict_tag(enriched)
                if msg and _vtag in SUPPRESS_VERDICTS:
                    print(f"[SUPPRESS-{_vtag}] {filing['ticker']:6s} "
                          f"${total:>12,.0f}  {filing['owner']}", file=sys.stderr)
                    msg = None
                if msg and send_telegram(msg):
                    alerts_sent += 1
                    print(f"[ALERT-BUY] {filing['ticker']:6s}  ${total:>12,.0f}  "
                          f"{filing['owner']} ({filing['role']})", file=sys.stderr)

                    # v2.3: composite signal check (non-fatal)
                    # 复合信号检测 (非致命)
                    if _COMPOSITE_AVAILABLE:
                        try:
                            _comp_log_alert(
                                firehose_type="insider",
                                ticker=filing["ticker"],
                                amount_usd=total,
                                extra={
                                    "role": filing.get("role", ""),
                                    "owner": filing.get("owner", ""),
                                    "title": filing.get("title", ""),
                                },
                            )
                            if not _comp_sent(filing["ticker"]):
                                composite = _comp_check(
                                    filing["ticker"], own_type="insider"
                                )
                                if composite:
                                    own_sum = (
                                        f"{filing.get('owner', 'Insider')} "
                                        f"(${total:,.0f}, {filing.get('role', '')})"
                                    )
                                    mega = _comp_format(
                                        ticker=filing["ticker"],
                                        company_name=filing.get("company", ""),
                                        composite_info=composite,
                                        own_alert_summary=own_sum,
                                    )
                                    if send_telegram(mega):
                                        _comp_mark(filing["ticker"])
                                        print(
                                            f"[MEGA] {filing['ticker']:6s}  "
                                            f"insider+partner cross-fire",
                                            file=sys.stderr,
                                        )
                        except Exception as ce:
                            print(f"[COMPOSITE-WARN] {filing['ticker']}: {ce}",
                                  file=sys.stderr)

        # Optionally process SELLS (off by default; VIP always included)
        if INCLUDE_SELLS or vip:
            sells = [t for t in filing["transactions"] if t["code"] == CODE_SALE]
            vip_sells = vip and vip.get("include_sells", True)
            if sells and (not filing["is_10pct_only"] or vip):
                total = sum(t["value"] for t in sells)
                sell_threshold = MIN_VALUE_USD * 5
                if total >= sell_threshold or vip_sells:
                    msg = format_alert(filing, side="SELL")
                    enriched = None
                    if msg and _ENRICH_AVAILABLE and enrichment_enabled():
                        try:
                            enriched = enrich(filing["ticker"], filing, total)
                            if enriched:
                                msg = render_enriched(msg, enriched)
                        except Exception as ee:
                            print(f"[ENRICH-FAIL] {filing['ticker']}: {ee}",
                                  file=sys.stderr)
                    # v2.4: drop AVOID verdicts — don't push.
                    _vtag = _verdict_tag(enriched)
                    if msg and _vtag in SUPPRESS_VERDICTS:
                        print(f"[SUPPRESS-{_vtag}] {filing['ticker']:6s} "
                              f"${total:>12,.0f}  (SELL)", file=sys.stderr)
                        msg = None
                    if msg and send_telegram(msg):
                        alerts_sent += 1
                        print(f"[ALERT-SELL] {filing['ticker']:6s}  ${total:>12,.0f}",
                              file=sys.stderr)

    # Persist state
    state["seen_accessions"] = list(seen) + new_accessions
    save_state(state)

    print(
        f"[DONE] processed={processed} alerts={alerts_sent} "
        f"below_threshold={skipped_below_threshold} "
        f"skipped_10pct={skipped_10pct_only}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
