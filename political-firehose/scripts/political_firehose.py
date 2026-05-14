#!/usr/bin/env python3
"""
political_firehose.py — Monitor political stock trades and alert via Telegram.

Covers two disclosure systems:
  1. STOCK Act PTR  — Congress (Senate + House), scraped daily from disclosure portals
  2. OGE Form 278-T — Executive branch (President, Cabinet), PDF-based

Env vars:
    TELEGRAM_BOT_TOKEN   Bot token
    TELEGRAM_CHAT_ID     Target chat
    TEST_MODE            "1" = print, don't send Telegram
    PRIORITY_MAX         Only alert on priority <= this (default 2)
    FORCE_RESCAN         "1" = re-alert even if already seen
    DAYS_BACK            How many days back to scan for new trades (default 3)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from politician_registry import get_politicians, find_politician, get_congress_names, get_oge_names
from format_alert import render_congress_alert, render_oge_alert

# Deferred imports to keep startup fast
congress_watcher = None
oge_watcher = None

STATE_FILE = Path(__file__).parent / "state.json"
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
FORCE_RESCAN = os.environ.get("FORCE_RESCAN", "") == "1"
PRIORITY_MAX = int(os.environ.get("PRIORITY_MAX", "2"))
DAYS_BACK = int(os.environ.get("DAYS_BACK", "3"))


# ─── State ─────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            print(f"[WARN] state.json corrupt: {e}", file=sys.stderr)
    return {"congress_seen": {}, "oge_seen": set(), "last_run_iso": None}


def save_state(state: dict) -> None:
    state["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    # Sets aren't JSON-serializable; convert to sorted list
    if isinstance(state.get("oge_seen"), set):
        state["oge_seen"] = sorted(state["oge_seen"])
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ─── Telegram ──────────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    if TEST_MODE:
        print("─── TEST_MODE: would send ───", file=sys.stderr)
        print(msg)
        print("─── end ───", file=sys.stderr)
        return True
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[WARN] No Telegram creds, msg NOT sent:\n{msg[:300]}", file=sys.stderr)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if r.ok:
            return True
        print(f"[ERROR] Telegram {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] Telegram: {e}", file=sys.stderr)
        return False


# ─── Congress processing ──────────────────────────────────────────────────
def run_congress_scan(state: dict) -> int:
    global congress_watcher
    if congress_watcher is None:
        import congress_watcher as _cw
        congress_watcher = _cw

    seen = state.setdefault("congress_seen", {})
    tracked_names = get_congress_names()
    politicians = get_politicians(system="CONGRESS", priority_max=PRIORITY_MAX)

    print(f"[INFO] Congress scan: {len(politicians)} politicians, {DAYS_BACK} days back",
          file=sys.stderr)

    try:
        all_trades = congress_watcher.fetch_recent_congress_trades(days_back=DAYS_BACK)
    except Exception as e:
        print(f"[ERROR] Congress fetch failed: {e}", file=sys.stderr)
        return 0

    # Group trades by politician
    by_politician: dict[str, list] = {}
    for trade in all_trades:
        # Match against registry
        first = trade.get("first_name", "") or trade.get("politician", "").split()[0]
        last = trade.get("last_name", "") or trade.get("politician", "").split()[-1]
        p = find_politician(first, last)
        if p is None:
            continue
        if p.priority > PRIORITY_MAX:
            continue
        key = p.name
        by_politician.setdefault(key, []).append(trade)

    alerts_sent = 0
    for p in politicians:
        trades = by_politician.get(p.name, [])
        if not trades:
            continue

        # Dedup: build a key from trade date + ticker + type
        new_trades = []
        for t in trades:
            trade_key = (
                f"{t.get('transaction_date','')}"
                f"|{t.get('ticker','')}"
                f"|{t.get('transaction_type','')}"
                f"|{t.get('amount_range','')}"
            )
            if not FORCE_RESCAN and trade_key in seen.get(p.name, set()):
                continue
            new_trades.append((trade_key, t))

        if not new_trades:
            print(f"[SKIP] {p.name}: {len(trades)} trades already seen", file=sys.stderr)
            continue

        print(f"[NEW] {p.name}: {len(new_trades)} new trade(s)", file=sys.stderr)
        filing_url = new_trades[0][1].get("filing_url", "https://efdsearch.senate.gov")
        msg = render_congress_alert(p, [t for _, t in new_trades], filing_url)
        if send_telegram(msg):
            seen.setdefault(p.name, [])
            if isinstance(seen[p.name], list):
                seen[p.name].extend(k for k, _ in new_trades)
            alerts_sent += 1
        save_state(state)

    return alerts_sent


# ─── OGE processing ──────────────────────────────────────────────────────
def run_oge_scan(state: dict) -> int:
    global oge_watcher
    if oge_watcher is None:
        import oge_watcher as _ow
        oge_watcher = _ow

    oge_seen_raw = state.get("oge_seen", [])
    oge_seen: set[str] = set(oge_seen_raw) if isinstance(oge_seen_raw, list) else oge_seen_raw
    tracked_names = get_oge_names()
    politicians = get_politicians(system="OGE", priority_max=PRIORITY_MAX)

    print(f"[INFO] OGE scan: {len(politicians)} officials, checking for new 278-T PDFs",
          file=sys.stderr)

    try:
        new_filings = oge_watcher.check_oge_new_filings(known_urls=oge_seen)
    except Exception as e:
        print(f"[ERROR] OGE check failed: {e}", file=sys.stderr)
        return 0

    alerts_sent = 0
    for filing in new_filings:
        person_name = filing.get("person", "")
        last_name = person_name.split(",")[0].strip() if "," in person_name else person_name.split()[-1]
        first_name = person_name.split(",")[1].strip() if "," in person_name else person_name.split()[0]

        p = find_politician(first_name, last_name)
        if p is None:
            print(f"[SKIP] OGE: {person_name} not in registry", file=sys.stderr)
            oge_seen.add(filing["url"])
            continue
        if p.priority > PRIORITY_MAX:
            print(f"[SKIP] OGE: {p.name} priority {p.priority} > max {PRIORITY_MAX}",
                  file=sys.stderr)
            oge_seen.add(filing["url"])
            continue

        # Date filter: skip historical filings beyond DAYS_BACK window
        filing_date_str = filing.get("date", "")
        if filing_date_str and filing_date_str != "unknown":
            try:
                fdate = datetime.strptime(filing_date_str, "%m/%d/%Y")
                cutoff = datetime.now() - timedelta(days=DAYS_BACK + 7)  # +7 buffer
                if fdate < cutoff and not FORCE_RESCAN:
                    print(f"[SKIP] OGE: {p.name} filing {filing_date_str} older than "
                          f"DAYS_BACK+7={DAYS_BACK+7}d — marking seen, skipping alert",
                          file=sys.stderr)
                    oge_seen.add(filing["url"])
                    continue
            except ValueError:
                pass

        print(f"[NEW] OGE: {p.name} — {filing.get('date','?')} — parsing PDF...",
              file=sys.stderr)

        try:
            trades = oge_watcher.parse_oge_278t(filing["url"])
        except Exception as e:
            print(f"[WARN] OGE PDF parse failed for {p.name}: {e}", file=sys.stderr)
            trades = []

        if not trades:
            print(f"[WARN] OGE: no trades parsed from {filing['url']}", file=sys.stderr)

        msg = render_oge_alert(
            p, trades,
            pdf_url=filing["url"],
            report_period=filing.get("date", ""),
        )
        if send_telegram(msg):
            oge_seen.add(filing["url"])
            alerts_sent += 1
        state["oge_seen"] = sorted(oge_seen)
        save_state(state)

    return alerts_sent


# ─── Main ─────────────────────────────────────────────────────────────────
def main() -> int:
    state = load_state()
    print(
        f"[INFO] Political Firehose | TEST={TEST_MODE} FORCE={FORCE_RESCAN} "
        f"P<={PRIORITY_MAX} DAYS_BACK={DAYS_BACK}",
        file=sys.stderr,
    )

    total = 0

    try:
        total += run_congress_scan(state)
    except Exception as e:
        print(f"[ERROR] Congress scan crashed: {e}", file=sys.stderr)
        import traceback; traceback.print_exc(file=sys.stderr)

    try:
        total += run_oge_scan(state)
    except Exception as e:
        print(f"[ERROR] OGE scan crashed: {e}", file=sys.stderr)
        import traceback; traceback.print_exc(file=sys.stderr)

    save_state(state)
    print(f"[DONE] total_alerts={total}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
