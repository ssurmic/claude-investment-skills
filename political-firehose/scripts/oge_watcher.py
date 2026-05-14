"""
oge_watcher.py — OGE Form 278-T monitor and PDF parser for the political-firehose system.

Tracks executive branch officials' stock trades via Periodic Transaction Reports filed
with the U.S. Office of Government Ethics.

Dependencies: requests, pdfplumber, beautifulsoup4
Install: pip install requests pdfplumber beautifulsoup4
"""

import io
import re
import sys
import urllib.request
import urllib.parse

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Date-sorted view of all PAS 278-T filings
OGE_DATE_VIEW = (
    "https://extapps2.oge.gov/201/Presiden.nsf/"
    "PAS+Filings+by+Date?OpenView&Count=500"
)

USER_AGENT = "ssurmiczizhao@gmail.com political-firehose/1.0"

# OGE amount-range category codes -> (min, max, label) in dollars
AMOUNT_RANGES = [
    (1_001,       15_000,     "$1,001 - $15,000"),
    (15_001,      50_000,     "$15,001 - $50,000"),
    (50_001,     100_000,     "$50,001 - $100,000"),
    (100_001,    250_000,     "$100,001 - $250,000"),
    (250_001,    500_000,     "$250,001 - $500,000"),
    (500_001,  1_000_000,     "$500,001 - $1,000,000"),
    (1_000_001, 5_000_000,    "$1,000,001 - $5,000,000"),
    (5_000_001, 25_000_000,   "$5,000,001 - $25,000,000"),
    (25_000_001, 999_999_999, "$25,000,001+"),
]

# Cap to prevent artifact amplification (OCR-merged multi-row amounts)
MAX_OGE_AMOUNT = 25_000_000

# Vertical tolerance (pts) for matching type-word row to date-word row
ROW_TOLERANCE = 10

# Stock name suffixes to strip when extracting short name
STRIP_SUFFIXES = re.compile(
    r"\b(COM|CORP|INC|LTD|LLC|PLC|CO|SA|AG|NV|SE|ETF|FUND|TRUST|SHS|ORD|ADR|"
    r"NEW|CL\s*[A-C]|CLASS\s*[A-C]|COMMON|ORDINARY)\b",
    re.IGNORECASE,
)

# Explicit ticker in parens: "NVIDIA CORP COM (NVDA)" -> "NVDA"
TICKER_PAREN_RE = re.compile(r"[\(\[]\s*([A-Z]{1,5})\s*[\)\]]")

# Date column: OCR-corrupted date strings
DATE_COL_RE = re.compile(
    r"^\d[0-9lL/']{3,}\d{4}'?$"
    r"|^\d{1,2}/\d{1,2}/\d{4}$"
)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# Portal scraper
# ---------------------------------------------------------------------------

def check_oge_new_filings(known_urls: set) -> list:
    """
    Scrape the OGE date-sorted 278-T view; return new filings not in known_urls.

    Each item: {"name": str, "date": str, "url": str, "person": str}
    """
    print("[OGE] Fetching portal filing index...", file=sys.stderr)
    try:
        html = _fetch(OGE_DATE_VIEW).decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[OGE] ERROR fetching portal: {exc}", file=sys.stderr)
        return []

    new_filings = []

    if _BS4_AVAILABLE:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "278" not in a.get_text() and "278" not in href:
                continue
            if "$FILE" not in href and "Transaction" not in a.get_text():
                continue
            if not href.lower().endswith(".pdf") and "$FILE" not in href:
                continue
            full_url = (href if href.startswith("http")
                        else urllib.parse.urljoin(OGE_DATE_VIEW, href))
            if full_url not in known_urls:
                decoded = urllib.parse.unquote(full_url)
                filename = decoded.split("$FILE/")[-1]
                person, date = _parse_filename(filename)
                new_filings.append({"name": filename, "date": date,
                                    "url": full_url, "person": person})
    else:
        for pattern in [
            r'href="([^"]*\$FILE/[^"]*278[^"]*\.pdf[^"]*)"',
            r'href="([^"]*278[Tt]ransaction[^"]*\.pdf[^"]*)"',
        ]:
            for raw_link in re.findall(pattern, html, re.IGNORECASE):
                full_url = (raw_link if raw_link.startswith("http")
                            else urllib.parse.urljoin(OGE_DATE_VIEW, raw_link))
                if full_url not in known_urls:
                    decoded = urllib.parse.unquote(full_url)
                    filename = decoded.split("$FILE/")[-1]
                    person, date = _parse_filename(filename)
                    new_filings.append({"name": filename, "date": date,
                                        "url": full_url, "person": person})

    # Deduplicate
    seen_urls: set = set()
    deduped = []
    for f in new_filings:
        if f["url"] not in seen_urls:
            seen_urls.add(f["url"])
            deduped.append(f)

    msg = (f"[OGE] Found {len(deduped)} new filing(s)."
           if deduped else "[OGE] No new filings.")
    print(msg, file=sys.stderr)
    return deduped


