#!/usr/bin/env python3
"""CTA Trigger Level Firehose — daily systematic-flow radar.

Replicates the core of sell-side CTA/trend-follower models (GS, Nomura
McElligott style) with public data:

  1. Multi-horizon momentum flip levels (1M / 3M / 6M / 12M lookback price)
     — price crossing below a flip level = that horizon's momentum turns
     negative = mechanical selling tranche.
  2. Key moving averages (20/50/100/200 DMA) — the 50DMA zone is where
     bank models' "first sell trigger" usually clusters (±1%).
  3. Realized-vol regime (1M/3M annualized) — vol-control/risk-parity
     deleveraging pressure proxy. RV > 20% = mechanical de-risking
     regardless of price direction.

State-aware: remembers each trigger's side (above/below) in state.json and
prepends a 🔔 TRIGGER BREACHED banner when an index crosses a line since the
last run. Telegram fan-out via shared _tg.py (DM + channel).

Usage
─────
  python cta_levels.py                  # print to stdout only
  python cta_levels.py --telegram       # send digest (breach => banner)
  TEST_MODE=1 python cta_levels.py --telegram   # dry-run send

Env: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / TELEGRAM_CHAT_ID_CHANNEL
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yfinance as yf

# repo root (two levels up) for shared _tg helper
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import _tg  # noqa: E402

STATE_FILE = Path(__file__).resolve().parent / "state.json"

INDICES = {
    "^GSPC": "SPX",
    "^NDX":  "NDX",
    "^RUT":  "RTY",
}

# (label, lookback trading days) — momentum flip horizons
MOMENTUM_HORIZONS = [
    ("1M", 21),
    ("3M", 63),
    ("6M", 126),
    ("12M", 252),
]

MA_WINDOWS = [20, 50, 100, 200]

VOL_DERISK_THRESHOLD = 20.0  # 1M RV above this = vol-control selling regime


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    state["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def analyze_index(symbol: str) -> dict | None:
    """Compute trigger levels + vol regime for one index."""
    try:
        hist = yf.Ticker(symbol).history(period="2y")
        close = hist["Close"].dropna()
        if len(close) < 260:
            return None
    except Exception as e:
        print(f"[WARN] {symbol}: {e}", file=sys.stderr)
        return None

    price = float(close.iloc[-1])
    asof = str(close.index[-1].date())

    triggers = []  # (name, level, above:bool)
    for label, days in MOMENTUM_HORIZONS:
        level = float(close.iloc[-days - 1])
        triggers.append((f"mom_{label}", level, price > level))
    for n in MA_WINDOWS:
        level = float(close.rolling(n).mean().iloc[-1])
        triggers.append((f"ma_{n}d", level, price > level))

    rets = np.diff(np.log(close.values))
    rv1m = float(np.std(rets[-21:]) * np.sqrt(252) * 100)
    rv3m = float(np.std(rets[-63:]) * np.sqrt(252) * 100)

    # nearest unbroken support trigger below price
    below = sorted((lv for _, lv, ab in triggers if ab), reverse=True)
    nearest_support = below[0] if below else None

    return {
        "price": price,
        "asof": asof,
        "triggers": triggers,
        "rv1m": rv1m,
        "rv3m": rv3m,
        "nearest_support": nearest_support,
    }


def detect_breaches(name: str, result: dict, state: dict) -> list[str]:
    """Compare trigger sides vs last run; return list of newly-breached names."""
    prev = state.get(name, {}).get("sides", {})
    breaches = []
    for tname, level, above in result["triggers"]:
        was_above = prev.get(tname)
        if was_above is True and not above:
            breaches.append(f"{tname} ({level:,.0f})")
    return breaches


def fmt_trigger_name(tname: str) -> str:
    if tname.startswith("mom_"):
        return f"{tname[4:]}动量线"
    return f"{tname[3:-1]}日均线"


def build_digest(results: dict, all_breaches: dict) -> str:
    lines = []
    if any(all_breaches.values()):
        lines.append("🔔 *CTA TRIGGER BREACHED* 🔔")
        for idx, brs in all_breaches.items():
            for b in brs:
                lines.append(f"  🚨 {idx}: 跌破 {b}")
        lines.append("")

    lines.append("📊 *CTA Trigger Radar*")
    lines.append(f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    for idx, r in results.items():
        if r is None:
            lines.append(f"*{idx}*: ⚠️ no data")
            continue
        lines.append(f"*{idx}*  `{r['price']:,.0f}`  (close {r['asof']})")

        # momentum flips
        for tname, level, above in r["triggers"]:
            if not tname.startswith("mom_"):
                continue
            dist = (r["price"] / level - 1) * 100
            flag = "✅" if above else "🚨"
            warn = " ⚠️" if above and dist < 1.5 else ""
            lines.append(
                f"  {flag} {fmt_trigger_name(tname)} `{level:,.0f}` ({dist:+.1f}%){warn}")

        # MAs — only flag the interesting ones (50d = first-trigger zone)
        for tname, level, above in r["triggers"]:
            if not tname.startswith("ma_"):
                continue
            n = tname[3:-1]
            if n not in ("50", "200"):
                continue
            dist = (r["price"] / level - 1) * 100
            flag = "✅" if above else "🚨"
            star = " ⭐首轮触发区" if n == "50" else ""
            lines.append(f"  {flag} {n}DMA `{level:,.0f}` ({dist:+.1f}%){star}")

        # vol regime
        vol_flag = "🔥vol-control卖压" if r["rv1m"] > VOL_DERISK_THRESHOLD else "🆗"
        lines.append(f"  RV: 1M `{r['rv1m']:.1f}%` / 3M `{r['rv3m']:.1f}%` {vol_flag}")
        lines.append("")

    lines.append("_动量线跌破=对应周期CTA机械卖出 | 50DMA±1%≈投行模型首轮触发区_")
    return "\n".join(lines)


def main() -> int:
    send = "--telegram" in sys.argv
    force = "--force" in sys.argv or True  # daily digest always sends

    state = load_state()
    results: dict = {}
    all_breaches: dict = {}

    for symbol, name in INDICES.items():
        r = analyze_index(symbol)
        results[name] = r
        if r is None:
            continue
        all_breaches[name] = detect_breaches(name, r, state)
        state[name] = {
            "sides": {t: ab for t, _, ab in r["triggers"]},
            "price": r["price"],
            "asof": r["asof"],
        }

    digest = build_digest(results, all_breaches)
    print(digest)

    if send:
        tm = os.environ.get("TEST_MODE", "") == "1"
        ok = _tg.send(digest, test_mode=tm)
        print(f"[telegram] sent={ok}", file=sys.stderr)

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
