#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis.py — "Should I invest?" scoring for a strategic-partner signal.

战略合作信号的 "该不该投" 评分脚本.

═══════════════════════════════════════════════════════════════════════
  COMPANION TO: insider-firehose/scripts/enrichment/score.py
═══════════════════════════════════════════════════════════════════════

我们已经有 insider buying 的评分系统 (Smart Money Score 0-10).
这个脚本是它的姐妹版 —— 给 strategic-partner 信号一个 0-10 评分.

We already have a Smart Money Score (0-10) for insider buying.
This script is its sibling — scores 0-10 for strategic-partner signals.

When BOTH signals fire on the same ticker within 30 days = MEGA SIGNAL.
当两个信号在同一 ticker 30 天内都触发 = 巨型信号.

═══════════════════════════════════════════════════════════════════════
  RUBRIC / 评分标准
═══════════════════════════════════════════════════════════════════════

Score = clamp(0, 10, sum of):

  INVESTOR QUALITY (max 4):
    +3   Tier-1 strategic (NVIDIA, MSFT, SK Telecom, Samsung, TSMC)
    +2   Sovereign or Tier-2 (MGX, PIF, Intel Capital, Qualcomm)
    +1   Smart-money VC (a16z, Sequoia, Founders Fund)
    +2   BONUS: multiple Tier-1 investors in same deal (cluster)

  DEAL SIZE (max 3):
    +1   ≥ $50M
    +2   ≥ $200M (like PENG)
    +3   ≥ $1B (like CRWV OpenAI)
    Bonus: +1 if deal ≥ 10% of current market cap (meaningful dilution)

  STRUCTURE QUALITY (max 2):
    +1   PIPE Preferred with conversion premium (long-term commitment)
    +1   Joint Development / Master Supply Agreement (real revenue)
    -1   13G only (passive, no strategic intent)

  PRICE / TIMING (max 2):
    +1   Stock below 200DMA (buying weakness, contrarian setup)
    +1   Stock within 30% of 52W low (deep value entry)
    -1   Stock at ATH (chase risk)

═══════════════════════════════════════════════════════════════════════
  USAGE / 使用方法
═══════════════════════════════════════════════════════════════════════

Programmatic:
    from analysis import compute_partner_score
    result = compute_partner_score(signal, valuation, price)
    # result = {"score": 8, "factors": [...], "verdict": "STRONG BUY"}

CLI:
    python analysis.py TICKER --amount 200 --tier tier_1 --type pipe_preferred
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional


# ─── Score weights / 评分权重 ────────────────────────────────────────────

_TIER_BASE_POINTS: dict[str, int] = {
    "tier_1": 3,
    "sovereign": 2,
    "tier_2": 2,
    "smart_vc": 1,
}

# Verdict labels by score range
# 评分对应的判断
_VERDICT_LABELS: list[tuple[int, str]] = [
    (9, "🔥🔥🔥 EXCEPTIONAL — Founder-CEO level signal"),
    (7, "⭐⭐⭐ STRONG BUY — Tier-1 + meaningful size"),
    (5, "⭐⭐ WATCH — Real signal, but caveats present"),
    (3, "⭐ MODEST — Some signal, mostly priced in"),
    (0, "▫️ WEAK — Likely noise or already extended"),
]


def _verdict_for(score: int) -> str:
    """Map a 0-10 score to a verdict label. / 把 0-10 评分映射成判断."""
    for threshold, label in _VERDICT_LABELS:
        if score >= threshold:
            return label
    return "▫️ WEAK"


def _investor_score(investors: list[tuple[str, str]]) -> tuple[int, list[str]]:
    """
    Score investor quality (max 4 + 2 cluster bonus).
    给投资人质量打分 (最多 4 + 2 cluster bonus).

    Returns (points, factor_descriptions).
    """
    if not investors:
        return (0, [])

    points = 0
    factors = []
    tiers_seen: list[str] = []

    # Take the BEST tier as base, then check for cluster bonus
    # 取最高 tier 作为 base, 再检查 cluster bonus
    for tier, name in investors:
        tiers_seen.append(tier)

    # Best-tier base points
    if "tier_1" in tiers_seen:
        points += 3
        factors.append("✅ Tier-1 strategic investor")
    elif "sovereign" in tiers_seen:
        points += 2
        factors.append("✅ Sovereign wealth fund investor")
    elif "tier_2" in tiers_seen:
        points += 2
        factors.append("✅ Tier-2 strategic investor")
    elif "smart_vc" in tiers_seen:
        points += 1
        factors.append("✅ Smart-money VC participant")

    # Cluster bonus: 2+ tier-1 investors in same deal
    # Cluster 加分: 同笔交易 2+ tier-1 投资人
    tier_1_count = tiers_seen.count("tier_1")
    if tier_1_count >= 2:
        points += 2
        factors.append(f"✅✅ CLUSTER: {tier_1_count} Tier-1 investors")

    return (points, factors)


