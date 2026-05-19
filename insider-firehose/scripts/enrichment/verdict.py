"""verdict.py — synthesize a clear BUY/WATCH/AVOID verdict with entry ladder.

Combines: smart money score + pattern match + sector heat + risk flags.

Rules (priority order):

  1. AVOID if:
     - Risk count ≥ 3 (story stock red flags)
     - Sector heat = ❄️❄️ (deep cold)
     - 1Y change > +80% AND insider buy < $1M (chasing top)

  2. BUY (3-tier ladder) if:
     - Smart Money Score ≥ 7 AND best pattern matched ≥ 4/5
     - OR Score ≥ 6 AND sector is AI 🔥🔥🔥 AND no risk flags
     - OR Pattern matched ≥ 4/5 AND risk_count ≤ 1

  3. WATCH if:
     - Score 5-6 AND pattern 2-3/5
     - OR Score ≥ 6 BUT risk_count = 1 or 2 (needs more confirmation)
     - OR good setup but >+25% from 52W low (entry timing not ideal)

  4. SKIP (lowest signal) if:
     - Score < 4
     - No pattern matched
     - Defensive cold sector with no real catalyst
"""
from __future__ import annotations


def _val(d, key, default=None):
    if not d:
        return default
    v = d.get(key)
    return default if v is None else v


def _compute_ladder(current_price: float, target_price: float | None,
                   p_low: float | None, p_high: float | None) -> dict:
    """Build a 3-tier entry ladder.

    T1 = current price (or slightly below if available)
    T2 = -5% from current OR vicinity of 52W low
    T3 = -12% from current OR 52W low
    Stop = -22% OR slightly below 52W low

    All values are absolute prices.
    """
    if current_price <= 0:
        return {}

    # 52W low and high (absolute prices) — recover from pct distances
    # p_low is pct ABOVE 52W low, p_high is pct BELOW 52W high (negative)
    low_52 = current_price / (1 + (p_low / 100)) if p_low is not None and p_low > 0 else None
    high_52 = current_price / (1 + (p_high / 100)) if p_high is not None else None

    t1 = round(current_price, 2)
    t2 = round(current_price * 0.945, 2)  # -5.5%
    t3 = round(current_price * 0.87, 2)   # -13%

    # If 52W low is between t2 and t3, snap t3 to that
    if low_52 and t3 > low_52 > t3 * 0.93:
        t3 = round(low_52 * 1.01, 2)  # 1% above 52W low

    stop = round(current_price * 0.78, 2)  # -22%
    if low_52 and stop > low_52 * 0.92:
        stop = round(low_52 * 0.92, 2)  # 8% below 52W low

    target = target_price or (high_52 * 0.85 if high_52 else current_price * 1.5)
    target = round(target, 2) if target else None

    # Compute average cost assuming 50/30/20
    avg_cost = (t1 * 0.5 + t2 * 0.3 + t3 * 0.2)
    if target and avg_cost > 0:
        upside_pct = (target - avg_cost) / avg_cost * 100
        downside_pct = (avg_cost - stop) / avg_cost * 100
        rr = round(upside_pct / downside_pct, 2) if downside_pct > 0 else 0
    else:
        rr = 0
        upside_pct = 0

    return {
        "t1": t1, "t2": t2, "t3": t3,
        "stop": stop, "target": target,
        "avg_cost": round(avg_cost, 2),
        "rr": rr,
        "upside_pct": round(upside_pct, 0),
    }


