#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parsers.py — Extract structured signal from SEC 8-K and SC 13D/13G filings.

从 SEC 8-K 和 SC 13D/13G filing 中提取结构化信号。

═══════════════════════════════════════════════════════════════════════
  FORM PRIMER / 表格科普
═══════════════════════════════════════════════════════════════════════

8-K = "Current Report" — 任何 material event 都必须在 4 个工作日内披露
      "Current Report" — any material event must be disclosed within 4 days

KEY ITEMS WE CARE ABOUT / 我们关注的 Item:
  Item 1.01 = Entry into a Material Definitive Agreement
              进入重大确定性协议 (合伙/JV/客户大单/收购意向书)
  Item 3.02 = Unregistered Sales of Equity Securities (PIPE deals!)
              非注册股票发行 → 这就是 PENG/SGH 的 SK Telecom $200M 入口
  Item 7.01 = Regulation FD Disclosure (often "press release" attached)
              FD 法规披露, 通常附带 press release
  Item 8.01 = Other Events (catch-all but often material)
              其他事项, 兜底但常有干货

SC 13D = Beneficial Ownership > 5% with active intent
         实质性持股 >5% 并有 active intent (战略意图)
SC 13G = Beneficial Ownership > 5% passive (index funds, ETFs)
         实质性持股 >5% passive (指数基金) — 我们较少关注

═══════════════════════════════════════════════════════════════════════
  EDGAR DATA SOURCES / 数据源
═══════════════════════════════════════════════════════════════════════

Atom feeds (公开、免费、无 API key):
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom&count=100
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+13D&output=atom&count=40

Filing index page lists all documents in a filing (multiple .htm / .xml files).
We must:
  1. Fetch index page
  2. Identify the primary 8-K document (usually first .htm)
  3. Identify exhibit 99.1 (press release with $$ details)
  4. Combine text and run regex
我们必须从 filing index 找主文档 + 附件 99.1 (press release 含金额细节)。

SEC rate-limit: 10 req/sec. We add 0.15s sleep between requests.
SEC 限速 10 req/sec, 我们每请求间隔 0.15 秒。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

# ─── Constants / 常量 ────────────────────────────────────────────────────

# 8-K Items we treat as "potentially material partnership signals"
# 我们认为可能是 partnership 信号的 8-K Item
KEY_8K_ITEMS: set[str] = {
    "1.01",  # Material Definitive Agreement (M&A, JV, big customer contracts)
    "3.02",  # Unregistered Sales of Equity Securities (PIPE deals)
    "7.01",  # Reg FD Disclosure (press releases get attached here)
    "8.01",  # Other Events (catch-all, often material)
}

# Atom namespace used in EDGAR feeds
# EDGAR atom feed 命名空间
ATOM_NS: dict[str, str] = {"a": "http://www.w3.org/2005/Atom"}

# ─── Regex patterns / 正则模式 ───────────────────────────────────────────

# Extract 8-K Item numbers from cover page
# 提取 8-K 封面 Item 编号
# Matches: "Item 1.01", "ITEM 3.02", "Item  8.01" (multi-space)
_RX_ITEMS = re.compile(r"Item\s+(\d+\.\d+)", re.IGNORECASE)

