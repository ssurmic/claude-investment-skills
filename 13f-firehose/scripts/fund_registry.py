"""
fund_registry.py — Registry of famous funds whose 13F filings we monitor.

A 13F-HR is filed quarterly by institutional managers with >$100M AUM, within
45 days after each quarter-end (Q1→May 15, Q2→Aug 14, Q3→Nov 14, Q4→Feb 14).

Each entry:
    cik          SEC CIK (10-digit zero-padded, but we accept any int)
    name         Display name for Telegram alerts
    manager      Person running the fund (for narrative)
    tag          Category: AI, VALUE, MACRO, QUANT, VC, ACTIVIST, CORP
    blurb        One-line why-we-care
    priority     1 = always alert | 2 = top-N positions only | 3 = digest only

To verify a CIK: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<cik>
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Fund:
    cik: int
    name: str
    manager: str
    tag: str
    blurb: str
    priority: int = 1


# ─── Registry ──────────────────────────────────────────────────────────────
# Ordered by priority — top of list = highest signal.
FUNDS: List[Fund] = [
    # === AI / AGI thematic ===
    Fund(
        cik=2045724,
        name="Situational Awareness LP",
        manager="Leopold Aschenbrenner",
        tag="AI",
        blurb="Former OpenAI; pure-play AGI fund. +33% AUM Q3→Q4 2025",
        priority=1,
    ),
    Fund(
        cik=1045810,
        name="NVIDIA Corporation",
        manager="Corp. Strategic Investments",
        tag="CORP",
        blurb="NVDA's own 13F — they show their hand on AI ecosystem bets",
        priority=1,
    ),

    # === Legendary value / activist ===
    Fund(
        cik=1067983,
        name="Berkshire Hathaway",
        manager="Warren Buffett / Greg Abel",
        tag="VALUE",
        blurb="The benchmark — every Q4 13F moves markets",
        priority=1,
    ),
    Fund(
        cik=1336528,
        name="Pershing Square Capital",
        manager="Bill Ackman",
        tag="ACTIVIST",
        blurb="High-conviction concentrated bets (8-12 names)",
        priority=1,
    ),
    Fund(
        cik=1040273,
        name="Third Point LLC",
        manager="Dan Loeb",
        tag="ACTIVIST",
        blurb="Event-driven activist, classic catalyst trades",
        priority=1,
    ),
    Fund(
        cik=1079114,
        name="Greenlight Capital",
        manager="David Einhorn",
        tag="VALUE",
        blurb="Long/short value, famous short calls (Lehman, Allied Capital). May be stale — last 13F Feb 2024",
        priority=3,
    ),
    Fund(
        cik=1656456,
        name="Appaloosa LP",
        manager="David Tepper",
        tag="MACRO",
        blurb="Macro/distressed, made fortune timing 2009 bottom",
        priority=1,
    ),

    # === Quant / systematic ===
    Fund(
        cik=1037389,
        name="Renaissance Technologies",
        manager="Jim Simons (legacy)",
        tag="QUANT",
        blurb="Medallion is closed; their 13F shows the RIEF/RIDA tilts",
        priority=2,
    ),
    Fund(
        cik=1273087,
        name="Millennium Management",
        manager="Izzy Englander",
        tag="QUANT",
        blurb="$70B+ multi-strategy pod shop; biggest market-neutral book on the Street",
        priority=1,
    ),
    Fund(
        cik=1350694,
        name="Bridgewater Associates",
        manager="Ray Dalio (legacy) / Karen Karniol-Tambour",
        tag="MACRO",
        blurb="Largest hedge fund globally — All Weather tilts visible",
        priority=2,
    ),

    # === Macro / global ===
    Fund(
        cik=1029160,
        name="Soros Fund Management",
        manager="Soros family office (post-Quantum)",
        tag="MACRO",
        blurb="Quantum Fund successor — concentrated macro bets",
        priority=1,
    ),

    # === Growth / VC-adjacent ===
    Fund(
        cik=1167483,
        name="Tiger Global Management",
        manager="Chase Coleman",
        tag="VC",
        blurb="Hybrid public/private growth, AI heavy post-2024 reset",
        priority=2,
    ),
    Fund(
        cik=1135730,
        name="Coatue Management",
        manager="Philippe Laffont",
        tag="VC",
        blurb="Tech/AI public-private crossover, NVDA early adopter",
        priority=2,
    ),
    Fund(
        cik=1061165,
        name="Lone Pine Capital",
        manager="Stephen Mandel",
        tag="VC",
        blurb="Tiger Cub — quality growth at reasonable price",
        priority=2,
    ),
    Fund(
        cik=1697748,
        name="ARK Investment Management",
        manager="Cathie Wood",
        tag="VC",
        blurb="Disruptive innovation thesis; ETFs disclose daily but 13F shows full book",
        priority=3,
    ),

    # === Distressed / credit ===
    Fund(
        cik=1027796,
        name="Oaktree Capital Management",
        manager="Howard Marks",
        tag="VALUE",
        blurb="Distressed credit + opportunistic equity — Marks's memos are gold",
        priority=2,
    ),

    # === Famous short / contrarian ===
    Fund(
        cik=1649339,
        name="Scion Asset Management",
        manager="Michael Burry",
        tag="VALUE",
        blurb="The Big Short guy — small AUM but every 13F triggers Twitter frenzy",
        priority=1,
    ),
]


def get_funds(priority_max: int = 3) -> List[Fund]:
    """Return funds with priority <= priority_max."""
    return [f for f in FUNDS if f.priority <= priority_max]


def get_fund_by_cik(cik: int) -> Fund | None:
    """Lookup a fund by CIK."""
    for f in FUNDS:
        if f.cik == cik:
            return f
    return None


if __name__ == "__main__":
    print(f"Registry contains {len(FUNDS)} funds:")
    for f in FUNDS:
        print(f"  [P{f.priority}] CIK {f.cik:>10} | {f.tag:>8} | {f.name:<35} ({f.manager})")
