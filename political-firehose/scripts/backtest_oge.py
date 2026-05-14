#!/usr/bin/env python3
"""
backtest_oge.py — Validate the OGE 278-T parser against three known Trump filings.

Downloads and parses:
  1. Oct 2025 filing (4 pages)
  2. Feb 2026 filing (5 pages)
  3. May 2026 filing (113 pages, ~3,642 transactions)

Usage:
    python3 backtest_oge.py
"""

import re
import sys
from collections import Counter

# Ensure the scripts directory is on path so we can import oge_watcher
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oge_watcher import parse_oge_278t, parse_amount, extract_ticker

# ---------------------------------------------------------------------------
# Known test filings
# ---------------------------------------------------------------------------

FILINGS = [
    {
        "label": "Trump 10.20.2025 278-T",
        "url": (
            "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/"
            "18353894FE440B3685258D430031A337/"
            "$FILE/Donald%20J.%20Trump%2010.20.2025%20278-T%20(2).pdf"
        ),
    },
    {
        "label": "Trump 2.26.2026 278-T",
        "url": (
            "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/"
            "BCF60D94B8F1E59285258DB000347F61/"
            "$FILE/Donald%20J.%20Trump%202.26.2026%20278-T%20(2).pdf"
        ),
    },
    {
        "label": "Trump 5.8.2026 278-T (Q1 2026)",
        "url": (
            "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/"
            "405E4EC4E27BE8D185258DF7002DD1C0/"
            "$FILE/Trump,%20Donald%20J.-05.08.2026-278T(2).pdf"
        ),
    },
]


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def top_by_amount(transactions: list, n: int = 5) -> list:
    """Return top-N transactions sorted by amount_max descending."""
    return sorted(transactions, key=lambda t: t["amount_max"], reverse=True)[:n]


def print_summary(label: str, idx: int, transactions: list) -> None:
    """Print a formatted summary block for one filing."""
    purchases = [t for t in transactions if t["type"] == "Purchase"]
    sales     = [t for t in transactions if t["type"] == "Sale"]

    print(f"\n[{idx}] {label}")
    print(f"    Transactions found: {len(transactions):,}")
    print(f"    Purchases: {len(purchases)}  |  Sales: {len(sales)}")

    if not transactions:
        print("    (no transactions parsed)")
        return

    # Top 5 by amount
    print("    Largest (by amount category):")
    for tx in top_by_amount(transactions):
        name = tx["ticker"] or tx["asset"][:40]
        clean_name = name[:40].ljust(40)
        print(f"      {clean_name} | {tx['type'][0]} | {tx['amount_range']}")

    # Top tickers for buys and sells
    buy_tickers  = [t["ticker"] for t in purchases if t["ticker"]]
    sell_tickers = [t["ticker"] for t in sales     if t["ticker"]]

    # Show most-frequently-mentioned tickers
    if buy_tickers:
        top_buys = [k for k, _ in Counter(buy_tickers).most_common(7)]
        print(f"    Top buys:  {', '.join(top_buys[:7])}")
    if sell_tickers:
        top_sells = [k for k, _ in Counter(sell_tickers).most_common(7)]
        print(f"    Top sells: {', '.join(top_sells[:7])}")

    # Quick transaction table (first 8 rows)
    print()
    print(f"    {'#':<4} {'Date':<12} {'Type':<4} {'Amount Range':<30} {'Asset (truncated)'}")
    print(f"    {'-'*4} {'-'*12} {'-'*4} {'-'*30} {'-'*40}")
    for i, tx in enumerate(transactions[:8], 1):
        asset_short = (tx["asset"] or "")[:45]
        print(f"    {i:<4} {tx['date']:<12} {tx['type'][0]:<4} {tx['amount_range']:<30} {asset_short}")
    if len(transactions) > 8:
        print(f"    ... and {len(transactions) - 8} more ...")


# ---------------------------------------------------------------------------
# Cross-validation checks
# ---------------------------------------------------------------------------

def run_cross_validation(all_results: list) -> None:
    """Run sanity checks across filings."""
    print("\n" + "=" * 60)
    print("CROSS-VALIDATION")
    print("=" * 60)

    # Check 1: May 2026 should have the most transactions
    counts = [len(r) for r in all_results]
    print(f"Transaction counts: {counts}")
    assert counts[2] > counts[1] > 0, \
        f"Expected May 2026 > Feb 2026 > 0, got {counts}"
    print("  [PASS] Filing sizes are in expected order")

    # Check 2: Oct 2025 all purchases (all-bond filing)
    oct_types = set(t["type"] for t in all_results[0])
    print(f"  Oct 2025 transaction types: {oct_types}")
    # Oct 2025 is all-purchase (bonds bought at market)
    if oct_types == {"Purchase"}:
        print("  [PASS] Oct 2025: all purchases as expected")
    else:
        print(f"  [INFO] Oct 2025 has mixed types: {oct_types}")

    # Check 3: May 2026 should have >1000 transactions
    may_count = len(all_results[2])
    print(f"  May 2026 count: {may_count:,}")
    if may_count >= 1000:
        print(f"  [PASS] May 2026 has {may_count:,} transactions (large filing)")
    else:
        print(f"  [WARN] May 2026 only has {may_count:,} — expected >1000 (target ~3,642)")

    # Check 4: Known stock names should appear in May 2026
    may_assets = ' '.join(t["asset"].upper() for t in all_results[2])
    expected_names = ["NVIDIA", "ORACLE", "MICROSOFT", "AMAZON", "APPLE"]
    found = [name for name in expected_names if name in may_assets]
    print(f"  May 2026 recognizes: {found}")
    if len(found) >= 3:
        print("  [PASS] Major names detected in May 2026")
    else:
        print(f"  [WARN] Only {len(found)}/{len(expected_names)} expected names found")

    # Check 5: All dates look sane (year 2024-2026)
    all_txns = [t for r in all_results for t in r]
    bad_dates = [t["date"] for t in all_txns
                 if t["date"] and not re.match(r'^\d{1,2}/\d{1,2}/20[2-9]\d$', t["date"])]
    if not bad_dates:
        print("  [PASS] All dates match M/D/20XX format")
    else:
        print(f"  [WARN] {len(bad_dates)} malformed dates (showing first 5): {bad_dates[:5]}")

    # Check 6: Amount ranges are all non-zero
    zero_amount = [t for t in all_txns if t["amount_min"] == 0]
    if not zero_amount:
        print("  [PASS] All transactions have a parsed amount range")
    else:
        print(f"  [WARN] {len(zero_amount)} transactions with unknown amount")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("=== BACKTEST: OGE 278-T Parser ===")
    print("=" * 60)

    all_results = []

    for idx, filing in enumerate(FILINGS, 1):
        print(f"\n{'='*60}")
        print(f"Parsing filing {idx}/{len(FILINGS)}: {filing['label']}")
        print(f"{'='*60}")

        transactions = parse_oge_278t(filing["url"])
        all_results.append(transactions)
        print_summary(filing["label"], idx, transactions)

    run_cross_validation(all_results)

    print("\nBacktest complete.")
    print(f"Total transactions across all filings: {sum(len(r) for r in all_results):,}")


if __name__ == "__main__":
    main()
