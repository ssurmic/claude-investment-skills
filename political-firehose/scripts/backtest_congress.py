#!/usr/bin/env python3
"""
backtest_congress.py — Verify Congress STOCK Act PTR watcher.

Fetches last 30 days of House + Senate PTR filings and prints:
  1. ALL filings found (with source, date, politician)
  2. TRACKED POLITICIANS matching the registry
  3. Aggregated summary table

Usage:
    python3 backtest_congress.py            # last 30 days, parses PDFs
    python3 backtest_congress.py 14         # last 14 days
    python3 backtest_congress.py 30 --no-pdfs  # skip PDF parsing (fast mode)
"""

import sys
import os

# Resolve path so we can import from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from congress_watcher import fetch_recent_congress_trades, get_tracked_politicians


def _fmt_row(
    politician: str,
    filing_date: str,
    source: str,
    tx_type: str,
    ticker: str,
    amount: str,
    party: str,
    state: str,
) -> str:
    """Format a single trade row for table display."""
    party_str = f"[{party}]" if party else "   "
    ticker_str = ticker if ticker else "—"
    amount_str = amount if amount else "—"
    tx_str = tx_type[:4] if tx_type else "—"
    src = "SEN" if source == "senate" else "HSE"
    return (
        f"  {politician[:28]:<28} {party_str:<4} {state or '??':<4} "
        f"{filing_date or '??':<12} {src} "
        f"{tx_str:<5} {ticker_str:<6} {amount_str}"
    )


def _header() -> str:
    return (
        f"  {'Name':<28} {'Par':<4} {'ST':<4} "
        f"{'Filed':<12} Src {'Type':<5} {'Tckr':<6} Amount"
    )


def main():
    # Parse CLI args
    days_back = 30
    parse_pdfs = True

    args = sys.argv[1:]
    for arg in args:
        if arg.isdigit():
            days_back = int(arg)
        elif arg in ("--no-pdfs", "--fast"):
            parse_pdfs = False

    print(f"Congress STOCK Act PTR Watcher — last {days_back} days", flush=True)
    print("=" * 70)

    trades = fetch_recent_congress_trades(
        days_back=days_back,
        parse_pdfs=parse_pdfs,
        include_senate=True,
        include_house=True,
    )

    # ── Counts ─────────────────────────────────────────────────────────────────
    house_trades = [t for t in trades if t["source"] == "house"]
    senate_trades = [t for t in trades if t["source"] == "senate"]

    # Unique filers (dedupe on politician+date)
    house_filings = set((t["politician"], t["filing_date"]) for t in house_trades)
    senate_filings = set((t["politician"], t["filing_date"]) for t in senate_trades)

    print(f"\nHouse PTR filings  (last {days_back} days): {len(house_filings)} unique filers  "
          f"/ {len(house_trades)} transaction rows")
    print(f"Senate PTR filings (last {days_back} days): {len(senate_filings)} unique filers  "
          f"/ {len(senate_trades)} transaction rows")

    # ── ALL HOUSE FILINGS ─────────────────────────────────────────────────────
    if house_trades:
        print(f"\n{'─'*70}")
        print(f"ALL HOUSE PTR FILINGS (last {days_back} days) — {len(house_trades)} rows")
        print(_header())
        print(f"  {'─'*68}")

        # Group by politician+date for display
        seen_filer = set()
        for t in house_trades:
            key = (t["politician"], t["filing_date"])
            is_first = key not in seen_filer
            seen_filer.add(key)

            # Show filer name on first occurrence only
            if is_first:
                tracked_marker = " *" if t.get("is_tracked") else ""
                display_name = t["politician"] + tracked_marker
                party_str = t.get("party") or ""
                state_str = t.get("state") or t.get("district", "")[:2]
            else:
                display_name = "  ↳"  # continuation row
                party_str = ""
                state_str = ""
            print(_fmt_row(
                display_name,
                t["filing_date"] or "",
                t["source"],
                t.get("transaction_type") or "",
                t.get("ticker") or "",
                t.get("amount_range") or "",
                party_str,
                state_str,
            ))
        print(f"\n  (* = in tracked politician registry)")

    # ── ALL SENATE FILINGS ────────────────────────────────────────────────────
    if senate_trades:
        print(f"\n{'─'*70}")
        print(f"ALL SENATE PTR FILINGS (last {days_back} days) — {len(senate_trades)} rows")
        print(_header())
        print(f"  {'─'*68}")
        for t in senate_trades:
            tracked_marker = " *" if t.get("is_tracked") else ""
            print(_fmt_row(
                t["politician"] + tracked_marker,
                t["filing_date"] or "",
                t["source"],
                t.get("transaction_type") or "",
                t.get("ticker") or "",
                t.get("amount_range") or "",
                t.get("party") or "",
                t.get("state") or "",
            ))
        print(f"\n  (* = in tracked politician registry)")
    elif not senate_trades:
        print(f"\n{'─'*70}")
        print(f"SENATE PTR FILINGS: 0 records")
        print("  NOTE: Senate eFD API may be blocked by Akamai WAF in automated mode.")
        print("  Senate data requires a real browser session or Playwright-based fetch.")

    # ── TRACKED POLITICIANS ───────────────────────────────────────────────────
    tracked = [t for t in trades if t.get("is_tracked")]
    print(f"\n{'─'*70}")
    print(f"TRACKED POLITICIANS — matching registry ({len(tracked)} records)")

    if tracked:
        print(_header())
        print(f"  {'─'*68}")
        for t in tracked:
            print(_fmt_row(
                t["politician"],
                t["filing_date"] or "",
                t["source"],
                t.get("transaction_type") or "",
                t.get("ticker") or "",
                t.get("amount_range") or "",
                t.get("party") or "",
                t.get("state") or t.get("district", "")[:2],
            ))
    else:
        print("  (none found — extend the registry in congress_watcher.py)")

    # ── REGISTRY MEMBERS NOT FILING ───────────────────────────────────────────
    registry = get_tracked_politicians()
    tracked_names = set(t["politician"].lower().split()[-1] for t in tracked)
    missing = [
        p for p in registry
        if p["name"].lower().split()[-1] not in tracked_names
    ]
    if missing:
        print(f"\n{'─'*70}")
        print(f"REGISTRY MEMBERS WITH NO RECENT FILING ({len(missing)}):")
        for p in missing:
            print(f"  {p['name']:<28} [{p['party']}] {p['state']}  ({p['chamber']})")

    # ── STATS ─────────────────────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"STATS (House parsed transactions only):")

    # Count by type
    purchases = [t for t in house_trades if t.get("transaction_type") == "Purchase"]
    sales = [t for t in house_trades if t.get("transaction_type") == "Sale"]
    with_ticker = [t for t in house_trades if t.get("ticker")]
    filings_only = [t for t in house_trades if not t.get("transaction_type")]

    print(f"  Purchases:          {len(purchases)}")
    print(f"  Sales:              {len(sales)}")
    print(f"  With ticker:        {len(with_ticker)}")
    print(f"  Filing-only rows:   {len(filings_only)} (paper scans or PDF parse failures)")

    if with_ticker:
        # Most traded tickers
        from collections import Counter
        ticker_counts = Counter(t["ticker"] for t in with_ticker)
        print(f"\n  Top tickers (last {days_back} days):")
        for ticker, count in ticker_counts.most_common(10):
            print(f"    {ticker:<8} {count:>3} transactions")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