def _parse_filename(filename: str) -> tuple:
    """Extract (person, date) from a 278-T filename."""
    name_part = re.split(r"[-\s]+278", filename)[0]
    person = re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", name_part)).strip()
    # Strip trailing date like "12.05.2025" or "12-05-2025" from person name
    person = re.sub(r"\s+\d{1,2}[.\-]\d{1,2}[.\-]\d{4}\s*$", "", person).strip()
    date_m = re.search(r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})", filename)
    date = (f"{date_m.group(1)}/{date_m.group(2)}/{date_m.group(3)}"
            if date_m else "unknown")
    return person, date


# ---------------------------------------------------------------------------
# Date normalizer
# ---------------------------------------------------------------------------

def normalize_date(s: str) -> str:
    """
    Normalize OCR-corrupted date strings to M/D/YYYY.

    Handles:
        '3/212028'    -> '3/21/2028'   (missing slash)
        '2l20l2028'   -> '2/20/2028'   (OCR 'l' as '/')
        '3/1912026'   -> '3/19/2026'   (fused day+year)
        '112912026'   -> '1/29/2026'   (no slashes at all)
        "3/27/2026'"  -> '3/27/2026'   (trailing apostrophe)
    """
    s = s.strip().rstrip("'`")
    s = re.sub(r"(?<=[0-9])[lL](?=[0-9])", "/", s)  # OCR l -> /

    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

    year_m = re.search(r"(202[0-9])", s)
    if not year_m:
        return s

    year = year_m.group(1)
    before_year = s[: year_m.start()].rstrip("/").strip()

    m = re.match(r"^(\d{1,2})/(\d{1,2})$", before_year)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{year}"

    m = re.match(r"^(\d{1,2})/(\d+)$", before_year)  # M/DDYYYY noise
    if m:
        return f"{m.group(1)}/{m.group(2)[:2]}/{year}"

    digits = re.sub(r"[^0-9]", "", before_year)
    if len(digits) >= 3:
        if len(digits) >= 4:
            month, day = digits[:2], digits[2:4]
        else:
            month, day = digits[0], digits[1:3]
        return f"{month}/{day}/{year}"

    return s


# ---------------------------------------------------------------------------
# Amount parser
# ---------------------------------------------------------------------------

def parse_amount(amount_str: str) -> tuple:
    """
    Parse an OCR-corrupted OGE amount range string.

    Returns (label: str, amount_min: int, amount_max: int).
    """
    s = amount_str.strip()
    s = re.sub(r"[*·–—]", "-", s)
    s = re.sub(r"['\"`‘’“”]", "", s)
    s = re.sub(r"\$", " ", s)

    for _ in range(4):
        s = re.sub(r"\s*[\.,]\s*(?=\d{3}\b)", ",", s)
        s = re.sub(r"([0-9])\s+([0-9]{3})\b", r"\1,\2", s)
    for _ in range(4):
        s = re.sub(r"([0-9]),([0-9]{3})", r"\1\2", s)

    nums = [int(n) for n in re.findall(r"\b(\d+)\b", s) if int(n) >= 1000]
    if not nums:
        nums = [int(n) for n in re.findall(r"\b(\d+)\b", s) if int(n) > 0]
    if not nums:
        return ("Unknown", 0, 0)

    nums = [n for n in nums if n <= MAX_OGE_AMOUNT]
    if not nums:
        return ("Unknown", 0, 0)

    anchor = max(nums)

    for lo, hi, label in AMOUNT_RANGES:
        if lo <= anchor <= hi:
            return (label, lo, hi)

    return (f"${anchor:,}", anchor, anchor)


# ---------------------------------------------------------------------------
# Ticker extractor
# ---------------------------------------------------------------------------

def extract_ticker(description: str) -> str:
    """
    Best-effort ticker/name extraction from an OGE asset description.

    1. Explicit ticker in parens: "NVIDIA CORP COM (NVDA)" -> "NVDA"
    2. Strip bond/fund noise; return first part of company name
    """
    m = TICKER_PAREN_RE.search(description)
    if m:
        return m.group(1).upper()

    cleaned = re.sub(r"^[\d#\.\s*\-\"\']+", "", description)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    first_part = re.split(
        r"\b(DUE|REGS|REG|SENIOR|UNSECURED|NOTES|NOTE|BOND|ETF|FUND|TRUST|"
        r"DISC|DISC\.|FORWARD|SPLIT|UNSOLICITED)\b",
        cleaned,
        flags=re.I,
    )[0].strip()
    first_part = STRIP_SUFFIXES.sub("", first_part).strip()
    return first_part if first_part else description[:20].strip()


