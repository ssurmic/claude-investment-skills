"""
format_alert.py — Render political trade alerts into Telegram-ready Markdown.

Two alert types:
  Congress PTR  — STOCK Act periodic transaction reports (Senate + House)
  OGE 278-T     — Executive branch PDF disclosures
"""

from __future__ import annotations
from typing import List

from politician_registry import Politician


# Amount range -> human label
OGE_AMOUNT_MAP = {
    "J": "$1K–$15K",
    "K": "$15K–$50K",
    "L": "$50K–$100K",
    "M": "$100K–$250K",
    "N": "$250K–$500K",
    "O": "$500K–$1M",
    "P1": "$1M–$5M",
    "P2": "$5M–$25M",
    "P3": "$25M+",
}

CONGRESS_PARTY_EMOJI = {"D": "🔵", "R": "🔴", "I": "⚪"}


def _fmt_amount(amount_str: str) -> str:
    """Format dollar amount range for display."""
    # OGE category code
    if amount_str in OGE_AMOUNT_MAP:
        return OGE_AMOUNT_MAP[amount_str]
    # Already formatted range like "$1,001 - $15,000"
    return amount_str


def _trade_emoji(t_type: str) -> str:
    t = t_type.lower()
    if "purchase" in t or t == "p":
        return "🟢"
    if "sale" in t or "sell" in t or t == "s":
        return "🔴"
    return "⚪"


def render_congress_alert(
    politician: Politician,
    trades: List[dict],
    filing_url: str,
) -> str:
    """Render a Telegram alert for new Congress PTR trades."""
    party_emoji = CONGRESS_PARTY_EMOJI.get(politician.party, "⚪")
    chamber_label = "Sen." if politician.chamber == "SENATE" else "Rep."

    lines = [
        f"🏛 *Political Trade: {chamber_label} {politician.name}*  {party_emoji}`{politician.party}-{politician.state}`",
        f"_{politician.role}_",
        f"📋 *{len(trades)} new transaction(s)* via STOCK Act PTR",
        "",
    ]

    # Group by type
    purchases = [t for t in trades if "purchase" in t.get("transaction_type", "").lower()]
    sales = [t for t in trades if "sale" in t.get("transaction_type", "").lower() or "sell" in t.get("transaction_type", "").lower()]

    if purchases:
        lines.append(f"🟢 *PURCHASES* ({len(purchases)}):")
        for t in purchases[:5]:
            ticker = t.get("ticker", "")
            ticker_str = f"`{ticker}`  " if ticker else ""
            lines.append(
                f"  • {ticker_str}*{t.get('asset_description', 'Unknown')[:35]}*  "
                f"{_fmt_amount(t.get('amount_range', '?'))}  "
                f"_{t.get('transaction_date', '?')}_"
            )
        if len(purchases) > 5:
            lines.append(f"  _...+{len(purchases)-5} more_")
        lines.append("")

    if sales:
        lines.append(f"🔴 *SALES* ({len(sales)}):")
        for t in sales[:5]:
            ticker = t.get("ticker", "")
            ticker_str = f"`{ticker}`  " if ticker else ""
            lines.append(
                f"  • {ticker_str}*{t.get('asset_description', 'Unknown')[:35]}*  "
                f"{_fmt_amount(t.get('amount_range', '?'))}  "
                f"_{t.get('transaction_date', '?')}_"
            )
        if len(sales) > 5:
            lines.append(f"  _...+{len(sales)-5} more_")
        lines.append("")

    lines.append(f"📎 [Filing]({filing_url})")
    lines.append(f"_{politician.blurb}_")
    return "\n".join(lines)


def render_oge_alert(
    politician: Politician,
    trades: List[dict],
    pdf_url: str,
    report_period: str = "",
) -> str:
    """Render a Telegram alert for a new OGE 278-T filing."""
    period_str = f"  Period: *{report_period}*" if report_period else ""

    purchases = [t for t in trades if t.get("type", "").upper() in ("P", "PURCHASE", "BUY")]
    sales = [t for t in trades if t.get("type", "").upper() in ("S", "SALE", "SELL")]

    # Find biggest trades by amount code
    amount_order = ["P3", "P2", "P1", "O", "N", "M", "L", "K", "J"]

    def sort_by_amount(trade_list):
        return sorted(
            trade_list,
            key=lambda t: amount_order.index(t.get("amount", "J"))
            if t.get("amount", "J") in amount_order else 99
        )

    lines = [
        f"🏛 *OGE 278-T: {politician.name}*  🔴`{politician.party}`",
        f"_{politician.role}_{period_str}",
        f"📋 *{len(trades)} total transactions*  "
        f"({len(purchases)} buys / {len(sales)} sells)",
        "",
    ]

    if purchases:
        top_buys = sort_by_amount(purchases)[:5]
        lines.append(f"🟢 *TOP BUYS* ({len(purchases)} total):")
        for t in top_buys:
            ticker = t.get("ticker", "")
            ticker_str = f"`{ticker}`  " if ticker else ""
            lines.append(
                f"  • {ticker_str}*{t.get('asset', 'Unknown')[:35]}*  "
                f"{_fmt_amount(t.get('amount', '?'))}  "
                f"_{t.get('date', '?')}_"
            )
        if len(purchases) > 5:
            lines.append(f"  _...+{len(purchases)-5} more buys_")
        lines.append("")

    if sales:
        top_sells = sort_by_amount(sales)[:5]
        lines.append(f"🔴 *TOP SELLS* ({len(sales)} total):")
        for t in top_sells:
            ticker = t.get("ticker", "")
            ticker_str = f"`{ticker}`  " if ticker else ""
            lines.append(
                f"  • {ticker_str}*{t.get('asset', 'Unknown')[:35]}*  "
                f"{_fmt_amount(t.get('amount', '?'))}  "
                f"_{t.get('date', '?')}_"
            )
        if len(sales) > 5:
            lines.append(f"  _...+{len(sales)-5} more sells_")
        lines.append("")

    lines.append(f"📎 [OGE 278-T PDF]({pdf_url})")
    lines.append(f"_{politician.blurb}_")
    return "\n".join(lines)
