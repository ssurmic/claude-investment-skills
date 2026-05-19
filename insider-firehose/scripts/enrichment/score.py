"""score.py — compute a 0-10 Smart Money Score from filing + valuation + price.

Rubric (max 10 points):

  Role/conviction (max 4):
    +3   CEO / Chairman / Founder direct buy
    +2   CFO / President / COO
    +1   Other officer
    +1   Director (additive with officer if same person)
    -1   Pure 10% holder (downgrade — usually activist/passive)
    +1   Buy value ≥ $1M (big check)
    +1   Buy value ≥ $5M (whale check)

  Valuation (max 3):
    +1   Trailing P/E in (0, 15] — cheap on earnings
    -1   Trailing P/E > 50 — expensive
    +1   Net cash ≥ 30% of mcap — balance sheet cushion
    +1   Dividend yield ≥ 3% — paid to wait

  Price action (max 3):
    +1   Price below 200DMA — buying weakness
    +1   Within 20% of 52W LOW — fire-sale entry
    -1   Within 5% of 52W HIGH — chasing the top
    +1   Above 50DMA but below 200DMA — turn-up confirmation zone

A 0-10 floor/ceiling is enforced. Score is interpretive, not a buy/sell signal.
"""
from __future__ import annotations


def _role_score(filing: dict, total_value: float) -> int:
    s = 0
    role = (filing.get("role") or "").lower()
    title = (filing.get("title") or "").lower()

    if "ceo" in title or "chairman" in title or "chief executive" in title or "founder" in role:
        s += 3
    elif "cfo" in title or "chief financial" in title or "president" in title or "coo" in title:
        s += 2
    elif "officer" in role:
        s += 1

    if "dir" in role:
        s += 1

    if filing.get("is_10pct_only"):
        s -= 1

    if total_value >= 5_000_000:
        s += 2
    elif total_value >= 1_000_000:
        s += 1

    return s


def _valuation_score(valuation: dict) -> int:
    s = 0
    pe = valuation.get("trailing_pe")
    if pe is not None and 0 < pe <= 15:
        s += 1
    elif pe is not None and pe > 50:
        s -= 1

    net_pct = valuation.get("net_cash_pct_mcap")
    if net_pct is not None and net_pct >= 30:
        s += 1

    div = valuation.get("dividend_yield")
    # valuation.py now normalizes dividend_yield to ALWAYS be a fraction
    # (e.g. 0.0481 = 4.81%). No more ambiguity.
    if div is not None:
        div_pct = div * 100
        if div_pct >= 3:
            s += 1

    return s


def _price_score(price: dict) -> int:
    s = 0
    p_vs_200 = price.get("pct_vs_200dma")
    p_vs_50 = price.get("pct_vs_50dma")
    p_vs_high = price.get("pct_vs_52w_high")
    p_vs_low = price.get("pct_vs_52w_low")

    if p_vs_200 is not None and p_vs_200 < 0:
        s += 1
    if p_vs_low is not None and p_vs_low <= 20:
        s += 1
    if p_vs_high is not None and p_vs_high >= -5:
        s -= 1
    if p_vs_50 is not None and p_vs_200 is not None and p_vs_50 > 0 and p_vs_200 < 0:
        s += 1
    return s


def compute_score(filing: dict, total_value: float,
                  valuation: dict, price: dict) -> dict:
    """Return {score: int 0-10, factors: list[str]} explaining the score."""
    role = _role_score(filing, total_value)
    val = _valuation_score(valuation or {})
    pri = _price_score(price or {})
    raw = role + val + pri
    score = max(0, min(10, raw))

    factors = []
    # Build explanation list — only mention triggered factors
    title = (filing.get("title") or "").lower()
    role_str = (filing.get("role") or "").lower()
    if "ceo" in title or "chairman" in title or "founder" in role_str:
        factors.append("✅ CEO/Chairman/Founder buying")
    elif "cfo" in title or "president" in title or "coo" in title:
        factors.append("✅ Senior officer buying")
    if total_value >= 5_000_000:
        factors.append(f"✅ Whale-size check (${total_value/1e6:.1f}M)")
    elif total_value >= 1_000_000:
        factors.append(f"✅ Big check (${total_value/1e6:.1f}M)")
    if filing.get("is_10pct_only"):
        factors.append("⚠️ 10% holder only (not officer/director)")

    if valuation:
        pe = valuation.get("trailing_pe")
        if pe is not None and 0 < pe <= 15:
            factors.append(f"✅ Cheap P/E ({pe:.1f})")
        elif pe is not None and pe > 50:
            factors.append(f"⚠️ Expensive P/E ({pe:.1f})")
        net_pct = valuation.get("net_cash_pct_mcap")
        if net_pct is not None and net_pct >= 30:
            factors.append(f"✅ Net cash {net_pct:.0f}% of mcap")
        div = valuation.get("dividend_yield")
        if div is not None:
            div_pct = div * 100  # always fraction now
            if div_pct >= 3:
                factors.append(f"✅ Dividend {div_pct:.1f}%")

    if price:
        p_vs_high = price.get("pct_vs_52w_high")
        p_vs_low = price.get("pct_vs_52w_low")
        p_vs_200 = price.get("pct_vs_200dma")
        if p_vs_low is not None and p_vs_low <= 20:
            factors.append(f"✅ Near 52W low (+{p_vs_low:.0f}%)")
        if p_vs_200 is not None and p_vs_200 < 0:
            factors.append(f"✅ Below 200DMA ({p_vs_200:+.0f}%)")
        if p_vs_high is not None and p_vs_high >= -5:
            factors.append(f"⚠️ Near 52W high ({p_vs_high:+.0f}%)")

    return {"score": score, "factors": factors, "raw": raw}
