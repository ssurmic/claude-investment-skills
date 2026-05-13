#!/usr/bin/env python3
"""
13f_firehose.py — Daily scan for new 13F-HR filings across the fund registry.

For each fund in the registry:
  1. Fetch their most recent 13F filing from EDGAR submissions API
  2. Check state.json for last-seen accession — skip if already alerted
  3. Pull the prior 13F and compute the diff
  4. Render a Telegram alert and send it
  5. Update state to mark accession as seen

State persists across cron runs via state.json (committed by GH Actions).
Designed to be cheap to run: most days, all funds have nothing new and the
script exits in ~5 seconds total (one HTTP HEAD per fund).

Env vars:
    EDGAR_USER_AGENT       Required by SEC: "<email> <product>/<version>"
    TELEGRAM_BOT_TOKEN     Bot token
    TELEGRAM_CHAT_ID       Target chat
    TEST_MODE              "1" = print alerts, do not send to Telegram
    PRIORITY_MAX           Only scan funds with priority <= this (default 3)
    FORCE_RESCAN           "1" = ignore state and re-emit all funds (for testing)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Make sibling imports work whether run via `python 13f_firehose.py` or as a module
sys.path.insert(0, str(Path(__file__).resolve().parent))

from edgar_13f import fetch_latest_filing, fetch_filing_by_accession, list_13f_filings
from diff import compute_diff
from format_alert import render_alert, edgar_url_for_filing
from fund_registry import get_funds, Fund


STATE_FILE = Path(__file__).parent / "state.json"
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
FORCE_RESCAN = os.environ.get("FORCE_RESCAN", "") == "1"
PRIORITY_MAX = int(os.environ.get("PRIORITY_MAX", "3"))


# ─── State ─────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            print(f"[WARN] state.json corrupt, starting fresh: {e}", file=sys.stderr)
    return {"seen": {}, "last_run_iso": None}


def save_state(state: dict) -> None:
    state["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ─── Telegram ──────────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    if TEST_MODE:
        print("─── TEST_MODE: would send ───", file=sys.stderr)
        print(msg, file=sys.stderr)
        print("─── end ───", file=sys.stderr)
        return True

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[WARN] No Telegram creds, message NOT sent:\n{msg[:500]}", file=sys.stderr)
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
        print(f"[ERROR] Telegram exception: {e}", file=sys.stderr)
        return False


# ─── Per-fund processing ──────────────────────────────────────────────────
def process_fund(fund: Fund, state: dict) -> bool:
    """Process one fund. Returns True if an alert was sent."""
    seen_map = state.setdefault("seen", {})
    cik_str = str(fund.cik)
    last_seen_acc = seen_map.get(cik_str)

    # 1. Get list of recent 13Fs
    try:
        filings = list_13f_filings(fund.cik, limit=4)
    except Exception as e:
        print(f"[WARN] {fund.name} (CIK {fund.cik}): EDGAR list failed: {e}",
              file=sys.stderr)
        return False
    if not filings:
        print(f"[INFO] {fund.name}: no 13F-HR filings on record", file=sys.stderr)
        return False

    latest = filings[0]
    latest_acc = latest["accession"]

    # 2. Already alerted? skip.
    if not FORCE_RESCAN and last_seen_acc == latest_acc:
        # Already alerted on this filing.
        return False

    print(f"[NEW] {fund.name}: {latest['form']} period {latest['period']} "
          f"filed {latest['filed']} (was {last_seen_acc or 'never'})",
          file=sys.stderr)

    # 3. Pull current and prior filings (full holdings)
    current = fetch_filing_by_accession(fund.cik, latest_acc)
    if not current:
        print(f"[WARN] {fund.name}: current filing fetch failed", file=sys.stderr)
        return False

    prior = None
    if len(filings) > 1:
        prior = fetch_filing_by_accession(fund.cik, filings[1]["accession"])
        if not prior:
            print(f"[WARN] {fund.name}: prior filing fetch failed, "
                  "diff will mark everything NEW", file=sys.stderr)

    # 4. Compute diff
    diff = compute_diff(current, prior, fund.name)

    # 5. Render + send
    edgar_url = edgar_url_for_filing(fund.cik, latest_acc)
    msg = render_alert(diff, fund, edgar_url)
    sent = send_telegram(msg)

    if sent:
        seen_map[cik_str] = latest_acc
        print(f"[OK] {fund.name}: alert sent, state updated", file=sys.stderr)
    else:
        print(f"[ERR] {fund.name}: alert NOT sent, state NOT updated",
              file=sys.stderr)
    return sent


# ─── Main ──────────────────────────────────────────────────────────────────
def main() -> int:
    state = load_state()
    funds = get_funds(priority_max=PRIORITY_MAX)
    print(f"[INFO] 13F scan: {len(funds)} funds, priority<={PRIORITY_MAX}, "
          f"TEST_MODE={TEST_MODE}, FORCE_RESCAN={FORCE_RESCAN}",
          file=sys.stderr)

    alerts_sent = 0
    for fund in funds:
        try:
            if process_fund(fund, state):
                alerts_sent += 1
        except Exception as e:
            print(f"[ERROR] {fund.name}: unexpected exception: {e}",
                  file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        # save state after every fund so partial progress survives
        save_state(state)

    print(f"[DONE] alerts_sent={alerts_sent} funds_scanned={len(funds)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
