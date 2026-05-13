"""
format_alert.py — Render a FilingDiff into a Telegram-friendly Markdown message.

Style matches the existing firehoses (insider-firehose, strategic-partner):
    🔔 emoji header
    Fund name + manager + period
    AUM change
    NEW positions (top 5)
    ADDED positions (top 5)
    CLOSED positions (top 3)
    Top 10 holdings table

Markdown is escaped per Telegram's "Markdown" mode (not MarkdownV2):
    Underscores in tickers/CUSIPs are fine; only `*`, `_`, `[` need watching.
"""

from __future__ import annotations

from diff import FilingDiff, PositionChange
from fund_registry import Fund


def _fmt_money(v: float) -> str:
    """Format USD as $1.2M / $345K / $4.5B."""
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def _fmt_pct(p: float) -> str:
    if p == float("inf"):
        return "NEW"
    return f"{p*100:+.0f}%"


def _line_new(c: PositionChange) -> str:
    opt = f" `[{c.put_call.upper()}]`" if c.put_call else ""
    return f"  • *{c.issuer[:30]}*{opt} — {_fmt_money(c.new_value)}"


def _line_added(c: PositionChange) -> str:
    opt = f" `[{c.put_call.upper()}]`" if c.put_call else ""
    pct = _fmt_pct(c.share_change_pct)
    return (f"  • *{c.issuer[:30]}*{opt}  "
            f"{_fmt_money(c.prior_value)} → {_fmt_money(c.new_value)} ({pct})")


def _line_closed(c: PositionChange) -> str:
    opt = f" `[{c.put_call.upper()}]`" if c.put_call else ""
    return f"  • *{c.issuer[:30]}*{opt} — was {_fmt_money(c.prior_value)}"


def _line_top(c: PositionChange, aum: float) -> str:
    opt = f" `[{c.put_call.upper()}]`" if c.put_call else ""
    pct = (c.new_value / aum * 100) if aum > 0 else 0
    return f"  {pct:>4.1f}%  *{c.issuer[:32]}*{opt}  {_fmt_money(c.new_value)}"


def render_alert(diff: FilingDiff, fund: Fund, edgar_url: str) -> str:
    """Render a Telegram-ready Markdown message for a new 13F filing."""
    aum_change_str = ""
    if diff.aum_prior > 0:
        aum_change_str = f" ({_fmt_pct(diff.aum_change_pct)})"

    lines = [
        f"🔔 *13F: {fund.name}*  `{fund.tag}`",
        f"_{fund.manager}_",
        f"📅 Period: *{diff.period_new}*  (vs {diff.period_prior})",
        f"💼 AUM: *{_fmt_money(diff.aum_new)}*{aum_change_str}",
        "",
    ]

    # NEW positions
    if diff.new_positions:
        lines.append(f"🆕 *NEW* ({len(diff.new_positions)}):")
        for c in diff.new_positions[:5]:
            lines.append(_line_new(c))
        if len(diff.new_positions) > 5:
            lines.append(f"  _...+{len(diff.new_positions)-5} more new_")
        lines.append("")

    # ADDED positions
    if diff.added_positions:
        lines.append(f"📈 *ADDED* (>+20% shares, {len(diff.added_positions)}):")
        for c in diff.added_positions[:5]:
            lines.append(_line_added(c))
        if len(diff.added_positions) > 5:
            lines.append(f"  _...+{len(diff.added_positions)-5} more added_")
        lines.append("")

    # CLOSED positions
    if diff.closed_positions:
        lines.append(f"❌ *CLOSED* ({len(diff.closed_positions)}):")
        for c in diff.closed_positions[:3]:
            lines.append(_line_closed(c))
        if len(diff.closed_positions) > 3:
            lines.append(f"  _...+{len(diff.closed_positions)-3} more closed_")
        lines.append("")

    # Top holdings
    if diff.top_holdings:
        lines.append("🏆 *Top 10 holdings*:")
        for c in diff.top_holdings:
            lines.append(_line_top(c, diff.aum_new))
        lines.append("")

    lines.append(f"📎 [SEC EDGAR filing]({edgar_url})")
    lines.append(f"_{fund.blurb}_")

    return "\n".join(lines)


def edgar_url_for_filing(cik: int, accession: str) -> str:
    """Build the human-readable EDGAR URL for an accession."""
    acc_no_dashes = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/"