# v2.5: TAM-misparse guardrail threshold.
# A real PIPE / strategic-investment / 13D stake amount cannot plausibly
# exceed a company's market cap by a large multiple. When "deal" ≥ this %
# of mcap, the amount is almost always a market-size / TAM figure scraped
# from an investor deck (e.g. GHM "$90B radar market" → parsed as a "$90B
# deal" = 6856% of a $1.3B mcap). Such signals are suppressed.
TAM_MISPARSE_PCT_OF_MCAP = 500.0  # 5x mcap = impossible for a financing/stake


def _amount_score(
    amount_usd_m: float, market_cap_usd: Optional[float],
) -> tuple[int, list[str]]:
    """
    Score deal size, both absolute + relative to mcap. Max 3 + 1 dilution bonus.
    交易金额评分 — 绝对值 + 相对市值. 最多 3 + 1 稀释加分.
    """
    points = 0
    factors = []

    # Absolute size
    if amount_usd_m >= 1000:
        points += 3
        factors.append(f"✅ Whale deal (${amount_usd_m/1000:.1f}B)")
    elif amount_usd_m >= 200:
        points += 2
        factors.append(f"✅ Large deal (${amount_usd_m:.0f}M)")
    elif amount_usd_m >= 50:
        points += 1
        factors.append(f"✅ Meaningful deal (${amount_usd_m:.0f}M)")

    # Relative to market cap (dilution bonus)
    # 相对市值 (稀释 bonus)
    if market_cap_usd and market_cap_usd > 0:
        pct_of_mcap = (amount_usd_m * 1e6) / market_cap_usd * 100
        if pct_of_mcap >= 10:
            points += 1
            factors.append(f"✅ Deal = {pct_of_mcap:.0f}% of mcap (high commitment)")

    return (points, factors)


def _structure_score(
    deal_type: str, conversion_price: Optional[float],
    current_price: Optional[float], form_type: str,
) -> tuple[int, list[str]]:
    """
    Score deal structure quality. Max 2, with -1 for pure passive.
    交易结构评分. 最多 2, 纯 passive -1.
    """
    points = 0
    factors = []

    # PIPE Preferred with conversion premium = long-term commitment
    # PIPE preferred + 转换溢价 = 长期承诺
    if "preferred" in deal_type.lower() and conversion_price and current_price:
        premium = (conversion_price / current_price - 1) * 100
        if premium > 20:
            points += 1
            factors.append(
                f"✅ Conversion premium {premium:+.0f}% (long-term believer)"
            )

    # Joint development / supply agreements = real revenue path
    if any(kw in deal_type.lower() for kw in [
        "joint development", "master supply", "supply agreement",
        "strategic partnership",
    ]):
        points += 1
        factors.append("✅ Operating agreement (revenue path)")

    # 13G filers are usually passive index funds — downgrade signal
    # 13G 通常是被动 index fund — 降权
    if form_type == "SC 13G":
        points -= 1
        factors.append("⚠️ Passive 13G filing (no active intent)")

    return (points, factors)


def _price_score(
    current_price: Optional[float],
    ma_200: Optional[float],
    high_52w: Optional[float],
    low_52w: Optional[float],
) -> tuple[int, list[str]]:
    """
    Score timing relative to price action. Max 2, -1 for ATH chase.
    时机评分. 最多 2, ATH 追高 -1.
    """
    points = 0
    factors = []

    if current_price is None:
        return (0, [])

    # Below 200DMA = contrarian / buying weakness
    if ma_200 and current_price < ma_200:
        points += 1
        factors.append(
            f"✅ Below 200DMA ({(current_price/ma_200 - 1)*100:+.0f}%) — contrarian"
        )

    # Within 30% of 52W low = deep value entry
    if low_52w and current_price <= low_52w * 1.30:
        pct = (current_price / low_52w - 1) * 100
        points += 1
        factors.append(f"✅ Near 52W low (+{pct:.0f}%) — deep value")

    # Within 5% of ATH = chase risk
    if high_52w and current_price >= high_52w * 0.95:
        points -= 1
        factors.append(
            f"⚠️ Near 52W high ({(current_price/high_52w - 1)*100:+.0f}%) — chase risk"
        )

    return (points, factors)


