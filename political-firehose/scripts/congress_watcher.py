#!/usr/bin/env python3
"""
congress_watcher.py — STOCK Act PTR Watcher: Senate + House Periodic Transaction Reports.

Sources:
  HOUSE: disclosures-clerk.house.gov XML filing index + PDF parsing (pdftotext)
    - House XML: https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.xml
    - PTRs have FilingType='P'
    - Digital filings (DocID ≥ 20000000) have text PDFs; paper scans (DocID < 10000000) do not.
    - PDF URL: https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{DocID}.pdf

  SENATE: efdsearch.senate.gov DataTables AJAX API
    - Requires: agree to prohibition terms → POST /search/home/ → session cookies
    - Data API: POST /search/report/data/
    - NOTE: As of May 2026, the Senate eFD data API is blocked by Akamai WAF for
      non-browser clients. Senate fetcher is implemented but may return empty
      with a warning in automated environments. Run from a browser or set
      SENATE_EFD_BYPASS=1 if you have an alternative route.

PDF parsing requires system-installed pdftotext (poppler-utils):
  brew install poppler   # macOS
  apt-get install poppler-utils  # Linux
"""

import io
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("ERROR: requests not installed. Run: pip install requests")

# ── Constants ──────────────────────────────────────────────────────────────────
USER_AGENT = "ssurmiczizhao@gmail.com political-firehose/1.0"
HOUSE_XML_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.xml"
HOUSE_PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
SENATE_HOME_URL = "https://efdsearch.senate.gov/search/home/"
SENATE_DATA_URL = "https://efdsearch.senate.gov/search/report/data/"
# Community S3 aggregate — all Senate PTRs, updated daily, no WAF
SENATE_S3_URL = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/"
    "aggregate/all_transactions.json"
)
DIGITAL_DOCTYPE_THRESHOLD = 10_000_000  # DocIDs above this have text-layer PDFs

# ── Helpers ───────────────────────────────────────────────────────────────────

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _eprint(*args):
    """Print progress to stderr."""
    print(*args, file=sys.stderr, flush=True)


def _parse_date_mdy(s: str) -> Optional[datetime]:
    """Parse MM/DD/YYYY date strings."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y")
    except ValueError:
        return None


def _standardize_date(s: str) -> Optional[str]:
    """Return YYYY-MM-DD or None."""
    d = _parse_date_mdy(s)
    return d.strftime("%Y-%m-%d") if d else None


def _state_from_district(statedst: str) -> str:
    """'CA17' -> 'CA'"""
    return statedst[:2].upper() if statedst and len(statedst) >= 2 else ""


# ── House PDF Parser ──────────────────────────────────────────────────────────

def _parse_house_ptr_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Parse a House PTR PDF (digital format only, DocID >= 20M).
    Uses pdftotext -layout (poppler) to extract text.
    Returns list of transaction dicts with ticker, type, date, amount.
    Returns empty list if pdftotext unavailable or PDF has no text.
    """
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-", "-"],
            input=pdf_bytes,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        _eprint("  [WARN] pdftotext not found — install poppler: brew install poppler")
        return []
    except subprocess.TimeoutExpired:
        _eprint("  [WARN] pdftotext timed out")
        return []

    raw = result.stdout
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
    if not text or not text.strip():
        return []  # Scanned image PDF — no text layer

    lines = text.split("\n")
    transactions = []

    for i, line in enumerate(lines):
        # Pattern A: "(TICKER) [ST]" is on the SAME row as transaction type + dates + amount
        # e.g. "   Apple Inc. - Common Stock (AAPL)     P    04/15/2026 05/01/2026   $1,001 - $15,000"
        ma = re.match(
            r"^\s+(?:SP\s+)?(.+?)\(([A-Z]{1,5})\)\s*(?:\[ST\])?\s+"
            r"([PS])\s+(\d{2}/\d{2}/\d{4})\s+\d{2}/\d{2}/\d{4}\s+"
            r"(\$[\d,]+ - \$[\d,]+)",
            line,
        )
        # Pattern B: Ticker is on the NEXT line (…Stock [P/S]  dates  amount  \n (TICKER) [ST])
        mb = re.match(
            r"^\s+(?:SP\s+)?(.+?)\s+([PS])\s+(\d{2}/\d{2}/\d{4})\s+"
            r"\d{2}/\d{2}/\d{4}\s+(\$[\d,]+ - \$[\d,]+)",
            line,
        )

        if ma:
            asset_name = ma.group(1).strip()
            ticker = ma.group(2)
            trans_type = "Purchase" if ma.group(3) == "P" else "Sale"
            trans_date = _standardize_date(ma.group(4))
            amount = ma.group(5)
            transactions.append(
                {
                    "ticker": ticker,
                    "asset_description": asset_name + f" ({ticker})",
                    "transaction_type": trans_type,
                    "transaction_date": trans_date,
                    "amount_range": amount,
                }
            )
        elif mb:
            asset_name = re.sub(r"^SP\s+", "", mb.group(1)).strip()
            trans_type = "Purchase" if mb.group(2) == "P" else "Sale"
            trans_date = _standardize_date(mb.group(3))
            amount = mb.group(4)

            # Look for ticker in next 1–2 lines
            ticker = None
            for j in [i + 1, i + 2]:
                if j < len(lines):
                    tm = re.search(r"\(([A-Z]{1,5})\)\s*\[ST\]", lines[j])
                    if tm:
                        ticker = tm.group(1)
                        break

            transactions.append(
                {
                    "ticker": ticker,
                    "asset_description": asset_name,
                    "transaction_type": trans_type,
                    "transaction_date": trans_date,
                    "amount_range": amount,
                }
            )

    # Deduplicate (member + spouse ownership creates duplicate rows)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for t in transactions:
        key = (t["ticker"], t["transaction_type"], t["transaction_date"])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique


