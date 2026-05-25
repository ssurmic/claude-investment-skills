#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capex_monitor.py — Hyperscaler CapEx tracker (the master AI-buildout signal).

超大规模厂商 CapEx 追踪器 —— AI 基建周期的总闸门信号.

═══════════════════════════════════════════════════════════════════════
  WHY THIS IS THE KEY SIGNAL / 为什么这是最关键的信号
═══════════════════════════════════════════════════════════════════════

Every dollar of AI infrastructure alpha downstream (GPUs, optics, power,
switch fabric) is ultimately funded by a handful of hyperscalers' CapEx.
If MSFT/GOOGL/AMZN/META/ORCL CapEx is ACCELERATING → the whole supply chain
(NVDA, AVGO, VRT, COHR, ANET, MU...) eats. If it ROLLS OVER → the AI trade
tops. Tracking aggregate CapEx + the QoQ/YoY trend is the single highest
master signal for the entire thesis.

下游所有 AI 基建 alpha (GPU/光/电/交换) 的钱, 最终都来自这几家
hyperscaler 的 CapEx. CapEx 加速 = 整条供应链吃肉; CapEx 见顶回落 =
AI 交易做头. 跟踪合计 CapEx + 趋势 = 整个论点的总信号.

═══════════════════════════════════════════════════════════════════════
  WHAT IT DOES / 干啥
═══════════════════════════════════════════════════════════════════════

Every run:
  1. Pull quarterly CapEx (from cash-flow statement) for each spender via yfinance
  2. Compute latest-quarter CapEx + QoQ% + YoY%
  3. Dedup: alert per-name ONLY when a NEW quarter appears (= they just reported)
  4. Always recompute the AGGREGATE (Big-spender combined CapEx + YoY trend)
  5. On a new print OR in digest mode, push a Telegram table

