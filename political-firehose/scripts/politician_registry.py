"""
politician_registry.py — Registry of politicians whose stock trades we monitor.

Two systems:
  CONGRESS  — STOCK Act PTR (Periodic Transaction Report), Senate + House
              Disclosed within 45 days of transaction; public JSON/XML
  OGE       — OGE Form 278-T, executive branch (President, Cabinet, senior staff)
              PDF only; no structured API

Each entry:
    name         Display name (must match disclosure filing name)
    first_name   For Senate/House search filtering
    last_name    For Senate/House search filtering
    system       "CONGRESS" or "OGE"
    chamber      "SENATE" | "HOUSE" | "EXECUTIVE" (for CONGRESS entries)
    party        "D" | "R" | "I"
    state        Two-letter state code
    role         Current role
    blurb        Why we care
    priority     1 = alert immediately | 2 = digest only
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Politician:
    name: str
    first_name: str
    last_name: str
    system: str          # "CONGRESS" or "OGE"
    chamber: str         # "SENATE" | "HOUSE" | "EXECUTIVE"
    party: str
    state: str
    role: str
    blurb: str
    priority: int = 1


# ─── Registry ──────────────────────────────────────────────────────────────
POLITICIANS: List[Politician] = [

    # === Executive Branch (OGE Form 278-T) ===
    Politician(
        name="Donald J. Trump",
        first_name="Donald",
        last_name="Trump",
        system="OGE",
        chamber="EXECUTIVE",
        party="R",
        state="FL",
        role="President of the United States",
        blurb="3,642 trades in Q1 2026. NVDA/ORCL/HOOD buys; AMZN/META/MSFT sells",
        priority=1,
    ),
    Politician(
        name="Scott Bessent",
        first_name="Scott",
        last_name="Bessent",
        system="OGE",
        chamber="EXECUTIVE",
        party="R",
        state="NY",
        role="Secretary of the Treasury",
        blurb="Former macro hedge fund manager; Treasury sees policy before markets do",
        priority=1,
    ),
    Politician(
        name="Howard Lutnick",
        first_name="Howard",
        last_name="Lutnick",
        system="OGE",
        chamber="EXECUTIVE",
        party="R",
        state="NY",
        role="Secretary of Commerce",
        blurb="Former Cantor Fitzgerald CEO; deep ties to financial markets",
        priority=1,
    ),

    # === Senate (STOCK Act PTR) ===
    Politician(
        name="Tommy Tuberville",
        first_name="Tommy",
        last_name="Tuberville",
        system="CONGRESS",
        chamber="SENATE",
        party="R",
        state="AL",
        role="Senator",
        blurb="500+ trades disclosed in 2023; active trader on Armed Services committee",
        priority=1,
    ),
    Politician(
        name="Mark Kelly",
        first_name="Mark",
        last_name="Kelly",
        system="CONGRESS",
        chamber="SENATE",
        party="D",
        state="AZ",
        role="Senator",
        blurb="Aerospace/tech focused; frequent tech stock trades",
        priority=2,
    ),
    Politician(
        name="Dan Sullivan",
        first_name="Dan",
        last_name="Sullivan",
        system="CONGRESS",
        chamber="SENATE",
        party="R",
        state="AK",
        role="Senator",
        blurb="Energy committee; oil/gas and defense trades",
        priority=2,
    ),
    Politician(
        name="Sheldon Whitehouse",
        first_name="Sheldon",
        last_name="Whitehouse",
        system="CONGRESS",
        chamber="SENATE",
        party="D",
        state="RI",
        role="Senator",
        blurb="Active trader; energy transition-related positions",
        priority=2,
    ),

    # === House (STOCK Act PTR) ===
    Politician(
        name="Nancy Pelosi",
        first_name="Nancy",
        last_name="Pelosi",
        system="CONGRESS",
        chamber="HOUSE",
        party="D",
        state="CA",
        role="Representative",
        blurb="Legendary track record; NVDA, PANW, CRWD buys consistently outperform",
        priority=1,
    ),
    Politician(
        name="Austin Scott",
        first_name="Austin",
        last_name="Scott",
        system="CONGRESS",
        chamber="HOUSE",
        party="R",
        state="GA",
        role="Representative",
        blurb="Agriculture/Armed Services committees; frequent tech trades",
        priority=1,
    ),
    Politician(
        name="Dan Crenshaw",
        first_name="Dan",
        last_name="Crenshaw",
        system="CONGRESS",
        chamber="HOUSE",
        party="R",
        state="TX",
        role="Representative",
        blurb="Intelligence/defense committee; active in defense/tech names",
        priority=1,
    ),
    Politician(
        name="Michael McCaul",
        first_name="Michael",
        last_name="McCaul",
        system="CONGRESS",
        chamber="HOUSE",
        party="R",
        state="TX",
        role="Representative",
        blurb="Foreign Affairs chair; tech and defense stock activity",
        priority=2,
    ),
    Politician(
        name="Josh Gottheimer",
        first_name="Josh",
        last_name="Gottheimer",
        system="CONGRESS",
        chamber="HOUSE",
        party="D",
        state="NJ",
        role="Representative",
        blurb="Financial Services committee; frequent tech/finance trades",
        priority=2,
    ),
    Politician(
        name="Marjorie Taylor Greene",
        first_name="Marjorie Taylor",
        last_name="Greene",
        system="CONGRESS",
        chamber="HOUSE",
        party="R",
        state="GA",
        role="Representative",
        blurb="Crypto and tech stock trader; often correlated with policy signals",
        priority=2,
    ),
]


def get_politicians(system: Optional[str] = None, priority_max: int = 3) -> List[Politician]:
    """Return politicians filtered by system and priority."""
    result = [p for p in POLITICIANS if p.priority <= priority_max]
    if system:
        result = [p for p in result if p.system == system]
    return result


def get_congress_names() -> set[str]:
    """Return set of last names for Congress filtering (fast lookup)."""
    return {p.last_name.lower() for p in POLITICIANS if p.system == "CONGRESS"}


def get_oge_names() -> set[str]:
    """Return set of last names for OGE filtering."""
    return {p.last_name.lower() for p in POLITICIANS if p.system == "OGE"}


def find_politician(first: str, last: str) -> Optional[Politician]:
    """Match a politician by first/last name (case-insensitive partial match)."""
    last_lower = last.strip().lower()
    first_lower = first.strip().lower()
    for p in POLITICIANS:
        if p.last_name.lower() == last_lower:
            # Full first name match OR just first word match (e.g., "Nancy" matches "Nancy")
            p_first_words = p.first_name.lower().split()
            q_first_words = first_lower.split()
            if p_first_words and q_first_words and p_first_words[0] == q_first_words[0]:
                return p
            # Also match if one name is a substring
            if first_lower in p.first_name.lower() or p.first_name.lower() in first_lower:
                return p
    return None


if __name__ == "__main__":
    print(f"Registry contains {len(POLITICIANS)} politicians:")
    for p in POLITICIANS:
        print(f"  [P{p.priority}] {p.system:>9} | {p.chamber:>9} | {p.party} | "
              f"{p.state} | {p.name:<35} ({p.role})")