# Extract dollar amounts in millions/billions
# 提取美元金额 (million/billion 单位)
# Matches: "$200 million", "$1.5 billion", "$50.0M", "USD 200 million"
# Note: we capture (amount, unit) pairs
_RX_DOLLAR = re.compile(
    r"""
    (?:\$|USD\s*)        # $ or USD prefix
    (\d{1,4}(?:,\d{3})*  # integer part with optional commas
        (?:\.\d{1,2})?)  # optional decimals
    \s*                  # whitespace
    (million|billion|M\b|B\b)  # unit (note \b on M/B to avoid "MA", "BMW")
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Extract conversion price for preferred → common conversion
# 提取 preferred 转 common 的 conversion price
# Matches: "conversion price of $32.81", "at $32.81 per share"
_RX_CONVERSION = re.compile(
    r"conversion\s+price\s+of\s+\$(\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Extract issuer ticker from 8-K cover page
# Matches: "Common Stock, $0.001 par value per share | NVDA | The Nasdaq..."
# OR XBRL: <dei:TradingSymbol>NVDA</dei:TradingSymbol>
_RX_TICKER_XBRL = re.compile(
    r"<dei:TradingSymbol[^>]*>([A-Z][A-Z0-9.\-]{0,5})</dei:TradingSymbol>",
    re.IGNORECASE,
)
_RX_TICKER_INLINE = re.compile(
    r"Trading\s+Symbol[\s:|]*([A-Z][A-Z0-9.\-]{0,5})",
    re.IGNORECASE,
)

# Detect deal type from text content
# 从文本判定 deal type
_DEAL_TYPE_KEYWORDS: list[tuple[str, re.Pattern]] = [
    ("PIPE (Preferred)",
        re.compile(r"\b(?:convertible\s+)?preferred\s+(?:stock|shares|equity)\b", re.I)),
    ("PIPE (Common)",
        re.compile(r"\b(?:private\s+placement|PIPE|unregistered\s+sale)\b", re.I)),
    ("Joint Venture",
        re.compile(r"\b(?:joint\s+venture|JV\s+agreement)\b", re.I)),
    ("Joint Development",
        re.compile(r"\bjoint\s+development\s+agreement\b", re.I)),
    ("Strategic Partnership",
        re.compile(r"\bstrategic\s+(?:partnership|collaboration|alliance)\b", re.I)),
    ("Master Supply Agreement",
        re.compile(r"\bmaster\s+(?:supply|services?|purchase)\s+agreement\b", re.I)),
    ("Long-Term Supply",
        re.compile(r"\blong[- ]term\s+supply\s+agreement\b", re.I)),
    ("Licensing Agreement",
        re.compile(r"\b(?:patent\s+)?licens(?:e|ing)\s+agreement\b", re.I)),
]

# Filter OUT noise items (routine corporate events, not interesting)
# 过滤掉 routine 事件 (高管变动、利息支付等) — 8-K 大部分是这种垃圾
_NOISE_PATTERNS: list[re.Pattern] = [
    # Item 5.02 only: officer/director appointment/departure
    re.compile(r"^Item\s+5\.02\s+(?:Departure|Appointment)", re.I | re.M),
    # Item 5.07: shareholder vote results
    re.compile(r"^Item\s+5\.07", re.I | re.M),
    # Item 2.02 only: earnings release (we have other tools for earnings)
    re.compile(r"^Item\s+2\.02\s+Results\s+of\s+Operations", re.I | re.M),
]


# ─── Data classes / 数据类 ──────────────────────────────────────────────

@dataclass
class FilingMeta:
    """Metadata about a SEC filing from the EDGAR atom feed."""
    accession: str          # SEC accession number (unique ID)
    form_type: str          # "8-K", "SC 13D", "6-K", "Form D", etc.
    link: str               # URL to filing index page
    title: str              # "8-K - NVIDIA CORPORATION (0001045810) (Filer)"
    updated: str            # ISO timestamp
    cik: str = ""           # 10-digit CIK (extracted from title)
    company_name: str = ""  # Filer/issuer name parsed from title


@dataclass
class PartnerSignal:
    """A high-signal strategic-partner filing match."""
    ticker: str
    company_name: str
    form_type: str
    items: list[str] = field(default_factory=list)  # 8-K Items
    investors: list[tuple[str, str]] = field(default_factory=list)  # (tier, canonical)
    amount_usd_m: float = 0.0           # Max dollar amount mentioned (in millions)
    conversion_price: Optional[float] = None  # For PIPE deals
    deal_type: str = "Unknown"
    filing_link: str = ""
    accession: str = ""
    # v2.4: theme classification (catches anonymous-customer signals)
    # v2.4: 题材分类 (抓匿名客户信号)
    theme_score: int = 0                # 0-10 from classifier.py
    theme_primary: str = "None"          # "AI Data Center", "Hyperscaler Contract", ...
    theme_categories: dict = field(default_factory=dict)  # raw category hits


# ─── Parsing functions / 解析函数 ───────────────────────────────────────

def parse_atom_feed(xml_text: str) -> list[FilingMeta]:
    """
    Parse the SEC EDGAR atom feed into FilingMeta records.
    解析 SEC EDGAR atom feed.

    Args:
        xml_text: Raw atom XML from `?action=getcurrent&type=8-K&output=atom`

    Returns:
        List of FilingMeta, one per <entry> in the feed.

    Raises:
        ET.ParseError if XML is malformed (caller should catch + retry).
    """
    root = ET.fromstring(xml_text)
    results: list[FilingMeta] = []

    for entry in root.findall("a:entry", ATOM_NS):
        title_el = entry.find("a:title", ATOM_NS)
        link_el = entry.find("a:link", ATOM_NS)
        id_el = entry.find("a:id", ATOM_NS)
        updated_el = entry.find("a:updated", ATOM_NS)

        # Skip entries missing critical fields
        # 缺关键字段的 entry 跳过
        if any(el is None for el in (title_el, link_el, id_el)):
            continue

        # ID format: "urn:tag:sec.gov,2008:accession-number=0001045810-26-..."
        accession = (id_el.text or "").split("=")[-1]
        if not accession:
            continue

        title = title_el.text or ""

        # Detect form type from title (atom feeds tag each entry with its form).
        # 从 title 推断 form type. Title format: "<FORM> - <NAME> (CIK) (role)".
        form_prefix = title.split(" - ", 1)[0].strip().upper() if " - " in title else ""
        form_type = "8-K"
        if "13D" in title.upper():
            form_type = "SC 13D"
        elif "13G" in title.upper():
            form_type = "SC 13G"
        elif form_prefix.startswith("6-K"):
            form_type = "6-K"
        elif form_prefix == "D" or form_prefix.startswith("D/A"):
            form_type = "Form D"  # private placement / exempt offering

        # Extract CIK from title like "8-K - NVIDIA CORP (0001045810) (Filer)"
        # 从 title 抽取 10 位 CIK
        cik = ""
        cik_match = re.search(r"\((\d{10})\)", title)
        if cik_match:
            cik = cik_match.group(1)

        # Extract filer/issuer name: text between "<FORM> - " and " (CIK)"
        # 抽取申报方/发行方名字 (Form D 没 ticker, 靠名字匹配 registry)
        company_name = ""
        name_match = re.search(r"-\s+(.+?)\s+\(\d{10}\)", title)
        if name_match:
            company_name = name_match.group(1).strip()

        results.append(FilingMeta(
            accession=accession,
            form_type=form_type,
            link=link_el.get("href") or "",
            title=title,
            updated=updated_el.text if updated_el is not None else "",
            cik=cik,
            company_name=company_name,
        ))

    return results


def is_noise_filing(text: str) -> bool:
    """
    Return True if this 8-K appears to be a routine non-partnership filing.
    判断这个 8-K 是否是 routine 垃圾 (高管变动、shareholder vote 等).

    We use this to short-circuit expensive downstream processing on the
    common case of "Item 5.02 — CEO departure".
    用来短路常见的 "高管离职" 等垃圾, 节省下游处理成本。
    """
    if not text:
        return True

    # Strategy: if ONLY noise items are present (no key items), it's noise.
    # 策略: 如果只有 noise items 而没有 key items, 就是垃圾。
    items = set(_RX_ITEMS.findall(text))
    if not items:
        return True  # No items disclosed = malformed/empty

    # If any KEY item is present, NOT noise (worth analyzing)
    # 任何 KEY item 在 → 值得分析
    if items & KEY_8K_ITEMS:
        return False

    # Only noise items
    return True


def extract_items(text: str) -> list[str]:
    """Extract all 8-K Item numbers from text. / 提取所有 Item 编号。"""
    items = sorted(set(_RX_ITEMS.findall(text)))
    return items


def extract_max_amount_usd_m(text: str) -> float:
    """
    Extract the LARGEST USD amount mentioned, normalized to millions.
    提取文本中提到的最大美元金额, 标准化到 millions.

    Returns 0.0 if no amount found.

    Examples:
        "$200 million" → 200.0
        "$1.5 billion" → 1500.0
        "$50M" → 50.0
        "$2,000 million" → 2000.0
    """
    if not text:
        return 0.0

    max_m = 0.0
    for amount_str, unit in _RX_DOLLAR.findall(text):
        # Strip commas: "2,000" → "2000"
        try:
            amount = float(amount_str.replace(",", ""))
        except ValueError:
            continue

        unit_lower = unit.lower()
        if unit_lower.startswith("b"):
            amount *= 1000  # billion → million
        # else million stays as is

        # Filter out obvious noise: amounts > $1 trillion = parsing error
        # 过滤明显错误: > $1T 多半是抓错
        if amount > 1_000_000:
            continue

        max_m = max(max_m, amount)

    return max_m


def extract_conversion_price(text: str) -> Optional[float]:
    """
    Extract conversion price for PIPE preferred shares.
    提取 PIPE preferred 转换价格。

    Returns None if not found (most filings won't have this).
    """
    if not text:
        return None
    match = _RX_CONVERSION.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_ticker(text: str) -> str:
    """
    Extract the issuer's ticker symbol from 8-K cover page or XBRL.
    从 8-K 封面或 XBRL 提取 ticker.

    Returns "" if not found.
    """
    if not text:
        return ""

    # Try XBRL first (more reliable, machine-readable)
    # 先试 XBRL (机器可读, 最准)
    m = _RX_TICKER_XBRL.search(text)
    if m:
        return m.group(1).upper()

    # Fall back to inline "Trading Symbol: XXXX"
    m = _RX_TICKER_INLINE.search(text)
    if m:
        candidate = m.group(1).upper()
        # Filter common false positives (column headers, etc.)
        # 过滤常见误识别 (表格列名等)
        if candidate not in {"NONE", "N/A", "TICKER", "SYMBOL"}:
            return candidate

    return ""


def detect_deal_type(text: str) -> str:
    """
    Classify the deal type from text content.
    分类 deal type.

    Returns "Unknown" if no pattern matches.

    Order matters: more specific patterns first.
    顺序重要: 更具体的模式先匹配。
    """
    if not text:
        return "Unknown"

    for label, pattern in _DEAL_TYPE_KEYWORDS:
        if pattern.search(text):
            return label

    return "Unknown"


def parse_13d_filer_and_issuer(text: str) -> tuple[str, str]:
    """
    Parse SC 13D for the FILER (the strategic investor) and ISSUER (target).
    解析 SC 13D 找出 filer (战略投资人) 和 issuer (被投公司).

    Returns (filer_name, issuer_name). Empty strings if not found.

    SC 13D structure has these key fields:
      - "Name of Filing Person" or in cover page header
      - "Name of Issuer" on cover page
    SC 13D 有两个关键字段: Filing Person (投资人) 和 Issuer (被投).
    """
    if not text:
        return ("", "")

    # Issuer is typically on cover page after "Name of Issuer:" or in header
    # Issuer 通常在封面 "Name of Issuer:" 后
    issuer = ""
    issuer_match = re.search(
        r"Name\s+of\s+Issuer[:\s]+([A-Z][A-Za-z0-9 \.,&\-]{2,80})",
        text,
    )
    if issuer_match:
        issuer = issuer_match.group(1).strip()

    # Filer name has multiple possible labels
    filer = ""
    for label in [
        r"Name\s+of\s+(?:Reporting|Filing)\s+Person[s]?[:\s]+",
        r"Reporting\s+Person[s]?\s+name[:\s]+",
    ]:
        filer_match = re.search(
            label + r"([A-Z][A-Za-z0-9 \.,&\-]{2,80})",
            text,
        )
        if filer_match:
            filer = filer_match.group(1).strip()
            break

    return (filer, issuer)
