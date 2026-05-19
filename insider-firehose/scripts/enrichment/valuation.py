"""valuation.py — pull P/E, market cap, net cash, dividend yield, etc. via yfinance.

Single source of truth: Yahoo Finance (free, no API key, decent latency).
Returns None per field if the upstream doesn't have data (common for micro-caps,
recent IPOs, foreign ADRs). Caller must handle missing fields gracefully.
"""
from __future__ import annotations

import sys
from typing import Any


def _safe_get(info: dict, key: str, default: Any = None) -> Any:
    v = info.get(key)
    if v is None or v == "Infinity" or v == "-Infinity":
        return default
    return v


def pull_valuation(ticker: str) -> dict:
    """Pull valuation snapshot for a ticker. Empty dict on failure."""
    try:
        import yfinance as yf
    except ImportError:
        print("[ENRICH-WARN] yfinance not installed — skipping valuation",
              file=sys.stderr)
        return {}

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception as e:
        print(f"[ENRICH-WARN] yfinance.Ticker({ticker}) failed: {e}",
              file=sys.stderr)
        return {}

    if not info or not info.get("symbol"):
        return {}

    market_cap = _safe_get(info, "marketCap")
    total_cash = _safe_get(info, "totalCash")
    total_debt = _safe_get(info, "totalDebt")
    net_cash = None
    net_cash_pct_mcap = None
    if total_cash is not None and total_debt is not None:
        net_cash = total_cash - total_debt
        if market_cap and market_cap > 0:
            net_cash_pct_mcap = round(100 * net_cash / market_cap, 1)

    # ── Dividend yield: fix data-bug (ICFI 0.92 displayed as 92%) ─────
    # Prefer trailingAnnualDividendYield (always a fraction, e.g. 0.0092)
    # Fall back to dividendYield (which is sometimes already %, sometimes
    # a fraction — unreliable).
    div_yield_frac = _safe_get(info, "trailingAnnualDividendYield")
    if div_yield_frac is None:
        # last resort: compute from rate/price
        div_rate = _safe_get(info, "dividendRate") or _safe_get(info, "trailingAnnualDividendRate")
        cur_price = _safe_get(info, "currentPrice") or _safe_get(info, "regularMarketPrice")
        if div_rate and cur_price and cur_price > 0:
            div_yield_frac = div_rate / cur_price
    # Sanity check: if upstream returns >1, it's already a percent — divide back
    if div_yield_frac is not None and div_yield_frac > 1:
        div_yield_frac = div_yield_frac / 100

    # ── PEG: forward PE / earnings growth rate %  ─────────────────────
    fwd_pe = _safe_get(info, "forwardPE")
    eps_growth = _safe_get(info, "earningsGrowth")  # fraction, e.g. 0.18 = 18%
    peg = None
    if fwd_pe is not None and fwd_pe > 0 and eps_growth is not None and eps_growth > 0:
        # Convert growth fraction to percent for PEG formula
        peg = round(fwd_pe / (eps_growth * 100), 2)

    return {
        "name": _safe_get(info, "shortName") or _safe_get(info, "longName"),
        "sector": _safe_get(info, "sector"),
        "industry": _safe_get(info, "industry"),
        "market_cap": market_cap,
        "trailing_pe": _safe_get(info, "trailingPE"),
        "forward_pe": fwd_pe,
        "peg": peg,                                # NEW
        "price_to_sales": _safe_get(info, "priceToSalesTrailing12Months"),
        "price_to_book": _safe_get(info, "priceToBook"),
        "total_cash": total_cash,
        "total_debt": total_debt,
        "net_cash": net_cash,
        "net_cash_pct_mcap": net_cash_pct_mcap,
        "dividend_yield": div_yield_frac,         # NOW reliably a fraction
        "revenue_growth": _safe_get(info, "revenueGrowth"),
        "earnings_growth": eps_growth,
        "gross_margin": _safe_get(info, "grossMargins"),
        "operating_margin": _safe_get(info, "operatingMargins"),
        "profit_margin": _safe_get(info, "profitMargins"),
        "free_cashflow": _safe_get(info, "freeCashflow"),
        "beta": _safe_get(info, "beta"),
        "analyst_target": _safe_get(info, "targetMedianPrice"),
        "analyst_target_high": _safe_get(info, "targetHighPrice"),    # NEW
        "analyst_target_low": _safe_get(info, "targetLowPrice"),      # NEW
        "analyst_count": _safe_get(info, "numberOfAnalystOpinions"),
        "recommendation": _safe_get(info, "recommendationKey"),
        "shares_short_pct": _safe_get(info, "shortPercentOfFloat"),
        "insider_pct": _safe_get(info, "heldPercentInsiders"),
        "currency": _safe_get(info, "currency", "USD"),
    }
