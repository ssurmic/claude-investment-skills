#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_partner.py — Prove the strategic-partner engine on REAL past deals.

用真实历史合作验证引擎: 拿已发生的 NVDA 战略投资, 从 EDGAR 拉当时的 8-K 原文,
(1) 验证引擎当时会不会触发 (find_strategic_investors + amount + deal type),
(2) 算从 8-K 出来那一刻进场到今天的收益 vs SPY.

两部分都得过关才算"有用":
  DETECTION = 引擎会 fire 吗?
  ALPHA     = fire 那一刻进场赚钱吗 (跑赢 SPY)?

Usage: uv run --with requests,yfinance,pandas python backtest_partner.py
"""
from __future__ import annotations

import sys
import json
import time
from datetime import datetime, timedelta

import requests

# Reuse the live engine — same code the firehose runs in production.
from investor_registry import find_strategic_investors
from parsers import (
    FilingMeta, extract_items, extract_max_amount_usd_m, detect_deal_type,
    is_noise_filing,
)
# Production fetch (primary + exhibits) + full analyze pipeline (incl. filters).
from partner_firehose import fetch_filing_text, analyze_filing

HEADERS = {"User-Agent": "ssurmiczizhao@gmail.com strategic-partner-backtest/1.0",
           "Accept": "*/*"}
HTTP_DELAY = 0.18

# Real, publicly-announced strategic deals to backtest.
# (ticker, expected_investor, announce_date, label)
DEALS = [
    ("COHR", "NVIDIA", "2026-03-02", "NVIDIA $2B strategic investment + multi-year supply"),
    ("LITE", "NVIDIA", "2026-03-02", "NVIDIA $2B strategic investment (optical/lasers)"),
    ("MRVL", "NVIDIA", "2026-03-31", "NVIDIA $2B investment + NVLink Fusion / silicon photonics"),
]


def cik_for(ticker: str) -> str | None:
    """Resolve ticker -> zero-padded 10-digit CIK via SEC's official map."""
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=HEADERS, timeout=30)
        r.raise_for_status()
        for row in r.json().values():
            if row.get("ticker", "").upper() == ticker.upper():
                return str(row["cik_str"]).zfill(10)
    except Exception as e:
        print(f"[WARN] cik lookup failed {ticker}: {e}", file=sys.stderr)
    return None


def find_8k_near(cik: str, target_date: str) -> dict | None:
    """
    Find the 8-K filed on/closest-after target_date from the submissions feed.
    Returns {accession, filingDate, acceptanceDateTime, primaryDoc, index_url}.
    """
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=HEADERS, timeout=30)
        r.raise_for_status()
        recent = r.json()["filings"]["recent"]
        tgt = datetime.strptime(target_date, "%Y-%m-%d").date()
        best = None
        for i, form in enumerate(recent["form"]):
            if form != "8-K":
                continue
            fdate = datetime.strptime(recent["filingDate"][i], "%Y-%m-%d").date()
            # accept filings within [target-1, target+4] business window
            if not (tgt - timedelta(days=2) <= fdate <= tgt + timedelta(days=6)):
                continue
            acc = recent["accessionNumber"][i].replace("-", "")
            cand = {
                "accession": recent["accessionNumber"][i],
                "filingDate": recent["filingDate"][i],
                "acceptance": recent.get("acceptanceDateTime", [None]*len(recent["form"]))[i],
                "primaryDoc": recent["primaryDocument"][i],
                # Filing INDEX page (same as the atom feed's link) — its doc
                # hrefs are absolute paths, so fetch_filing_text() correctly
                # pulls primary + exhibits (the $ amount lives in 99.1).
                "index_url": (f"https://www.sec.gov/Archives/edgar/data/"
                              f"{int(cik)}/{acc}/{recent['accessionNumber'][i]}-index.htm"),
                "_delta": abs((fdate - tgt).days),
            }
            if best is None or cand["_delta"] < best["_delta"]:
                best = cand
        return best
    except Exception as e:
        print(f"[WARN] 8-K lookup failed {cik}: {e}", file=sys.stderr)
    return None


def fetch_text(url: str) -> str:
    try:
        time.sleep(HTTP_DELAY)
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        import re
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
    except Exception as e:
        print(f"[WARN] text fetch failed: {e}", file=sys.stderr)
        return ""


