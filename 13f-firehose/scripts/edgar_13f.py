"""
edgar_13f.py — SEC EDGAR 13F-HR fetcher and parser.

13F-HR filings list every position held by an institutional manager at quarter-end:
    - CUSIP (9-char identifier — needs translation to ticker)
    - Issuer name
    - Class title (COM, CL A, etc.)
    - Value (USD, in thousands per SEC convention — we convert to dollars)
    - Shares or principal amount

The filing has TWO parts on EDGAR:
    1. Index page: lists all attachments including the InfoTable XML
    2. InfoTable XML: the actual holdings

We use the EDGAR submissions JSON API to find recent filings, then download
the InfoTable XML directly.

API contract:
    submissions:  https://data.sec.gov/submissions/CIK{0-padded-10}.json
    archive:      https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/

SEC requires User-Agent with contact email. Polite throttle: ≤10 req/sec.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import requests


USER_AGENT = os.environ.get(
    "EDGAR_USER_AGENT",
    "ssurmiczizhao@gmail.com 13f-firehose/1.0",
)
HEADERS = {"User-Agent": USER_AGENT, "Accept": "*/*"}
HTTP_DELAY = 0.15  # ≤10 req/sec per SEC fair-use


# ─── Data types ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Holding:
    """A single line item in a 13F InfoTable."""
    cusip: str
    issuer: str
    class_title: str
    value_usd: float  # already converted from thousands to dollars
    shares: int
    put_call: str = ""  # "Put", "Call", or "" for stock

    @property
    def is_option(self) -> bool:
        return bool(self.put_call)

    @property
    def key(self) -> str:
        """Unique key for this position: cusip + put/call distinguishes 3 instruments."""
        return f"{self.cusip}|{self.put_call or 'STK'}"


@dataclass
class Filing:
    cik: int
    accession: str          # e.g. "0002045724-26-000002"
    form: str               # "13F-HR" or "13F-HR/A" (amendment)
    period: str             # "2025-12-31" (quarter-end the filing reports on)
    filed: str              # "2026-02-11" (date filed with SEC)
    holdings: list[Holding] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        return sum(h.value_usd for h in self.holdings)

    @property
    def num_positions(self) -> int:
        return len(self.holdings)


# ─── Fetch helpers ─────────────────────────────────────────────────────────
def _get(url: str, retries: int = 3) -> requests.Response:
    """GET with SEC-compliant headers + politeness sleep + retry."""
    last_exc = None
    for i in range(retries):
        try:
            time.sleep(HTTP_DELAY)
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"EDGAR GET failed after {retries} retries: {url}\n{last_exc}")


def list_13f_filings(cik: int, limit: int = 12) -> list[dict]:
    """
    Return recent 13F filings for a CIK, newest first.

    Each item: {accession, form, period, filed}
    """
    cik_str = f"{cik:010d}"
    url = f"https://data.sec.gov/submissions/CIK{cik_str}.json"
    r = _get(url)
    data = r.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accs = recent.get("accessionNumber", [])
    periods = recent.get("reportDate", [])
    fileds = recent.get("filingDate", [])

    out = []
    for i, form in enumerate(forms):
        if not form.startswith("13F-HR"):
            continue
        out.append({
            "accession": accs[i],
            "form": form,
            "period": periods[i],
            "filed": fileds[i],
        })
        if len(out) >= limit:
            break
    return out


def _find_infotable_url(cik: int, accession: str) -> Optional[str]:
    """
    Given an accession number, find the InfoTable XML file URL.

    The accession format is: 0002045724-26-000002
    The archive folder uses no dashes: 000204572426000002

    EDGAR index.json lists every file in the filing.
    """
    acc_no_dashes = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}"
    idx_url = f"{base}/index.json"
    try:
        r = _get(idx_url)
        idx = r.json()
        items = idx.get("directory", {}).get("item", [])
    except Exception as e:
        print(f"[WARN] {cik}/{accession}: index.json fetch failed: {e}", file=sys.stderr)
        return None

    # InfoTable file naming is inconsistent — filers use anything from
    # "form13fInfoTable.xml" to custom names like "SALP_13FQ425.xml".
    # Strategy: find .xml files that are NOT primary_doc.xml (cover page).
    # The InfoTable is always larger than primary_doc (holdings data), so we
    # also fall back to "largest .xml that isn't primary_doc".
    candidates = []
    for item in items:
        name = item.get("name", "")
        if not name.lower().endswith(".xml"):
            continue
        if name.lower() == "primary_doc.xml":
            continue
        size_str = item.get("size", "0") or "0"
        try:
            size = int(size_str)
        except ValueError:
            size = 0
        candidates.append((size, name))

    if not candidates:
        return None
    # Prefer files with "infotable" in the name; else the largest .xml.
    info_named = [c for c in candidates if "infotable" in c[1].lower()]
    if info_named:
        return f"{base}/{info_named[0][1]}"
    candidates.sort(reverse=True)  # largest first
    return f"{base}/{candidates[0][1]}"


# Strip XML namespace (e.g. {http://www.sec.gov/edgar/document/thirteenf/informationtable}infoTable)
_NS_RE = re.compile(r"^\{[^}]+\}")
def _tag(elem: ET.Element) -> str:
    return _NS_RE.sub("", elem.tag)


def _findtext_ns(parent: ET.Element, name: str) -> str:
    """Find child by tag name, ignoring namespace."""
    for child in parent:
        if _tag(child) == name:
            return (child.text or "").strip()
    return ""


def parse_infotable(xml_bytes: bytes) -> list[Holding]:
    """Parse 13F InfoTable XML into a list of Holdings.

    Each <infoTable> in the SEC schema has fields:
        nameOfIssuer, titleOfClass, cusip, value (in $1000s),
        shrsOrPrnAmt > sshPrnamt + sshPrnamtType,
        putCall (optional)
    """
    root = ET.fromstring(xml_bytes)
    out: list[Holding] = []
    for elem in root.iter():
        if _tag(elem) != "infoTable":
            continue
        cusip = _findtext_ns(elem, "cusip")
        issuer = _findtext_ns(elem, "nameOfIssuer")
        class_title = _findtext_ns(elem, "titleOfClass")
        val_thousands_str = _findtext_ns(elem, "value")
        put_call = _findtext_ns(elem, "putCall")

        # shares is nested under shrsOrPrnAmt
        shares = 0
        for child in elem:
            if _tag(child) == "shrsOrPrnAmt":
                shares_str = _findtext_ns(child, "sshPrnamt")
                try:
                    shares = int(shares_str.replace(",", ""))
                except ValueError:
                    shares = 0
                break

        try:
            # SEC convention: pre-2022 filings used $1000s; post-2022 use exact dollars.
            # We detect this by magnitude — if value/shares ratio is absurdly low (<$0.01/share),
            # it's almost certainly the old thousands convention. Otherwise treat as dollars.
            val = float(val_thousands_str.replace(",", "")) if val_thousands_str else 0.0
            # Modern filings (post-2022 Q4) are in raw dollars. Older were in thousands.
            # Heuristic: if value < shares * 0.05, it's in thousands.
            if shares > 0 and val > 0 and (val / shares) < 0.05:
                val *= 1000.0
        except ValueError:
            val = 0.0

        if not cusip:
            continue
        out.append(Holding(
            cusip=cusip.strip(),
            issuer=issuer,
            class_title=class_title,
            value_usd=val,
            shares=shares,
            put_call=put_call,
        ))
    return out


def fetch_latest_filing(cik: int) -> Optional[Filing]:
    """Fetch the most recent 13F-HR filing for a CIK, with all holdings parsed."""
    filings = list_13f_filings(cik, limit=4)
    if not filings:
        return None
    f = filings[0]
    info_url = _find_infotable_url(cik, f["accession"])
    if not info_url:
        print(f"[WARN] CIK {cik} acc {f['accession']}: no InfoTable XML found", file=sys.stderr)
        return None
    try:
        r = _get(info_url)
        holdings = parse_infotable(r.content)
    except Exception as e:
        print(f"[WARN] CIK {cik} InfoTable parse failed: {e}", file=sys.stderr)
        return None
    return Filing(
        cik=cik,
        accession=f["accession"],
        form=f["form"],
        period=f["period"],
        filed=f["filed"],
        holdings=holdings,
    )


def fetch_filing_by_accession(cik: int, accession: str) -> Optional[Filing]:
    """Fetch a specific 13F filing by accession number (for comparing vs prior)."""
    filings = list_13f_filings(cik, limit=12)
    match = next((x for x in filings if x["accession"] == accession), None)
    if not match:
        return None
    info_url = _find_infotable_url(cik, accession)
    if not info_url:
        return None
    try:
        r = _get(info_url)
        holdings = parse_infotable(r.content)
    except Exception:
        return None
    return Filing(
        cik=cik,
        accession=accession,
        form=match["form"],
        period=match["period"],
        filed=match["filed"],
        holdings=holdings,
    )


def fetch_previous_filing(cik: int, before_accession: str) -> Optional[Filing]:
    """Fetch the 13F immediately before the given accession (for diff)."""
    filings = list_13f_filings(cik, limit=12)
    target_idx = next(
        (i for i, x in enumerate(filings) if x["accession"] == before_accession),
        None,
    )
    if target_idx is None or target_idx + 1 >= len(filings):
        return None
    prev = filings[target_idx + 1]
    return fetch_filing_by_accession(cik, prev["accession"])


# ─── CLI for manual testing ────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python edgar_13f.py <CIK>")
        sys.exit(1)
    cik = int(sys.argv[1])
    print(f"Fetching latest 13F for CIK {cik}...", file=sys.stderr)
    f = fetch_latest_filing(cik)
    if not f:
        print("No 13F found.")
        sys.exit(1)
    print(f"\n{f.form} | period {f.period} | filed {f.filed} | acc {f.accession}")
    print(f"Total value: ${f.total_value:,.0f} | positions: {f.num_positions}")
    print("\nTop 10 holdings:")
    top = sorted(f.holdings, key=lambda h: h.value_usd, reverse=True)[:10]
    for h in top:
        opt = f" [{h.put_call.upper()}]" if h.put_call else ""
        pct = (h.value_usd / f.total_value * 100) if f.total_value else 0
        print(f"  {h.issuer[:35]:<35} {h.cusip}{opt}  ${h.value_usd:>15,.0f}  {pct:>5.2f}%")