State: capex_state.json maps ticker → last-seen quarter-end date.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TEST_MODE, DIGEST (force full table)
"""
from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# The CapEx deployers that fund the AI buildout. Sellers (NVDA/AVGO) excluded —
# we track who SPENDS, not who receives.
# 部署 CapEx 的买家. 卖方 (NVDA/AVGO) 不在内 — 我们盯花钱的.
SPENDERS: dict[str, str] = {
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "ORCL": "Oracle",
    "AAPL": "Apple",
    "CRWV": "CoreWeave",   # neocloud — pure AI capex
    "NBIS": "Nebius",      # neocloud
}

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "capex_state.json"

TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
DIGEST = os.environ.get("DIGEST", "") == "1"


# ─── State ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"seen": {}, "updated": None}


def save_state(state: dict) -> None:
    state["updated"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


# ─── CapEx pull ─────────────────────────────────────────────────────────

def pull_capex(ticker: str) -> list[tuple[str, float]]:
    """
    Return [(quarter_end_iso, capex_usd), ...] newest-first for a ticker.
    CapEx is reported as a negative cash outflow → we return abs() in USD.

    Returns [] on any error (non-fatal — one bad ticker shouldn't kill the run).
    """
    try:
        import yfinance as yf
        import pandas as pd  # noqa: F401  (yfinance pulls it in)

        cf = yf.Ticker(ticker).quarterly_cashflow
        if cf is None or cf.empty:
            return []

        # Find the CapEx row (label varies across yfinance versions)
        # 找 CapEx 行 (不同版本标签不一)
        row_label = None
        for idx in cf.index:
            if "capital expenditure" in str(idx).lower():
                row_label = idx
                break
        if row_label is None:
            return []

        out: list[tuple[str, float]] = []
        for col in cf.columns:
            val = cf.loc[row_label, col]
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            if v != v:  # NaN
                continue
            qend = col.date().isoformat() if hasattr(col, "date") else str(col)[:10]
            out.append((qend, abs(v)))

        out.sort(key=lambda x: x[0], reverse=True)
        return out
    except Exception as e:
        print(f"[WARN] {ticker} capex pull failed: {e}", file=sys.stderr)
        return []


def pct(new: float, old: float) -> float | None:
    if not old:
        return None
    return (new - old) / old * 100.0


# ─── Telegram ───────────────────────────────────────────────────────────

def send_telegram(msg: str) -> bool:
    if TEST_MODE:
        print("─── TEST_MODE: would send ───\n" + msg + "\n─── end ───",
              file=sys.stderr)
        return True
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[WARN] no Telegram creds; not sent:\n{msg}", file=sys.stderr)
        return False
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat_id, "text": msg,
        "parse_mode": "Markdown", "disable_web_page_preview": True,
    }, timeout=20)
    if r.status_code == 200:
        return True
    # Markdown parse failure → retry plain text so the alert always lands.
    print(f"[WARN] Telegram Markdown {r.status_code}: {r.text[:150]} — retry plain",
          file=sys.stderr)
    r2 = requests.post(url, json={
        "chat_id": chat_id, "text": msg, "disable_web_page_preview": True,
    }, timeout=20)
    return r2.status_code == 200


def fmt_usd(v: float) -> str:
    """Format USD to $X.XB / $XXXM."""
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    return f"${v/1e6:.0f}M"


def fmt_pct(p: float | None) -> str:
    if p is None:
        return "n/a"
    return f"{p:+.0f}%"


# ─── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    state = load_state()
    seen = state.get("seen", {})

    rows = []          # (ticker, name, qend, capex, qoq, yoy)
    new_prints = []    # tickers that just reported a new quarter

    for ticker, name in SPENDERS.items():
        series = pull_capex(ticker)
        if not series:
            print(f"[INFO] {ticker}: no capex data", file=sys.stderr)
            continue
        qend, capex = series[0]
        qoq = pct(capex, series[1][1]) if len(series) > 1 else None
        yoy = pct(capex, series[4][1]) if len(series) > 4 else None
        rows.append((ticker, name, qend, capex, qoq, yoy))

        if seen.get(ticker) != qend:
            new_prints.append(ticker)
            seen[ticker] = qend
        time.sleep(0.3)  # be gentle on yfinance

    if not rows:
        print("[DONE] no data pulled", file=sys.stderr)
        return 0

    # Aggregate: combined latest CapEx + YoY (only names with a YoY available)
    # 合计: 最新 CapEx 总和 + YoY 趋势 (总信号)
    agg_latest = sum(r[3] for r in rows)
    agg_yoy_now = sum(r[3] for r in rows if r[5] is not None)
    # year-ago sum for the same names that have a YoY
    yoy_base = 0.0
    for t, n, q, c, qoq, yoy in rows:
        if yoy is not None:
            yoy_base += c / (1 + yoy / 100.0)
    agg_yoy = pct(agg_yoy_now, yoy_base) if yoy_base else None

    should_send = bool(new_prints) or DIGEST
    print(f"[INFO] new prints: {new_prints or 'none'}; "
          f"agg latest {fmt_usd(agg_latest)} YoY {fmt_pct(agg_yoy)}",
          file=sys.stderr)

    if should_send:
        # Sort by latest CapEx desc
        rows.sort(key=lambda r: r[3], reverse=True)
        header = ("🏗️ *HYPERSCALER CAPEX* — AI buildout master signal"
                  if not new_prints else
                  f"🏗️🟢 *HYPERSCALER CAPEX — NEW PRINT* ({', '.join(new_prints)})")
        lines = [header, ""]
        for t, n, q, c, qoq, yoy in rows:
            star = " 🆕" if t in new_prints else ""
            lines.append(
                f"`{t:5s}` {fmt_usd(c):>7s}  QoQ {fmt_pct(qoq):>5s} · "
                f"YoY {fmt_pct(yoy):>5s}  _{q}_{star}"
            )
        lines.append("")
        lines.append(
            f"Σ *Combined*: {fmt_usd(agg_latest)} · "
            f"YoY {fmt_pct(agg_yoy)} {'📈' if (agg_yoy or 0) > 0 else '📉'}"
        )
        lines.append("_Accelerating = supply chain eats. Rolling over = AI trade tops._")
        send_telegram("\n".join(lines))

    if not TEST_MODE:
        state["seen"] = seen
        save_state(state)

    print(f"[DONE] rows={len(rows)} new={len(new_prints)} sent={should_send}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