# ── House Fetcher ─────────────────────────────────────────────────────────────

def fetch_house_ptr_filings(
    days_back: int = 7,
    parse_pdfs: bool = True,
    year: Optional[int] = None,
) -> list[dict]:
    """
    Fetch House PTR filing metadata from the Clerk XML index.
    Optionally downloads and parses digital PDFs for transaction detail.

    Args:
        days_back:   Only include filings dated within this many days.
        parse_pdfs:  If True, download + parse digital PDFs for ticker/amount data.
        year:        Override year (default: current year).

    Returns list of dicts. Each dict has at minimum:
        source, politician, party, state, district, filing_date, filing_url
    If parse_pdfs=True and the filing is digital, also adds:
        ticker, asset_description, transaction_type, transaction_date, amount_range
    """
    if year is None:
        year = datetime.now().year
    cutoff = datetime.now() - timedelta(days=days_back)

    xml_url = HOUSE_XML_URL.format(year=year)
    _eprint(f"[House] Fetching XML index for {year}: {xml_url}")

    sess = _session()
    try:
        resp = sess.get(xml_url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        _eprint(f"[House] ERROR fetching XML: {e}")
        return []

    content = resp.content
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]  # Strip UTF-8 BOM

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        _eprint(f"[House] ERROR parsing XML: {e}")
        return []

    members = root.findall("Member")
    _eprint(f"[House] Total filings in index: {len(members)}")

    # Filter PTRs (FilingType=P) within date window
    results: list[dict] = []
    ptr_count = 0

    for m in members:
        filing_type = m.findtext("FilingType", "").strip()
        if filing_type != "P":
            continue

        ptr_count += 1
        filing_date_raw = m.findtext("FilingDate", "").strip()
        filing_date = _parse_date_mdy(filing_date_raw)
        if filing_date is None or filing_date < cutoff:
            continue

        last = m.findtext("Last", "").strip()
        first = m.findtext("First", "").strip()
        state_dst = m.findtext("StateDst", "").strip()
        doc_id = m.findtext("DocID", "").strip()
        filing_year = m.findtext("Year", str(year)).strip()

        state = _state_from_district(state_dst)
        politician = f"{first} {last}".strip()
        doc_id_int = int(doc_id) if doc_id.isdigit() else 0
        is_digital = doc_id_int >= DIGITAL_DOCTYPE_THRESHOLD

        pdf_url = HOUSE_PDF_URL.format(year=filing_year, doc_id=doc_id)
        filing_date_str = _standardize_date(filing_date_raw)

        base_record = {
            "source": "house",
            "politician": politician,
            "party": None,       # Not in XML; caller enriches from registry
            "state": state,
            "district": state_dst,
            "filing_date": filing_date_str,
            "transaction_date": None,
            "ticker": None,
            "asset_description": None,
            "transaction_type": None,
            "amount_range": None,
            "filing_url": pdf_url,
            "doc_id": doc_id,
            "is_digital": is_digital,
        }

        if parse_pdfs and is_digital:
            _eprint(f"  [House] Parsing PDF for {politician} (DocID={doc_id})…")
            try:
                pdf_resp = sess.get(pdf_url, timeout=30)
                pdf_resp.raise_for_status()
                txns = _parse_house_ptr_pdf(pdf_resp.content)
            except requests.RequestException as e:
                _eprint(f"  [House] PDF download error: {e}")
                txns = []
            time.sleep(0.5)  # polite rate limiting

            if txns:
                for txn in txns:
                    row = base_record.copy()
                    row.update(
                        {
                            "ticker": txn["ticker"],
                            "asset_description": txn["asset_description"],
                            "transaction_type": txn["transaction_type"],
                            "transaction_date": txn["transaction_date"] or filing_date_str,
                            "amount_range": txn["amount_range"],
                        }
                    )
                    results.append(row)
            else:
                # No parsed transactions (scanned or empty) — keep filing-level record
                results.append(base_record)
        else:
            results.append(base_record)

    _eprint(f"[House] PTR filings in XML: {ptr_count}; in date window: {len(results)}")
    return results


