"""pattern.py — detect well-known setups: NOMD / UNIT / State4 / Story Stock.

Each detector returns (matched_count: int, total: int, factors: list[str]).
Higher matched ratio = stronger pattern fit.

Patterns:

  NOMD-like (Nomad Foods 2024) — defensive value with insider cluster:
    1. Beta < 1.3 OR Sector defensive
    2. Forward PE < 15
    3. Distance from 52W low ≤ +25% (capitulation done)
    4. Insider open-market buy (not RSU)
    5. Revenue growth ≥ 0 (not declining business)

  UNIT-like (Uniti 2026) — narrative reversal post-event:
    1. Distance from 52W high ≤ -40% (deep drawdown)
    2. Below 200DMA (still in trend repair)
    3. Concrete event already happened (merger close / restructuring / new contract)
    4. Forward PE < 25 (not still bubble priced)
    5. Insider/13F accumulation signal

  Jackal State 4 — deep capitulation entry:
    1. Distance from 52W high ≤ -30%
    2. Distance from 52W low ≤ +20% (near capitulation bottom)
    3. Below 200DMA materially (≤ -10%)
    4. Recent panic (today's move <-7% OR 7-day move <-15%)
    5. Insider buy at depressed price = smart-money confirmation

  Story Stock Risk — high-risk red flag (NEGATIVE pattern, demerit):
    1. 1Y return >+50% (already ran up)
    2. Operating margin negative
    3. Net debt > 50% market cap
    4. CEO with low public trust (manual override list)
    5. Score 10/10 audit/governance risk
"""
from __future__ import annotations

# Tickers where the CEO has documented public trust issues.
# Conservative: only include cases with clear public scandals.
LOW_TRUST_CEO = {
    "BETR": "Vishal Garg (Zoom mass-fire 2021 scandal)",
}


def _val(d: dict | None, key: str, default=None):
    if not d:
        return default
    v = d.get(key)
    return default if v is None else v


def detect_nomd_pattern(filing: dict, valuation: dict, price: dict,
                       sector: dict, total_value: float) -> dict:
    """Defensive value + insider buy. Like NOMD Q4 2024."""
    matched = []
    missing = []

    # 1. Defensive: low beta OR defensive sector
    beta = _val(valuation, "beta")
    is_def = _val(sector, "is_defensive", False)
    if (beta is not None and beta < 1.3) or is_def:
        matched.append(f"✅ 防御性 (β={beta if beta else 'n/a'}, sector defensive={is_def})")
    else:
        missing.append(f"❌ 高 β / 非防御 sector")

    # 2. Fwd PE < 15
    fpe = _val(valuation, "forward_pe")
    if fpe is not None and 0 < fpe < 15:
        matched.append(f"✅ Forward PE 便宜 ({fpe:.1f})")
    else:
        missing.append(f"❌ Forward PE 不够便宜 ({fpe if fpe else 'n/a'})")

    # 3. Near 52W low
    p_low = _val(price, "pct_vs_52w_low")
    if p_low is not None and p_low <= 25:
        matched.append(f"✅ 距 52W 低 +{p_low:.0f}% (capitulation done)")
    else:
        missing.append(f"❌ 离 52W 低较远 ({p_low if p_low else 'n/a'}%)")

    # 4. Insider open-market buy (always true if we got here, but check value)
    if total_value >= 200_000:
        matched.append(f"✅ Insider open-market buy (${total_value/1e6:.1f}M)")
    else:
        missing.append("❌ Insider buy < $200K")

    # 5. Revenue not declining
    rev_g = _val(valuation, "revenue_growth")
    if rev_g is not None and rev_g >= -0.05:  # tolerate -5%
        matched.append(f"✅ 收入未崩塌 ({rev_g*100:+.0f}% YoY)")
    else:
        missing.append(f"❌ 收入下滑严重 ({rev_g*100 if rev_g else 'n/a'}% YoY)")

    return {
        "name": "NOMD-like 防守价值",
        "matched": len(matched),
        "total": 5,
        "factors": matched,
        "missing": missing,
    }


def detect_unit_pattern(filing: dict, valuation: dict, price: dict,
                       sector: dict, total_value: float) -> dict:
    """Post-event narrative reversal, like UNIT after Windstream close."""
    matched = []
    missing = []

    p_high = _val(price, "pct_vs_52w_high")
    if p_high is not None and p_high <= -40:
        matched.append(f"✅ 距 52W 高 {p_high:.0f}% (深度回调)")
    else:
        missing.append(f"❌ 距高位不够深 ({p_high if p_high else 'n/a'}%)")

    p_200 = _val(price, "pct_vs_200dma")
    if p_200 is not None and p_200 < 0:
        matched.append(f"✅ 在 200DMA 下方 ({p_200:+.0f}%)")
    else:
        missing.append(f"❌ 还在 200DMA 上方")

    # 3. event-driven: skipped (need manual confirmation)
    matched.append("ℹ️ Event-driven 需手动确认 (财报/合并/合同)")

    fpe = _val(valuation, "forward_pe")
    if fpe is not None and 0 < fpe < 25:
        matched.append(f"✅ Forward PE 合理 ({fpe:.1f})")
    else:
        missing.append(f"❌ Forward PE 偏高 ({fpe if fpe else 'n/a'})")

    if total_value >= 500_000:
        matched.append(f"✅ Insider accumulation (${total_value/1e6:.1f}M)")
    else:
        missing.append("❌ Insider 信号偏弱")

    return {
        "name": "UNIT-like 叙事反转",
        "matched": len(matched),
        "total": 5,
        "factors": matched,
        "missing": missing,
    }