# ---------------------------------------------------------------------------
# Word-level classifier helpers
# ---------------------------------------------------------------------------

def _is_type_word(text: str) -> bool:
    """
    Return True if the word looks like a transaction type (Purchase/Sale)
    under heavy OCR corruption.

    Known OCR variants seen in OGE 278-T PDFs:
      Purchase: Purchase, lourchaae, DUrchOSO, l)Urt:NIIO, ourcliao,
                rx,rchase, lourdloao, purdlalo, loorchaso, p:urchase,
                Pu:rchase, etc.
      Sale:     Sale, Sold
    """
    t = text.lower()

    # Sale variants (simple)
    if t.rstrip(".") in ("sale", "sold"):
        return True
    if re.search(r"sal[eo]|sold", t):
        return True

    # Purchase variants — anchor on the 'urch'/'urc'/'urd'/'orch'/'rch' core
    if "urch" in t:
        return True
    if "urc" in t:
        return True
    if "urd" in t:
        return True
    if "orch" in t:
        return True
    if "rch" in t and len(t) > 3:
        return True

    # Colon-substitution variants: u[rn][t:][:h] patterns
    if re.search(r"u[rn][t:][:h]", t):
        return True

    # P + U + noise + C/N + noise + H patterns
    if re.search(r"p[u][a-z\)]{0,3}[cn:][a-z\)]{0,3}[hn]", t):
        return True

    # Generic colon-in-word indicator (OCR artifact, word length > 3)
    if re.search(r"[a-z]:[a-z]", t) and len(t) > 3:
        return True

    return False


def _is_amount_word(text: str) -> bool:
    """
    Return True if the word looks like part of an OGE amount range.

    Accepts:
      - Words starting with $ or digit (e.g. '$1,001', '15,000')
      - Continuation fragments: OCR-split amounts starting with '.' or ','
        followed by 3 digits (e.g. '.000', ',001')
    Rejects:
      - Pure row numbers (< 1000 digits only) unless continuation
      - Words starting with ')' or '-'
    """
    t = text.strip()

    # Primary: starts with $ or digit
    if re.match(r"^[\$\d]", t):
        if t.startswith(")") or t.startswith("-"):
            return False
        digits_only = re.sub(r"[^\d]", "", t)
        if digits_only:
            try:
                if int(digits_only) < 1000:
                    return False
            except ValueError:
                pass
        return True

    # Continuation fragments: '.000', ',001', '.000,001', etc.
    if re.match(r"^[,\.]", t) and re.search(r"\d{3}", t):
        return True

    return False


# ---------------------------------------------------------------------------
# Page parser — word-position-based (handles scanned/OCR'd PDFs)
# ---------------------------------------------------------------------------