# ── Senate Fetcher ────────────────────────────────────────────────────────────

def _senate_efd_session() -> tuple[requests.Session, str]:
    """
    Establish a Senate eFD session by accepting the prohibition agreement.
    Returns (session, csrf_token) or (session, '') on failure.
    """
    sess = _session()
    sess.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    try:
        r = sess.get(SENATE_HOME_URL, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        _eprint(f"[Senate] ERROR loading home page: {e}")
        return sess, ""

    m = re.search(r'csrfmiddlewaretoken" value="([^"]+)"', r.text)
    csrf = m.group(1) if m else sess.cookies.get("csrftoken", "")

    time.sleep(1)
    try:
        r2 = sess.post(
            SENATE_HOME_URL,
            data={"csrfmiddlewaretoken": csrf, "prohibition_agreement": "1"},
            headers={
                "Referer": SENATE_HOME_URL,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://efdsearch.senate.gov",
            },
            timeout=15,
        )
        r2.raise_for_status()
        _eprint(f"[Senate] Agreement accepted → {r2.url}")
    except requests.RequestException as e:
        _eprint(f"[Senate] ERROR submitting agreement: {e}")
        return sess, ""

    csrf2 = sess.cookies.get("csrftoken", csrf)
    return sess, csrf2


def _fetch_senate_s3(days_back: int) -> list[dict]:
    """
    Fetch Senate PTR trades from the community S3 aggregate JSON.

    The senate-stock-watcher S3 bucket is updated daily and has no WAF.
    Each record has: transaction_date, ticker, asset_description, type,
                     amount, senator, party, state, disclosure_date, etc.
    Returns list of dicts in congress_watcher canonical format.
    """
    cutoff = datetime.now() - timedelta(days=days_back)
    sess = _session()

    _eprint(f"[Senate] Trying S3 community aggregate: {SENATE_S3_URL}")
    try:
        r = sess.get(SENATE_S3_URL, timeout=30)
        r.raise_for_status()
        raw = r.json()
    except Exception as exc:
        _eprint(f"[Senate] S3 fetch failed: {exc}")
        return []

    # The aggregate JSON is a list of transaction objects
    if not isinstance(raw, list):
        _eprint("[Senate] S3 returned unexpected format (not a list)")
        return []

    results: list[dict] = []
    for rec in raw:
        # Parse disclosure date for window filter
        disc_str = rec.get("disclosure_date") or rec.get("date_received") or ""
        disc_date = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                disc_date = datetime.strptime(disc_str.strip(), fmt)
                break
            except ValueError:
                pass
        if disc_date is None or disc_date < cutoff:
            continue

        first = rec.get("first_name") or ""
        last = rec.get("last_name") or rec.get("senator") or ""
        politician = f"{first} {last}".strip() if first else last

        tx_date_raw = rec.get("transaction_date") or rec.get("transaction_date_raw") or ""
        tx_date = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                tx_date = datetime.strptime(tx_date_raw.strip(), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass

        tx_type_raw = rec.get("type", "")
        if re.search(r"purchase|buy", tx_type_raw, re.I):
            tx_type = "Purchase"
        elif re.search(r"sale|sell|sold", tx_type_raw, re.I):
            tx_type = "Sale"
        else:
            tx_type = tx_type_raw

        ticker = rec.get("ticker") or None
        asset = rec.get("asset_description") or rec.get("asset") or ""
        amount = rec.get("amount") or rec.get("amount_range") or None

        filing_url = rec.get("ptr_link") or rec.get("filing_url") or ""
        filing_date_str = disc_date.strftime("%Y-%m-%d") if disc_date else disc_str

        results.append({
            "source": "senate",
            "politician": politician,
            "party": rec.get("party"),
            "state": rec.get("state"),
            "district": None,
            "filing_date": filing_date_str,
            "transaction_date": tx_date or filing_date_str,
            "ticker": ticker,
            "asset_description": asset,
            "transaction_type": tx_type,
            "amount_range": amount,
            "filing_url": filing_url,
            "doc_id": None,
            "is_digital": False,
        })

    _eprint(f"[Senate] S3: {len(results)} PTR records in last {days_back} days")
    return results


def fetch_senate_ptr_filings(days_back: int = 7) -> list[dict]:
    """
    Fetch Senate PTR filings.

    Primary: community S3 aggregate (no WAF, updated daily).
    Fallback: efdsearch.senate.gov DataTables API (blocked by Akamai WAF in
    automated environments as of May 2026 — kept for completeness).

    Returns list of dicts (filing-level; no per-transaction detail for eFD path).
    """
    # Try S3 first — no WAF, comprehensive data
    s3_results = _fetch_senate_s3(days_back)
    if s3_results:
        return s3_results

    # Fallback: official eFD (often blocked)
    cutoff = datetime.now() - timedelta(days=days_back)
    start_date = cutoff.strftime("%m/%d/%Y")

    _eprint("[Senate] S3 empty — trying eFD API as fallback…")
    sess, csrf = _senate_efd_session()
    if not csrf:
        _eprint("[Senate] WARN: Could not establish eFD session. Senate data unavailable.")
        return []

    time.sleep(2)

    params = {
        "csrfmiddlewaretoken": csrf,
        "draw": "1",
        "columns[0][data]": "first_name",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "true",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",
        "columns[1][data]": "last_name",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",
        "columns[2][data]": "filer_type",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "true",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",
        "columns[3][data]": "date_received",
        "columns[3][name]": "",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "true",
        "columns[3][search][value]": "",
        "columns[3][search][regex]": "false",
        "columns[4][data]": "link",
        "columns[4][name]": "",
        "columns[4][searchable]": "false",
        "columns[4][orderable]": "false",
        "columns[4][search][value]": "",
        "columns[4][search][regex]": "false",
        "order[0][column]": "3",
        "order[0][dir]": "desc",
        "start": "0",
        "length": "100",
        "search[value]": "",
        "search[regex]": "false",
        "report_types": '["ptr"]',
        "filer_types": '[]',
        "submitted_start_date": start_date,
        "submitted_end_date": "",
        "candidate_state": "",
        "senator_state": "",
        "office_id": "",
        "first_name": "",
        "last_name": "",
    }

    _eprint(f"[Senate] Querying eFD PTR data API (from {start_date})…")
    try:
        r = sess.post(
            SENATE_DATA_URL,
            data=params,
            headers={
                "Referer": "https://efdsearch.senate.gov/search/",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://efdsearch.senate.gov",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            timeout=30,
        )
    except requests.RequestException as e:
        _eprint(f"[Senate] ERROR calling data API: {e}")
        return []

    if r.status_code == 503:
        _eprint("[Senate] HTTP 503 — Akamai WAF blocking eFD. Senate data unavailable.")
        return []

    if r.status_code != 200:
        _eprint(f"[Senate] Unexpected HTTP {r.status_code} from data API")
        return []

    try:
        data = r.json()
    except json.JSONDecodeError as e:
        _eprint(f"[Senate] JSON parse error: {e}")
        return []

    rows = data.get("data", [])
    _eprint(f"[Senate] eFD PTR filings: {data.get('recordsTotal', '?')} total, {len(rows)} returned")

    results: list[dict] = []
    for row in rows:
        if len(row) < 5:
            continue
        link_html = row[0] if isinstance(row[0], str) else str(row[0])
        first_name = row[1] if isinstance(row[1], str) else ""
        last_name = row[2] if isinstance(row[2], str) else ""
        date_received = row[3] if isinstance(row[3], str) else ""

        link_match = re.search(r'href="([^"]+)"', link_html)
        filing_url = ""
        if link_match:
            href = link_match.group(1)
            filing_url = href if href.startswith("http") else "https://efdsearch.senate.gov" + href

        filing_date_str = None
        if date_received:
            try:
                d = datetime.strptime(date_received.strip(), "%m/%d/%Y")
                filing_date_str = d.strftime("%Y-%m-%d")
            except ValueError:
                filing_date_str = date_received

        results.append({
            "source": "senate",
            "politician": f"{first_name} {last_name}".strip(),
            "party": None,
            "state": None,
            "district": None,
            "filing_date": filing_date_str,
            "transaction_date": None,
            "ticker": None,
            "asset_description": None,
            "transaction_type": None,
            "amount_range": None,
            "filing_url": filing_url,
            "doc_id": None,
            "is_digital": False,
        })

    return results


# ── Politician Registry Integration ──────────────────────────────────────────

# Default tracked politicians (can be overridden via get_tracked_politicians())
_DEFAULT_REGISTRY: list[dict] = [
    # House — Smart Money + AI names
    {"name": "Nancy Pelosi",       "chamber": "house",  "party": "D", "state": "CA"},
    {"name": "Michael McCaul",     "chamber": "house",  "party": "R", "state": "TX"},
    {"name": "John McGuire",       "chamber": "house",  "party": "R", "state": "VA"},
    {"name": "Marjorie Taylor Greene", "chamber": "house", "party": "R", "state": "GA"},
    {"name": "Byron Donalds",      "chamber": "house",  "party": "R", "state": "FL"},
    {"name": "Ro Khanna",          "chamber": "house",  "party": "D", "state": "CA"},
    {"name": "Suzan DelBene",      "chamber": "house",  "party": "D", "state": "WA"},
    # Senate
    {"name": "Tommy Tuberville",   "chamber": "senate", "party": "R", "state": "AL"},
    {"name": "Mark Warner",        "chamber": "senate", "party": "D", "state": "VA"},
    {"name": "Richard Burr",       "chamber": "senate", "party": "R", "state": "NC"},
    {"name": "Kelly Loeffler",     "chamber": "senate", "party": "R", "state": "GA"},
    {"name": "Sheldon Whitehouse", "chamber": "senate", "party": "D", "state": "RI"},
]


def get_tracked_politicians() -> list[dict]:
    """Load politician registry from registry.json if available, else use defaults."""
    registry_path = os.path.join(os.path.dirname(__file__), "politician_registry.json")
    if os.path.exists(registry_path):
        try:
            with open(registry_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return _DEFAULT_REGISTRY


def _name_matches(filing_name: str, registry_name: str) -> bool:
    """Fuzzy last-name match. Both names are normalized to lowercase."""
    filing_parts = set(filing_name.lower().split())
    registry_parts = set(registry_name.lower().split())
    # Match if last name matches (handles "Hon. Nancy Pelosi" vs "Nancy Pelosi")
    f_last = filing_name.lower().split()[-1] if filing_name else ""
    r_last = registry_name.lower().split()[-1] if registry_name else ""
    return f_last == r_last and len(f_last) > 2


def enrich_with_registry(
    trades: list[dict],
    registry: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Enrich trade records with party/state from the registry.
    Also sets `is_tracked=True` for matching politicians.
    """
    if registry is None:
        registry = get_tracked_politicians()

    for trade in trades:
        trade["is_tracked"] = False
        for pol in registry:
            if _name_matches(trade["politician"], pol["name"]):
                if trade["party"] is None:
                    trade["party"] = pol.get("party")
                if trade["state"] is None:
                    trade["state"] = pol.get("state")
                if pol.get("chamber", "") == trade.get("source", ""):
                    trade["is_tracked"] = True
                break

    return trades


# ── Main Public API ───────────────────────────────────────────────────────────

def fetch_recent_congress_trades(
    days_back: int = 7,
    parse_pdfs: bool = True,
    include_senate: bool = True,
    include_house: bool = True,
    politician_filter: Optional[list[str]] = None,
) -> list[dict]:
    """
    Returns list of recent Congressional PTR trades from Senate + House.

    Each dict has:
        source:            "senate" or "house"
        politician:        full name
        party:             "D" or "R" (from registry, if available)
        state:             e.g. "CA"
        district:          e.g. "CA17" (House only)
        filing_date:       "YYYY-MM-DD"
        transaction_date:  "YYYY-MM-DD" (from PDF, if available)
        ticker:            e.g. "NVDA" (from PDF parse, may be None)
        asset_description: company name (may be None)
        transaction_type:  "Purchase" or "Sale" (may be None)
        amount_range:      "$1,001 - $15,000" (may be None)
        filing_url:        URL to the PDF filing
        is_tracked:        True if politician is in the registry

    Args:
        days_back:          How many calendar days back to look
        parse_pdfs:         Parse digital PDFs for transaction detail (House only)
        include_senate:     Include Senate PTRs (may fail due to WAF)
        include_house:      Include House PTRs
        politician_filter:  Optional list of politician names to filter to.
                            If None, returns all + marks tracked ones.

    Returns:
        List of dicts, sorted by filing_date descending.
    """
    all_trades: list[dict] = []

    if include_house:
        _eprint(f"[Congress] Fetching House PTRs (last {days_back} days)…")
        house = fetch_house_ptr_filings(days_back=days_back, parse_pdfs=parse_pdfs)
        all_trades.extend(house)
        _eprint(f"[Congress] House PTR records: {len(house)}")

    if include_senate:
        _eprint(f"[Congress] Fetching Senate PTRs (last {days_back} days)…")
        senate = fetch_senate_ptr_filings(days_back=days_back)
        all_trades.extend(senate)
        _eprint(f"[Congress] Senate PTR records: {len(senate)}")

    # Enrich with registry (party, state, is_tracked)
    all_trades = enrich_with_registry(all_trades)

    # Optional filter
    if politician_filter:
        filter_lower = [n.lower() for n in politician_filter]
        all_trades = [
            t
            for t in all_trades
            if any(
                t["politician"].lower().endswith(n.lower().split()[-1])
                for n in politician_filter
            )
        ]

    # Sort by filing_date descending
    def sort_key(t: dict) -> str:
        return t.get("filing_date") or "0000-00-00"

    all_trades.sort(key=sort_key, reverse=True)
    return all_trades


if __name__ == "__main__":
    import sys

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    trades = fetch_recent_congress_trades(days_back=days)
    print(json.dumps(trades, indent=2))