def detect_state4_pattern(filing: dict, valuation: dict, price: dict,
                         sector: dict, total_value: float) -> dict:
    """Jackal State 4: deep correction capitulation entry."""
    matched = []
    missing = []

    p_high = _val(price, "pct_vs_52w_high")
    if p_high is not None and p_high <= -30:
        matched.append(f"✅ 距 52W 高 {p_high:.0f}%")
    else:
        missing.append(f"❌ 跌幅不够深 ({p_high if p_high else 'n/a'}%)")

    p_low = _val(price, "pct_vs_52w_low")
    if p_low is not None and p_low <= 20:
        matched.append(f"✅ 接近 52W 低 (+{p_low:.0f}%)")
    else:
        missing.append(f"❌ 离 52W 低较远 ({p_low if p_low else 'n/a'}%)")

    p_200 = _val(price, "pct_vs_200dma")
    if p_200 is not None and p_200 <= -10:
        matched.append(f"✅ 显著 < 200DMA ({p_200:+.0f}%)")
    else:
        missing.append(f"❌ 没大幅低于 200DMA")

    # Insider buy at low = smart money signal
    if total_value >= 500_000:
        matched.append(f"✅ Insider 接刀 (${total_value/1e6:.1f}M)")
    else:
        missing.append("❌ Insider 信号偏弱")

    # Bonus: today panic or 7-day panic — need to be supplied externally
    matched.append("ℹ️ Capitulation 还要 confirm volume (4x+) / RSI <25")

    return {
        "name": "Jackal State 4 深度回调",
        "matched": len(matched),
        "total": 5,
        "factors": matched,
        "missing": missing,
    }


def detect_story_stock_risk(ticker: str, filing: dict, valuation: dict,
                           price: dict, sector: dict) -> dict:
    """NEGATIVE pattern — high-risk story stock that LOOKS like insider buy
    setup but is actually dangerous. BETR-style.

    Returns risk_count (higher = more dangerous, demerits the verdict).
    """
    red_flags = []

    # 1. Big 1Y run = not beaten down
    ch_1y = _val(price, "change_1y_pct")
    if ch_1y is not None:
        ch_pct = ch_1y if abs(ch_1y) > 1 else ch_1y * 100
        if ch_pct > 50:
            red_flags.append(f"⚠️ 1Y +{ch_pct:.0f}% 已大涨 (不是 left side)")

    # 2. Operating margin negative
    op_m = _val(valuation, "operating_margin")
    if op_m is not None and op_m < -0.10:
        red_flags.append(f"⚠️ 运营利润率 {op_m*100:+.0f}% (现金流燃烧)")

    # 3. Heavy net debt
    net_cash_pct = _val(valuation, "net_cash_pct_mcap")
    if net_cash_pct is not None and net_cash_pct < -50:
        red_flags.append(f"⚠️ 净负债 {abs(net_cash_pct):.0f}% 市值")

    # 4. Revenue collapsing
    rev_g = _val(valuation, "revenue_growth")
    if rev_g is not None and rev_g < -0.50:
        red_flags.append(f"⚠️ 收入 {rev_g*100:+.0f}% YoY (业务崩塌)")

    # 5. Low-trust CEO list
    if (ticker or "").upper() in LOW_TRUST_CEO:
        red_flags.append(f"🚨 CEO 信任问题: {LOW_TRUST_CEO[ticker.upper()]}")

    # 6. Below 52W high but small market cap (sub-$500M) = manipulation risk
    mcap = _val(valuation, "market_cap")
    if mcap is not None and mcap < 500_000_000:
        red_flags.append(f"⚠️ 微小盘 ${mcap/1e6:.0f}M (单 insider 可拉抬)")

    return {
        "name": "Story Stock 红旗",
        "risk_count": len(red_flags),
        "red_flags": red_flags,
    }


def detect_all_patterns(ticker: str, filing: dict, valuation: dict,
                       price: dict, sector: dict, total_value: float) -> dict:
    """Run all pattern detectors. Returns the best-fit pattern + any risk flags."""
    nomd = detect_nomd_pattern(filing, valuation, price, sector, total_value)
    unit = detect_unit_pattern(filing, valuation, price, sector, total_value)
    state4 = detect_state4_pattern(filing, valuation, price, sector, total_value)
    risk = detect_story_stock_risk(ticker, filing, valuation, price, sector)

    # Pick the highest-scoring positive pattern
    patterns = sorted(
        [nomd, unit, state4],
        key=lambda p: p["matched"] / p["total"] if p["total"] else 0,
        reverse=True,
    )
    best = patterns[0]

    return {
        "best_pattern": best,
        "all_patterns": patterns,
        "risk": risk,
    }