def compute_partner_score(
    signal: dict,
    valuation: Optional[dict] = None,
    price: Optional[dict] = None,
) -> dict:
    """
    Compute the 0-10 Strategic Partner Score.
    计算 0-10 战略合作伙伴评分.

    Args:
        signal: dict from parsers.py with keys:
            - investors: list of (tier, canonical) tuples
            - amount_usd_m: float (millions USD)
            - deal_type: str
            - conversion_price: Optional[float]
            - form_type: str ("8-K" or "SC 13D"/"SC 13G")
        valuation: dict from enrichment/valuation.py (optional)
            - market_cap: Optional[float]
        price: dict from enrichment/price_action.py (optional)
            - current, ma_200, high_52w, low_52w

    Returns:
        {
            "score": int 0-10,
            "raw": int (pre-clamp),
            "factors": list[str] of triggered factors,
            "verdict": str,
        }
    """
    valuation = valuation or {}
    price = price or {}

    # Sub-scores
    inv_pts, inv_factors = _investor_score(signal.get("investors", []))
    amt_pts, amt_factors = _amount_score(
        signal.get("amount_usd_m", 0.0),
        valuation.get("market_cap"),
    )
    str_pts, str_factors = _structure_score(
        signal.get("deal_type", "Unknown"),
        signal.get("conversion_price"),
        price.get("current"),
        signal.get("form_type", "8-K"),
    )
    prc_pts, prc_factors = _price_score(
        price.get("current"),
        price.get("ma_200"),
        price.get("high_52w"),
        price.get("low_52w"),
    )

    # ── TAM-misparse guardrail (v2.5) ──────────────────────────────────
    # If the parsed "deal" is an implausible multiple of market cap, it is
    # almost certainly a TAM/market-size number lifted from an investor deck
    # (not a real financing/stake). Strip its points and flag for suppression.
    suppress = False
    suppress_reason = ""
    _mcap = valuation.get("market_cap")
    _amt_m = signal.get("amount_usd_m", 0.0) or 0.0
    if _mcap and _mcap > 0 and _amt_m > 0:
        _pct_mcap = (_amt_m * 1e6) / _mcap * 100
        if _pct_mcap >= TAM_MISPARSE_PCT_OF_MCAP:
            suppress = True
            suppress_reason = (
                f"deal=${_amt_m/1000:.0f}B = {_pct_mcap:.0f}% of mcap "
                f"→ implausible, likely TAM/market-size misparse"
            )
            amt_pts = 0
            amt_factors = [f"🚫 SUPPRESSED: {suppress_reason}"]

    raw = inv_pts + amt_pts + str_pts + prc_pts
    score = max(0, min(10, raw))

    factors = inv_factors + amt_factors + str_factors + prc_factors

    return {
        "score": score,
        "raw": raw,
        "factors": factors,
        "verdict": _verdict_for(score),
        "suppress": suppress,
        "suppress_reason": suppress_reason,
    }


# ─── CLI / 命令行 ────────────────────────────────────────────────────────

def main() -> int:
    """CLI entry for one-off scoring. / 单次评分的命令行入口."""
    ap = argparse.ArgumentParser(
        description="Score a strategic-partner signal (companion to insider_ratio.py)"
    )
    ap.add_argument("ticker", help="Issuer ticker, e.g. PENG")
    ap.add_argument("--amount", type=float, required=True,
                    help="Deal amount in USD millions, e.g. 200")
    ap.add_argument("--tier", default="tier_1",
                    choices=["tier_1", "tier_2", "sovereign", "smart_vc"],
                    help="Investor tier")
    ap.add_argument("--investor", default="UnknownInvestor",
                    help="Investor name (for display)")
    ap.add_argument("--type", default="PIPE (Preferred)",
                    help="Deal type")
    ap.add_argument("--conversion-price", type=float, default=None,
                    help="Conversion price for PIPE (optional)")
    ap.add_argument("--no-enrich", action="store_true",
                    help="Skip yfinance enrichment (faster, less accurate)")
    args = ap.parse_args()

    signal = {
        "investors": [(args.tier, args.investor)],
        "amount_usd_m": args.amount,
        "deal_type": args.type,
        "conversion_price": args.conversion_price,
        "form_type": "8-K",
    }

    valuation = {}
    price = {}

    if not args.no_enrich:
        # Try to pull enrichment from sibling skill
        # 尝试从姐妹 skill 调用 enrichment
        try:
            import sys as _sys
            from pathlib import Path as _Path
            insider_scripts = (_Path(__file__).resolve().parent.parent.parent /
                              "insider-firehose" / "scripts")
            if insider_scripts.exists():
                _sys.path.insert(0, str(insider_scripts))
                from enrichment.valuation import pull_valuation  # type: ignore
                from enrichment.price_action import pull_price_action  # type: ignore
                valuation = pull_valuation(args.ticker)
                price = pull_price_action(args.ticker)
        except Exception as e:
            print(f"[WARN] enrichment failed: {e}", file=sys.stderr)

    result = compute_partner_score(signal, valuation, price)

    print(f"\n{'═' * 60}")
    print(f"  Strategic Partner Score for {args.ticker}")
    print(f"{'═' * 60}")
    print(f"\n  Score: {result['score']}/10  (raw: {result['raw']})")
    print(f"  Verdict: {result['verdict']}\n")
    print(f"  Factors:")
    for f in result["factors"]:
        print(f"    {f}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