def _parse_page(page) -> list:
    """
    Parse one pdfplumber page using word x-position clustering.

    Algorithm:
      1. Extract all words with coordinates.
      2. Identify type-column words (x0 > 430) using _is_type_word().
      3. Identify date-column words (x0 > 490) using DATE_COL_RE.
      4. For each type word, find the closest date word within ROW_TOLERANCE pts.
      5. Collect row words within ±ROW_TOLERANCE of the type word's top.
      6. Amount words: x0 >= date_x0 + 70 (dynamic threshold).
      7. Description words: x0 < type_x0 - 5.
    """
    words = page.extract_words()
    if not words:
        return []

    # Type-column candidates: x0 > 430, recognized as purchase/sale
    type_words = [w for w in words
                  if _is_type_word(w["text"]) and float(w["x0"]) > 430]

    # Date-column candidates: x0 > 490, match date pattern
    date_words = [w for w in words
                  if DATE_COL_RE.match(w["text"]) and float(w["x0"]) > 490]

    # Also try 2-token combinations for split dates (e.g. "3/21" + "2026")
    for i in range(len(words) - 1):
        if float(words[i]["x0"]) > 490:
            combined = words[i]["text"] + words[i + 1]["text"]
            if (DATE_COL_RE.match(combined)
                    and abs(float(words[i + 1]["x0"]) - float(words[i]["x0"])) < 20):
                fake_word = dict(words[i])
                fake_word["text"] = combined
                date_words.append(fake_word)

    if not type_words or not date_words:
        return []

    # Index all words by rounded y-position for fast row lookup
    all_words_by_top: dict = {}
    for w in words:
        t = round(float(w["top"]))
        all_words_by_top.setdefault(t, []).append(w)

    def get_words_near_top(center_top: float, tol: int = ROW_TOLERANCE) -> list:
        result = []
        for t in range(int(center_top) - tol, int(center_top) + tol + 1):
            result.extend(all_words_by_top.get(t, []))
        return result

    transactions = []
    used_date_tops: set = set()

    for tw in sorted(type_words, key=lambda w: float(w["top"])):
        t_top = float(tw["top"])

        # Find the closest date word within ROW_TOLERANCE
        candidates = [
            (dw, abs(float(dw["top"]) - t_top))
            for dw in date_words
            if abs(float(dw["top"]) - t_top) <= ROW_TOLERANCE
        ]
        if not candidates:
            continue

        best_dw, _ = min(candidates, key=lambda x: x[1])
        d_top_key = round(float(best_dw["top"]))

        # Skip if we already processed a transaction at this date row
        if d_top_key in used_date_tops:
            continue
        used_date_tops.add(d_top_key)

        date_str = normalize_date(best_dw["text"])
        date_x0 = float(best_dw["x0"])

        # Gather all words in the same row
        row_words = get_words_near_top(t_top)

        # Amount words: right of date column + 70pt (dynamic per filing)
        amt_threshold = date_x0 + 70
        amt_words = [
            w["text"] for w in row_words
            if float(w["x0"]) >= amt_threshold and _is_amount_word(w["text"])
        ]
        # Deduplicate while preserving order
        seen_amt: set = set()
        unique_amt = []
        for a in amt_words:
            if a not in seen_amt:
                seen_amt.add(a)
                unique_amt.append(a)

        amount_raw = " ".join(unique_amt)
        amount_range, amount_min, amount_max = (
            parse_amount(amount_raw) if unique_amt else ("Unknown", 0, 0)
        )

        # Transaction type
        tx_type = ("Sale"
                   if re.search(r"sale|sold", tw["text"], re.I)
                   else "Purchase")

        # Description: words left of the type column
        type_x0 = float(tw["x0"])
        desc_words_raw = [w for w in row_words if float(w["x0"]) < type_x0 - 5]
        seen_desc: set = set()
        desc_sorted = []
        for w in sorted(desc_words_raw, key=lambda x: float(x["x0"])):
            if w["text"] not in seen_desc:
                seen_desc.add(w["text"])
                desc_sorted.append(w["text"])

        description = " ".join(desc_sorted).strip()
        description = re.sub(r"^[\d]+\s+", "", description).strip()
        description = re.sub(r"^[*\-\"\'.,;:•]+\s*", "", description).strip()

        ticker = extract_ticker(description)

        transactions.append({
            "asset": description,
            "ticker": ticker,
            "date": date_str,
            "type": tx_type,
            "amount_range": amount_range,
            "amount_min": amount_min,
            "amount_max": amount_max,
        })

    return transactions


# ---------------------------------------------------------------------------
# PDF parser — main entry point
# ---------------------------------------------------------------------------

def parse_oge_278t(pdf_url: str) -> list:
    """
    Download and parse a 278-T PDF.

    Uses pdfplumber word-coordinate extraction. Each page is processed by
    _parse_page() which clusters words by x-position to identify the type,
    date, amount, and description columns — resilient to OCR corruption.

    Returns list of transactions:
    {
        "asset": str,
        "ticker": str,
        "date": str,            # M/D/YYYY
        "type": str,            # "Purchase" or "Sale"
        "amount_range": str,
        "amount_min": int,
        "amount_max": int,
    }
    """
    print(f"[OGE] Downloading PDF: {pdf_url}", file=sys.stderr)
    try:
        pdf_bytes = _fetch(pdf_url, timeout=120)
    except Exception as exc:
        print(f"[OGE] ERROR downloading PDF: {exc}", file=sys.stderr)
        return []

    print(f"[OGE]   Downloaded {len(pdf_bytes):,} bytes. Parsing...", file=sys.stderr)

    transactions: list = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total_pages = len(pdf.pages)
        print(f"[OGE]   Total pages: {total_pages}", file=sys.stderr)

        for page_num, page in enumerate(pdf.pages, 1):
            if page_num % 20 == 0 or page_num == total_pages:
                print(f"[OGE]   Page {page_num}/{total_pages}...", file=sys.stderr)

            page_txns = _parse_page(page)
            transactions.extend(page_txns)

    print(f"[OGE]   Extracted {len(transactions):,} transaction(s).", file=sys.stderr)
    return transactions