def returns_from(ticker: str, start_date: str) -> dict:
    """Forward returns from first close on/after start_date, vs SPY."""
    import yfinance as yf
    out = {}
    try:
        end = (datetime.now().date() + timedelta(days=1)).isoformat()
        h = yf.Ticker(ticker).history(start=start_date, end=end)
        spy = yf.Ticker("SPY").history(start=start_date, end=end)
        if h is None or len(h) < 2:
            return out
        entry = float(h["Close"].iloc[0])
        entry_date = h.index[0].date().isoformat()
        spy_entry = float(spy["Close"].iloc[0])
        out["entry"] = entry
        out["entry_date"] = entry_date
        for label, td in [("1d", 1), ("1w", 5), ("1mo", 21)]:
            if len(h) > td:
                out[label] = (float(h["Close"].iloc[td]) - entry) / entry * 100
        out["now"] = (float(h["Close"].iloc[-1]) - entry) / entry * 100
        out["now_px"] = float(h["Close"].iloc[-1])
        out["spy_now"] = (float(spy["Close"].iloc[-1]) - spy_entry) / spy_entry * 100
        out["excess"] = out["now"] - out["spy_now"]
    except Exception as e:
        print(f"[WARN] returns failed {ticker}: {e}", file=sys.stderr)
    return out


def main() -> int:
    print("=" * 78)
    print("STRATEGIC-PARTNER FIREHOSE — BACKTEST ON REAL DEALS")
    print(f"as of {datetime.now().date()}")
    print("=" * 78)

    detect_pass = 0
    alpha_pass = 0
    rows = []

    for ticker, inv, adate, label in DEALS:
        print(f"\n### {ticker} — {label}  (announced {adate})")
        cik = cik_for(ticker)
        if not cik:
            print("  ✗ could not resolve CIK")
            continue
        filing = find_8k_near(cik, adate)
        if not filing:
            print("  ✗ no 8-K found near announce date")
            continue
        print(f"  8-K filed {filing['filingDate']} (accepted {filing['acceptance']})")
        print(f"  {filing['index_url']}")

        # ── DETECTION: run the EXACT production pipeline on the real filing ──
        # fetch_filing_text pulls primary + exhibits (where the $ amount lives);
        # analyze_filing runs investor-scan + item check + mcap/amount filters.
        body = fetch_filing_text(filing["index_url"])
        meta = FilingMeta(
            accession=filing["accession"], form_type="8-K",
            link=filing["index_url"], title=f"8-K - {ticker}",
            updated=filing["filingDate"], cik=cik, company_name=ticker)
        signal = analyze_filing(meta, body)
        would_fire = signal is not None
        if signal:
            inv_names = [c for _, c in signal.investors]
            print(f"  DETECTION: investors={inv_names or '—'} | items={signal.items or '—'} | "
                  f"amount=${signal.amount_usd_m:,.0f}M | type={signal.deal_type}")
        else:
            # Show why it didn't fire (raw extraction) for transparency.
            print(f"  DETECTION: investors={[c for _,c in find_strategic_investors(body)] or '—'} | "
                  f"items={extract_items(body) or '—'} | "
                  f"amount=${extract_max_amount_usd_m(body):,.0f}M | "
                  f"noise={is_noise_filing(body)}")
        print(f"  → WOULD FIRE (full prod filters): {'✅ YES' if would_fire else '❌ NO'}")
        if would_fire:
            detect_pass += 1

        # ── ALPHA: forward return from filing date vs SPY ──
        r = returns_from(ticker, filing["filingDate"])
        if r.get("entry") is not None:
            print(f"  ENTRY: ${r['entry']:.2f} on {r['entry_date']} → "
                  f"now ${r.get('now_px', 0):.2f}")
            seg = "  RETURN: " + "  ".join(
                f"{k}:{r[k]:+.0f}%" for k in ("1d", "1w", "1mo", "now") if k in r)
            print(seg)
            print(f"  vs SPY: stock {r['now']:+.0f}% | SPY {r['spy_now']:+.0f}% | "
                  f"EXCESS {r['excess']:+.0f}%")
            if r["excess"] > 0:
                alpha_pass += 1
            rows.append((ticker, would_fire, r["now"], r["spy_now"], r["excess"]))
        time.sleep(0.4)

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"DETECTION: {detect_pass}/{len(DEALS)} deals would have fired an alert")
    if rows:
        print(f"ALPHA:     {alpha_pass}/{len(rows)} beat SPY since the 8-K")
        avg = sum(r[2] for r in rows) / len(rows)
        avg_x = sum(r[4] for r in rows) / len(rows)
        print(f"           avg return since 8-K: {avg:+.0f}%  |  avg excess vs SPY: {avg_x:+.0f}%")
    print("\nNote: entry = CLOSE on the 8-K filing date (conservative — firehose")
    print("fires within ~15 min of filing, so intraday entry would be earlier/cheaper).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
