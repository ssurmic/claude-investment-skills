"""format.py — render the v3 enriched Telegram message.

v3 redesign (May 2026):
  - VERDICT at top (BUY/WATCH/AVOID/SKIP) — one-glance answer to "该不该买"
  - Business description (公司是干什么的) — plain Chinese
  - Sector heat tag (🔥🔥🔥 / ❄️ / ➖) — AI focus
  - Insider buy detail with close-to-cost-basis flag (谁买了多少 / close to buy?)
  - Valuation block: PEG, Forward PE, distance from 52W low, upper resistance
  - Pattern match (NOMD/UNIT/State4) with confidence ratio
  - Entry ladder (if BUY): T1/T2/T3/stop/target/RR
  - Risk flags (red flags from story-stock detector)

Output is Telegram Markdown. Target ≤2500 chars even with all sections.
"""
from __future__ import annotations


# ─── Formatters ────────────────────────────────────────────────────────
def _fmt_money(v: float | int | None) -> str:
    if v is None:
        return "—"
    sign = "-" if v < 0 else ""
    av = abs(v)
    if av >= 1e9:
        return f"{sign}${av/1e9:.1f}B"
    if av >= 1e6:
        return f"{sign}${av/1e6:.0f}M"
    if av >= 1e3:
        return f"{sign}${av/1e3:.0f}K"
    return f"{sign}${av:.0f}"


def _fmt_pct(v, plus=False):
    if v is None:
        return "—"
    return f"{v:+.1f}%" if plus else f"{v:.1f}%"


def _fmt_pe(v):
    if v is None:
        return "—"
    if v < 0:
        return "亏损"
    if v > 999:
        return ">999"
    return f"{v:.1f}"


def _verdict_emoji(tag: str) -> str:
    return {
        "BUY":   "🏆🟢",
        "WATCH": "👀🟡",
        "AVOID": "❌🔴",
        "SKIP":  "⏭️ ⚪",
    }.get(tag, "❓")


