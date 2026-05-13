"""
diff.py — Compute the delta between two 13F filings.

Output categories:
    NEW       — Position not in prior filing
    ADDED     — Existing position, value or shares increased >= ADD_THRESHOLD
    REDUCED   — Existing position, shares decreased >= REDUCE_THRESHOLD (but not closed)
    CLOSED    — Position present in prior, absent in current

We key positions by (cusip, put_call) so that stock + call + put on the same
issuer are tracked as three separate instruments.

Value changes are reported separately from share changes because price movement
can inflate value without any new buying.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from edgar_13f import Filing, Holding


# Thresholds for classification
ADD_SHARE_THRESHOLD = 0.20     # +20% shares = "ADDED"
REDUCE_SHARE_THRESHOLD = -0.20 # -20% shares = "REDUCED"
NEW_MIN_VALUE = 5_000_000      # Skip new positions <$5M (noise)


@dataclass
class PositionChange:
    """A single position's delta between two 13F filings."""
    cusip: str
    issuer: str
    put_call: str               # "" = stock, "Call" or "Put" = derivative

    # New filing
    new_value: float = 0.0
    new_shares: int = 0

    # Prior filing
    prior_value: float = 0.0
    prior_shares: int = 0

    # Derived
    @property
    def category(self) -> str:
        if self.prior_shares == 0 and self.new_shares > 0:
            return "NEW"
        if self.new_shares == 0 and self.prior_shares > 0:
            return "CLOSED"
        share_change = self.share_change_pct
        if share_change >= ADD_SHARE_THRESHOLD:
            return "ADDED"
        if share_change <= REDUCE_SHARE_THRESHOLD:
            return "REDUCED"
        return "HELD"

    @property
    def share_change_pct(self) -> float:
        if self.prior_shares == 0:
            return float("inf") if self.new_shares > 0 else 0.0
        return (self.new_shares - self.prior_shares) / self.prior_shares

    @property
    def value_change(self) -> float:
        return self.new_value - self.prior_value

    @property
    def label(self) -> str:
        """Human-readable label including instrument type."""
        suffix = ""
        if self.put_call:
            suffix = f" [{self.put_call.upper()}]"
        return f"{self.issuer}{suffix}"


@dataclass
class FilingDiff:
    """Full diff between current and prior filings of one fund."""
    cik: int
    fund_name: str
    period_new: str
    period_prior: str
    aum_new: float
    aum_prior: float
    new_positions: list[PositionChange]
    added_positions: list[PositionChange]
    reduced_positions: list[PositionChange]
    closed_positions: list[PositionChange]
    top_holdings: list[PositionChange]   # Top 10 in NEW filing by value

    @property
    def aum_change_pct(self) -> float:
        if self.aum_prior == 0:
            return float("inf")
        return (self.aum_new - self.aum_prior) / self.aum_prior


def _holdings_map(filing: Optional[Filing]) -> dict[str, Holding]:
    """Build cusip|put_call → Holding map. Empty dict if filing is None."""
    if not filing:
        return {}
    return {h.key: h for h in filing.holdings}


def compute_diff(
    current: Filing,
    prior: Optional[Filing],
    fund_name: str,
) -> FilingDiff:
    """Compute the diff between current and prior filing.

    If prior is None (first time we see this fund), all positions count as NEW.
    """
    cur_map = _holdings_map(current)
    prior_map = _holdings_map(prior)

    all_keys = set(cur_map.keys()) | set(prior_map.keys())
    changes: list[PositionChange] = []
    for key in all_keys:
        cur = cur_map.get(key)
        pri = prior_map.get(key)
        ref = cur or pri  # one of them is non-None
        change = PositionChange(
            cusip=ref.cusip,
            issuer=ref.issuer,
            put_call=ref.put_call,
            new_value=cur.value_usd if cur else 0.0,
            new_shares=cur.shares if cur else 0,
            prior_value=pri.value_usd if pri else 0.0,
            prior_shares=pri.shares if pri else 0,
        )
        changes.append(change)

    new_pos = [c for c in changes
               if c.category == "NEW" and c.new_value >= NEW_MIN_VALUE]
    added = [c for c in changes if c.category == "ADDED"]
    reduced = [c for c in changes if c.category == "REDUCED"]
    closed = [c for c in changes if c.category == "CLOSED"]

    # Sort by value/significance
    new_pos.sort(key=lambda c: c.new_value, reverse=True)
    added.sort(key=lambda c: c.value_change, reverse=True)
    reduced.sort(key=lambda c: c.value_change)  # Most negative first
    closed.sort(key=lambda c: c.prior_value, reverse=True)

    # Top holdings in new filing (full position table)
    held_now = [PositionChange(
        cusip=h.cusip,
        issuer=h.issuer,
        put_call=h.put_call,
        new_value=h.value_usd,
        new_shares=h.shares,
        prior_value=prior_map.get(h.key, Holding(h.cusip, "", "", 0, 0)).value_usd if prior_map else 0,
        prior_shares=prior_map.get(h.key, Holding(h.cusip, "", "", 0, 0)).shares if prior_map else 0,
    ) for h in current.holdings]
    held_now.sort(key=lambda c: c.new_value, reverse=True)

    return FilingDiff(
        cik=current.cik,
        fund_name=fund_name,
        period_new=current.period,
        period_prior=prior.period if prior else "(first observation)",
        aum_new=current.total_value,
        aum_prior=prior.total_value if prior else 0.0,
        new_positions=new_pos,
        added_positions=added,
        reduced_positions=reduced,
        closed_positions=closed,
        top_holdings=held_now[:10],
    )