def compute_verdict(ticker: str, filing: dict, valuation: dict, price: dict,
                   sector: dict, score_block: dict, patterns: dict,
                   total_value: float) -> dict:
    """Return a verdict dict ready for the formatter.

    Keys:
      - tag: "BUY" / "WATCH" / "AVOID" / "SKIP"
      - emoji: visual tag
      - headline: one-line takeaway in Chinese
      - reason: 1-2 sentence explanation
      - ladder: dict with t1/t2/t3/stop/target/avg/rr (only if BUY)
      - close_to_buy: bool — is current price close to insider's buy price?
    """
    score = _val(score_block, "score", 0)
    risk_count = _val(patterns.get("risk"), "risk_count", 0)
    best = patterns.get("best_pattern", {})
    matched = _val(best, "matched", 0)
    total = _val(best, "total", 5)
    is_ai = _val(sector, "is_ai", False)
    heat = _val(sector, "heat", "")
    bucket = _val(sector, "bucket", "")

    ch_1y_raw = _val(price, "change_1y_pct")
    ch_1y_pct = (ch_1y_raw if ch_1y_raw is not None and abs(ch_1y_raw) > 1
                else ((ch_1y_raw * 100) if ch_1y_raw is not None else None))
    p_low = _val(price, "pct_vs_52w_low")
    cur_price = _val(price, "current")

    # Close to insider's buy price?
    buy_price = _val(filing, "price_per_share")
    close_to_buy = False
    if buy_price and cur_price and buy_price > 0:
        diff_pct = abs(cur_price - buy_price) / buy_price * 100
        close_to_buy = diff_pct <= 8  # within 8% of insider's cost

    # ── AVOID rules (highest priority) ────────────────────────────────
    if risk_count >= 3:
        return {
            "tag": "AVOID",
            "emoji": "❌",
            "headline": "AVOID · 红旗太多 (story stock)",
            "reason": f"{risk_count} 个风险信号叠加 — 即便有 insider buy 也避开",
            "close_to_buy": close_to_buy,
            "ladder": None,
        }

    if heat == "❄️❄️":
        return {
            "tag": "AVOID",
            "emoji": "❌",
            "headline": "AVOID · 深冷板块",
            "reason": f"{bucket} 是结构性逆风板块，单 insider buy 不够",
            "close_to_buy": close_to_buy,
            "ladder": None,
        }

    if ch_1y_pct is not None and ch_1y_pct > 80 and total_value < 1_000_000:
        return {
            "tag": "AVOID",
            "emoji": "❌",
            "headline": "AVOID · 已大涨 + insider buy 太小",
            "reason": f"1Y +{ch_1y_pct:.0f}% 已涨过，${total_value/1e3:.0f}K buy 不足以追高",
            "close_to_buy": close_to_buy,
            "ladder": None,
        }

    # ── BUY rules ──────────────────────────────────────────────────────
    target_price = _val(valuation, "analyst_target")
    p_high = _val(price, "pct_vs_52w_high")
    is_cold_sector = heat in ("❄️", "❄️❄️")

    buy_qualified = False
    buy_reason = ""

    if score >= 7 and matched >= 4 and risk_count <= 1 and not is_cold_sector:
        buy_qualified = True
        buy_reason = f"Score {score}/10 + Pattern {matched}/{total} 双 confirm"
    elif score >= 6 and is_ai and heat in ("🔥🔥🔥",) and risk_count == 0:
        buy_qualified = True
        buy_reason = f"AI 核心板块 + Score {score}/10 + 无风险旗"
    elif matched >= 4 and risk_count <= 1 and not is_cold_sector and score >= 5:
        buy_qualified = True
        buy_reason = f"Pattern {matched}/{total} 强 + 风险 controlled"

    if buy_qualified:
        ladder = _compute_ladder(cur_price, target_price, p_low, p_high)
        return {
            "tag": "BUY",
            "emoji": "🏆",
            "headline": f"BUY · {best.get('name', '')} ({matched}/{total})",
            "reason": buy_reason,
            "close_to_buy": close_to_buy,
            "ladder": ladder,
        }

    # ── WATCH rules ────────────────────────────────────────────────────
    # WATCH conditions (any one triggers):
    #   1. Score 5+ AND pattern 2+ AND risk ≤ 2
    #   2. Strong pattern 4+ but COLD sector → downgrade from BUY to WATCH
    #   3. Whale check ≥ $2M AND pattern 3+ AND risk ≤ 2 (even if low score)
    #   4. Score 4 with pattern 4+ and no major fundamental collapse
    if score >= 5 and matched >= 2 and risk_count <= 2:
        reason = f"Score {score}/10 + {matched}/{total} pattern"
        return {
            "tag": "WATCH", "emoji": "👀",
            "headline": f"WATCH · 部分 confirm ({matched}/{total})",
            "reason": reason + "; 等更多 confirm 或更深回调",
            "close_to_buy": close_to_buy, "ladder": None,
        }

    if matched >= 4 and is_cold_sector and risk_count <= 2:
        return {
            "tag": "WATCH", "emoji": "👀",
            "headline": f"WATCH · 强 pattern 但冷板块",
            "reason": f"Pattern {matched}/{total} 但 {bucket} 是逆风板块",
            "close_to_buy": close_to_buy, "ladder": None,
        }

    if total_value >= 2_000_000 and matched >= 3 and risk_count <= 2:
        return {
            "tag": "WATCH", "emoji": "👀",
            "headline": f"WATCH · Whale check ${total_value/1e6:.1f}M",
            "reason": f"大额 ${total_value/1e6:.1f}M 买入 + Pattern {matched}/{total}; 但 Score 偏低",
            "close_to_buy": close_to_buy, "ladder": None,
        }

    # ── SKIP (default) ─────────────────────────────────────────────────
    return {
        "tag": "SKIP",
        "emoji": "⏭️",
        "headline": "SKIP · 信号不足",
        "reason": f"Score {score}/10 + Pattern {matched}/{total} 都不够强",
        "close_to_buy": close_to_buy,
        "ladder": None,
    }