# ─── Main renderer ─────────────────────────────────────────────────────
def render_enriched(basic_msg: str, enriched: dict) -> str:
    """v3 format: verdict at top, structured sections below.

    `enriched` may include: company, valuation, price, score, sector, patterns,
    verdict, filing. Any missing key → graceful skip.
    """
    if not enriched:
        return basic_msg

    company   = enriched.get("company") or {}
    valuation = enriched.get("valuation") or {}
    price     = enriched.get("price") or {}
    score     = enriched.get("score") or {}
    sector    = enriched.get("sector") or {}
    patterns  = enriched.get("patterns") or {}
    verdict   = enriched.get("verdict") or {}
    filing    = enriched.get("filing") or {}

    parts = []

    # ── 1. VERDICT (top-most, biggest signal) ─────────────────────────
    if verdict and verdict.get("tag"):
        tag = verdict["tag"]
        emoji = _verdict_emoji(tag)
        parts.append(f"{emoji} *{verdict.get('headline', tag)}*\n_{verdict.get('reason', '')}_\n\n")

    # ── 2. Original basic message (header with ticker/insider) ────────
    parts.append(basic_msg)

    # ── 3. 公司是干什么的 ────────────────────────────────────────────
    if company.get("one_liner"):
        sec_str = company.get("sector") or ""
        ind_str = company.get("industry") or ""
        ctx = f" · {sec_str}" if sec_str else ""
        if ind_str and ind_str != sec_str:
            ctx += f" / {ind_str}"
        parts.append(f"\n🏢 *公司业务*\n_{company['one_liner']}_{ctx}")

    # ── 4. Sector heat (HOT/COLD with rationale) ──────────────────────
    if sector and sector.get("heat"):
        heat = sector["heat"]
        bucket = sector.get("bucket", "")
        rationale = sector.get("rationale", "")
        is_ai = sector.get("is_ai")
        is_def = sector.get("is_defensive")
        ai_tag = " · AI 主线" if is_ai else ""
        def_tag = " · 防守" if is_def else ""
        parts.append(f"\n{heat} *{bucket}*{ai_tag}{def_tag}\n_{rationale}_")

    # ── 5. Insider buy detail (谁买了多少 / close to buy?) ───────────
    cur_price = price.get("current") if price else None
    buy_price = filing.get("price_per_share") if filing else None
    close_to_buy_tag = ""
    if cur_price and buy_price and buy_price > 0:
        diff_pct = (cur_price - buy_price) / buy_price * 100
        if abs(diff_pct) <= 8:
            close_to_buy_tag = f"  🟢 close-to-cost (现价比 insider {diff_pct:+.1f}%)"
        elif diff_pct > 8:
            close_to_buy_tag = f"  ⚠️ 已偏离 (现价比 insider +{diff_pct:.1f}%)"
        else:
            close_to_buy_tag = f"  🔥 仍在 insider 下方 ({diff_pct:+.1f}%)"
    if close_to_buy_tag:
        parts.append(f"\n💰 *Insider 入场判断*{close_to_buy_tag}")

    # ── 6. Valuation (PEG + 52W 位置 + 上方阻力) ─────────────────────
    if valuation:
        v = ["\n📈 *账面分析*"]
        mcap = valuation.get("market_cap")
        if mcap is not None:
            v.append(f"  • 市值: {_fmt_money(mcap)}")
        tpe = valuation.get("trailing_pe")
        fpe = valuation.get("forward_pe")
        peg = valuation.get("peg")
        pe_line = f"  • PE: {_fmt_pe(tpe)} (Fwd {_fmt_pe(fpe)})"
        if peg is not None:
            peg_tag = " 🟢 cheap" if peg < 1 else " ⚠️ 偏贵" if peg > 2 else ""
            pe_line += f" · *PEG {peg}*{peg_tag}"
        v.append(pe_line)
        rev_g = valuation.get("revenue_growth")
        if rev_g is not None:
            rev_tag = " ✅" if rev_g > 0.05 else " ⚠️" if rev_g < -0.05 else ""
            v.append(f"  • 收入增长: {rev_g*100:+.1f}% YoY{rev_tag}")
        net_pct = valuation.get("net_cash_pct_mcap")
        if net_pct is not None:
            if net_pct < -30:
                v.append(f"  • ⚠️ 净负债 {abs(net_pct):.0f}% 市值")
            elif net_pct > 20:
                v.append(f"  • ✅ 净现金 {net_pct:.0f}% 市值")
        div = valuation.get("dividend_yield")
        if div is not None and div > 0:
            v.append(f"  • Div yield: {div*100:.2f}%")
        if len(v) > 1:
            parts.append("\n".join(v))

    # ── 7. Price action (52W 距离 + MA + analyst target) ─────────────
    if price:
        p = ["\n📊 *价格 & 关键位*"]
        cur = price.get("current")
        if cur is not None:
            p.append(f"  • 现价: ${cur:.2f}")
        ch_1y = price.get("change_1y_pct")
        if ch_1y is not None:
            ch_pct = ch_1y if abs(ch_1y) > 1 else ch_1y * 100
            tag = " ⚠️" if ch_pct > 50 else ""
            p.append(f"  • 1Y: {ch_pct:+.1f}%{tag}")
        h = price.get("pct_vs_52w_high")
        l = price.get("pct_vs_52w_low")
        if h is not None and l is not None:
            l_tag = " 🟢" if l <= 15 else ""
            p.append(f"  • 52W: 距低 +{l:.0f}%{l_tag} · 距高 {h:.0f}%")
        m50 = price.get("pct_vs_50dma")
        m200 = price.get("pct_vs_200dma")
        if m50 is not None or m200 is not None:
            p.append(
                f"  • vs MA: 50d {_fmt_pct(m50, plus=True)} · "
                f"200d {_fmt_pct(m200, plus=True)}"
            )
        # ── 上方阻力 / 下方支撑 ──
        target_med = valuation.get("analyst_target") if valuation else None
        target_high = valuation.get("analyst_target_high") if valuation else None
        if target_med and cur:
            upside_pct = (target_med - cur) / cur * 100
            p.append(f"  • 🔴 上方目标价: ${target_med:.2f} (分析师中值, +{upside_pct:.0f}%)")
        if target_high and cur and target_high != target_med:
            p.append(f"  • 🔴 高位目标: ${target_high:.2f}")
        if len(p) > 1:
            parts.append("\n".join(p))

    # ── 8. Smart Money Score (concise) ────────────────────────────────
    if score and score.get("score") is not None:
        s_val = score["score"]
        emoji = "🔥🔥🔥" if s_val >= 9 else "⭐⭐⭐" if s_val >= 7 else "⭐⭐" if s_val >= 5 else "⭐" if s_val >= 3 else "▫️"
        factors = score.get("factors") or []
        s_block = [f"\n{emoji} *Smart Money Score: {s_val}/10*"]
        for f in factors[:5]:
            s_block.append(f"  {f}")
        parts.append("\n".join(s_block))

    # ── 9. Pattern match ──────────────────────────────────────────────
    best_pat = patterns.get("best_pattern") if patterns else None
    if best_pat:
        name = best_pat.get("name", "")
        m = best_pat.get("matched", 0)
        t = best_pat.get("total", 5)
        ratio_tag = " ✅" if m >= 4 else " 🟡" if m >= 2 else " ❌"
        p_block = [f"\n🎯 *Pattern: {name} ({m}/{t}){ratio_tag}*"]
        for f in (best_pat.get("factors") or [])[:5]:
            p_block.append(f"  {f}")
        parts.append("\n".join(p_block))

    # ── 10. Risk flags ────────────────────────────────────────────────
    risk = patterns.get("risk") if patterns else None
    if risk and risk.get("red_flags"):
        rb = ["\n🚨 *红旗 / 风险信号*"]
        for f in risk["red_flags"][:5]:
            rb.append(f"  {f}")
        parts.append("\n".join(rb))

    # ── 11. Entry ladder (if BUY) ─────────────────────────────────────
    ladder = verdict.get("ladder") if verdict else None
    if ladder and ladder.get("t1"):
        lb = ["\n🎯 *入场计划 (50/30/20)*"]
        lb.append(f"  • T1 (50%): ${ladder['t1']}")
        lb.append(f"  • T2 (30%): ${ladder['t2']}")
        lb.append(f"  • T3 (20%): ${ladder['t3']}")
        lb.append(f"  • Stop: ${ladder['stop']} · Target: ${ladder['target']}")
        if ladder.get("rr"):
            lb.append(f"  • Avg cost ${ladder['avg_cost']} · R/R {ladder['rr']}:1 (+{ladder['upside_pct']:.0f}%)")
        parts.append("\n".join(lb))

    return "".join(parts)
