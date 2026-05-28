#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nvdev_firehose.py — NVIDIA Developer technical-blog firehose (v2 SMART).

每 30 分钟轮询 NVIDIA Developer 博客 Atom 源,对每篇新文章:
1. 用正则启发式抽出所有大写短语(1–4 词)= 候选公司名
2. yfinance.Search(name) → 找美股 equity,做名字重叠校验
3. 命中的写进 ticker cache(正/负都存),以后永不重复查询
4. 用 TRACKED 集合区分"组合内"(高信号 🎯) vs "新发现"(🔍)

→ **不用手工维护 NAME_TO_TICKER**,新公司出现在博文里 = 第一次自动解析、
   永久缓存、以后秒命中。

State:  nvdev_state.json          (已推送过的文章 id, 5k 上限)
Cache:  nvdev_ticker_cache.json   (name → ticker meta, 持久学习)
Env:    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TEST_MODE, NVDEV_USER_AGENT
        MAX_ALERTS (default 8), MAX_LOOKUPS (default 40 per article)
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "nvdev_state.json"
CACHE_FILE = SCRIPT_DIR / "nvdev_ticker_cache.json"
FEED_URL = "https://developer.nvidia.com/blog/feed/"
UA = os.environ.get(
    "NVDEV_USER_AGENT",
    "nvidia-developer-firehose/2.0 (claude-investment-skills)",
)
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"
MAX_BODY = 60_000
MAX_ALERTS_PER_RUN = int(os.environ.get("MAX_ALERTS", "8"))
MAX_LOOKUPS_PER_ARTICLE = int(os.environ.get("MAX_LOOKUPS", "40"))


# ════════════════════════════════════════════════════════════════════════
#  TRACKED — your portfolio universe.  Mentioned in a post = 🎯 high signal.
#  Edit freely; resolution still works for names NOT in this list.
# ════════════════════════════════════════════════════════════════════════
TRACKED_TICKERS: set[str] = {
    # Optical / DSP / interconnect
    "MRVL", "LITE", "COHR", "AAOI", "CRDO", "AVGO", "ALAB", "MTSI", "APH",
    # Power semis / 800V HVDC partners
    "NVDA", "NVTS", "MPWR", "VICR", "POWI", "ON", "TXN", "STM", "IFNNY",
    # AI semis / foundries
    "AMD", "INTC", "ARM", "TSM", "GFS", "TSEM", "MU",
    # Networking / system / server
    "ANET", "CSCO", "JNPR", "DELL", "SMCI", "HPE",
    # Hyperscalers + neoclouds
    "MSFT", "AMZN", "GOOGL", "META", "ORCL", "AAPL", "CRWV", "NBIS",
    # Power / EPC / cooling
    "VRT", "ETN", "MOD", "NVT", "HUBB", "POWL", "STRL", "MTZ", "PWR",
    "PRIM", "GNRC", "SBGSY", "SBGSF",
    # Power generation
    "CEG", "VST", "TLN", "GEV", "BE", "CMI", "AEP", "D",
    # Auto / SDV / robotics
    "TSLA", "MBLY",
}


# ════════════════════════════════════════════════════════════════════════
#  ALIAS — only for ambiguous SHORT tokens; expand to full name for lookup.
#  Most names don't need an entry — yfinance.Search resolves them directly.
# ════════════════════════════════════════════════════════════════════════
ALIAS: dict[str, str] = {
    "MPS": "Monolithic Power Systems",
    "TI": "Texas Instruments",
    "TSMC": "Taiwan Semiconductor Manufacturing",
    "AMD": "Advanced Micro Devices",
    "HPE": "Hewlett Packard Enterprise",
    "STMicro": "STMicroelectronics",
    "STMicroelectronics": "STMicroelectronics",
    "Onsemi": "ON Semiconductor",
    "onsemi": "ON Semiconductor",
    "Arm": "Arm Holdings",
    "AWS": "Amazon",
    "GCP": "Alphabet",
    "Azure": "Microsoft",
}


# Common false-positive caps in tech writing.  Lowercase keys.
STOPWORDS: set[str] = {
    # NVIDIA itself + products / brands / architectures
    "nvidia", "nvidia developer", "nvidia technical blog",
    "cuda", "tensorrt", "nim", "triton", "rapids", "nemo", "omniverse",
    "dgx", "hgx", "mgx", "grace", "hopper", "blackwell", "rubin",
    "kepler", "ampere", "ada lovelace", "fermi", "turing", "pascal", "volta",
    "geforce", "rtx", "gtx", "tegra", "jetson", "drive", "spectrum",
    "nvlink", "infiniband", "mellanox", "bluefield", "connectx",
    "magnum", "isaac", "metropolis", "clara", "merlin", "morpheus",
    # Tech / generic
    "ai", "ml", "llm", "gpu", "cpu", "tpu", "npu", "asic", "fpga", "rag",
    "api", "sdk", "http", "json", "yaml", "xml", "csv", "rest", "grpc",
    "linux", "windows", "macos", "ubuntu", "debian", "kubernetes", "docker",
    "pytorch", "tensorflow", "jax", "hugging face", "open source",
    "machine learning", "deep learning", "neural network", "natural language",
    "supervised learning", "reinforcement learning", "computer vision",
    "github", "gitlab", "bitbucket",
    # Conferences / journals
    "gtc", "siggraph", "supercomputing", "isc", "neurips", "icml", "cvpr",
    # Corporate generics
    "inc", "ltd", "corp", "corporation", "company", "limited", "group",
    "technology", "technologies", "systems", "solutions", "platform",
    "the company", "the model", "the data", "the system", "the team",
    # Calendar
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    # Document structure / writing
    "figure", "table", "step", "example", "tutorial", "blog", "post",
    "notebook", "model", "data", "code", "image", "video", "audio",
    "user", "users", "developer", "developers", "researcher", "researchers",
    "scientist", "engineer", "scientists", "engineers",
    "first", "second", "third", "fourth", "fifth",
    # Geo
    "united states", "europe", "asia", "china", "japan", "korea",
    "north america", "south korea", "taiwan", "india", "germany",
    # Misc that show up capitalized in tech writing
    "new", "next", "previous", "however", "therefore", "additionally",
    "with", "using", "via", "from", "and", "or", "but", "for",
}

US_EXCHANGES = {"NMS", "NYQ", "NGM", "ASE", "PCX", "BTS",     # primary US
                "PNK", "OTC", "OQX", "OQB", "OQS"}             # OTC tiers (ADRs)


# ── feed ────────────────────────────────────────────────────────────────
def fetch_feed() -> str:
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def parse_atom(xml: str) -> list[dict]:
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    out: list[dict] = []
    for e in entries:
        def t(tag: str) -> str:
            m = re.search(f"<{tag}[^>]*>(.*?)</{tag}>", e, re.DOTALL)
            if not m:
                return ""
            v = m.group(1).strip()
            v = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", v, flags=re.DOTALL)
            return html.unescape(v).strip()

        link_m = re.search(r'<link[^>]+rel="alternate"[^>]*href="([^"]+)"', e)
        link = link_m.group(1) if link_m else ""
        a_m = re.search(r"<author>.*?<name>(.*?)</name>.*?</author>", e, re.DOTALL)
        author = a_m.group(1).strip() if a_m else ""
        out.append({
            "id":      t("id") or link,
            "title":   re.sub(r"<[^>]+>", "", t("title")),
            "link":    link,
            "author":  author,
            "updated": t("updated") or t("published"),
            "summary": re.sub(r"<[^>]+>", " ", t("summary"))[:500],
        })
    return out


def fetch_article(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception as exc:
        print(f"[WARN] fetch {url}: {exc}", file=sys.stderr)
        return ""
    m = re.search(r"<article[^>]*>(.*?)</article>", h, re.DOTALL)
    body = m.group(1) if m else h
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.DOTALL | re.I)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.DOTALL | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return re.sub(r"\s+", " ", body)[:MAX_BODY]


# ── smart name extraction ──────────────────────────────────────────────
# Capitalized 1–4 word phrases.  Allows dot, &, hyphen inside words.
_CAND_PAT = re.compile(
    r"\b([A-Z][a-zA-Z0-9.&\-]{1,30}(?:\s+[A-Z][a-zA-Z0-9.&\-]{1,30}){0,3})\b"
)


def extract_candidates(text: str) -> list[tuple[str, int]]:
    """Return [(candidate, freq)] of capitalized phrases that *look* like org
    names, deduped + ordered by frequency desc."""
    text = re.sub(r"https?://\S+", " ", text)
    # Insert spaces around sentence punctuation so "Vertiv. NVIDIA" doesn't
    # glue into one candidate.
    text = re.sub(r"([.!?;:,])", r" \1 ", text)
    freq: dict[str, int] = {}
    for m in _CAND_PAT.finditer(text):
        c = m.group(1).strip().rstrip(".")
        if c.lower().startswith("the "):
            c = c[4:]
        if len(c) < 3:
            continue
        if c.lower() in STOPWORDS:
            continue
        # Don't reject all-cap acronyms here — TSMC, GFS, MPS are legit
        # company tickers. yfinance.Search is the arbiter; negative caching
        # handles the false positives.
        freq[c] = freq.get(c, 0) + 1
    return sorted(freq.items(), key=lambda x: -x[1])


# ── ticker resolution ──────────────────────────────────────────────────
def _name_overlap(query: str, candidate: str) -> bool:
    """At least one significant word (>3 chars) shared between the search
    name and the canonical company name yfinance returned."""
    q = {w for w in re.split(r"\W+", query.lower()) if len(w) > 3}
    c = {w for w in re.split(r"\W+", candidate.lower()) if len(w) > 3}
    return bool(q & c) if q else True


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.load(open(CACHE_FILE))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    if not TEST_MODE:
        json.dump(cache, open(CACHE_FILE, "w"), indent=2, sort_keys=True,
                  ensure_ascii=False)


def resolve_ticker(name: str, cache: dict) -> dict | None:
    """name → {'ticker','exchange','name','source'} or None.  Hits cache
    first; on miss calls yfinance.Search and writes back (positive OR
    negative).  Negative caching prevents re-looking up junk."""
    key = name.lower().strip()
    if key in cache:
        return cache[key]
    lookup_name = ALIAS.get(name, name)
    try:
        import yfinance as yf
        results = yf.Search(lookup_name, max_results=5).quotes or []
    except Exception as exc:
        print(f"[WARN] yfinance.Search('{lookup_name}'): {exc}", file=sys.stderr)
        cache[key] = None
        return None
    for q in results:
        if q.get("quoteType") != "EQUITY":
            continue
        exch = q.get("exchange", "")
        if exch not in US_EXCHANGES:
            continue
        canon_name = q.get("longname") or q.get("shortname") or ""
        if not _name_overlap(lookup_name, canon_name):
            continue
        result = {
            "ticker":   q["symbol"],
            "exchange": exch,
            "name":     canon_name,
            "source":   "yfinance",
        }
        cache[key] = result
        return result
    cache[key] = None
    return None


def extract_all_mentions(text: str, cache: dict) -> dict[str, dict | None]:
    """Combine heuristic candidates → resolution + bonus (NASDAQ:XXX) catches.
    Caps yfinance lookups per article to MAX_LOOKUPS_PER_ARTICLE."""
    hits: dict[str, dict] = {}
    candidates = extract_candidates(text)
    lookups = 0
    for cand, _freq in candidates:
        key = cand.lower().strip()
        if key in cache:
            if cache[key]:
                hits[cand] = cache[key]
            continue
        if lookups >= MAX_LOOKUPS_PER_ARTICLE:
            print(f"[INFO] lookup cap {MAX_LOOKUPS_PER_ARTICLE} hit; remaining "
                  f"{len(candidates) - candidates.index((cand,_freq))} skipped",
                  file=sys.stderr)
            break
        r = resolve_ticker(cand, cache)
        lookups += 1
        time.sleep(0.15)  # gentle to Yahoo
        if r:
            hits[cand] = r
    # Bonus: explicit exchange tags like (NASDAQ: XYZ)
    for m in re.finditer(r"\((?:NASDAQ|NYSE|NSE):\s*([A-Z]{1,6})\)", text):
        sym = m.group(1)
        hits.setdefault(f"(exchange:{sym})",
                        {"ticker": sym, "source": "exchange-tag", "name": ""})
    return hits


# ── alert format ───────────────────────────────────────────────────────
def fmt_alert(item: dict, mentions: dict[str, dict]) -> str:
    tracked = [(n, m) for n, m in mentions.items()
               if m and m["ticker"] in TRACKED_TICKERS]
    other = [(n, m) for n, m in mentions.items()
             if m and m["ticker"] not in TRACKED_TICKERS]
    head = "🟢🟪" if tracked else "🟪"
    lines = [
        f"{head} *NVIDIA Developer — new post*",
        f"*{item['title']}*",
    ]
    if item.get("author"):
        lines.append(f"_作者: {item['author']}_")
    if item.get("updated"):
        lines.append(f"_发布: {item['updated'][:10]}_")
    lines.append("")
    if tracked:
        lines.append("🎯 *组合内标的(高信号):*")
        for n, m in tracked[:12]:
            lines.append(f"  • {n} → `{m['ticker']}`")
    if other:
        if tracked:
            lines.append("")
        lines.append("🔍 *其他识别到的可交易标的:*")
        for n, m in other[:10]:
            nm = m.get("name", "")[:35]
            lines.append(f"  • {n} → `{m['ticker']}`" + (f"  ({nm})" if nm else ""))
    if not mentions:
        lines.append("_未识别到可交易标的 — 文章可能是纯技术教程_")
    lines.append("")
    lines.append(item["link"])
    return "\n".join(lines)


# ── telegram ───────────────────────────────────────────────────────────
def send_telegram(msg: str) -> bool:
    if TEST_MODE:
        print("─── TEST_MODE ───\n" + msg + "\n─── end ───", file=sys.stderr)
        return True
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("[WARN] no Telegram creds, message dropped", file=sys.stderr)
        print(msg, file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat, "text": msg, "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }, timeout=20)
    if r.status_code == 200:
        return True
    r2 = requests.post(url, json={
        "chat_id": chat, "text": msg,
        "disable_web_page_preview": True,
    }, timeout=20)
    return r2.status_code == 200


# ── main ───────────────────────────────────────────────────────────────
def main() -> int:
    state = json.load(open(STATE_FILE)) if STATE_FILE.exists() else {"seen": []}
    cache = _load_cache()
    seen: set[str] = set(state.get("seen", []))
    print(f"[INFO] state={len(seen)} seen, cache={len(cache)} resolved",
          file=sys.stderr)

    try:
        xml = fetch_feed()
    except Exception as exc:
        print(f"[ERR] feed fetch: {exc}", file=sys.stderr)
        return 1

    entries = parse_atom(xml)
    print(f"[INFO] feed: {len(entries)} entries", file=sys.stderr)

    # First run: seed state silently (no Telegram avalanche)
    if not seen:
        for e in entries:
            seen.add(e["id"])
        state["seen"] = sorted(seen)[-5000:]
        state["updated"] = datetime.now(timezone.utc).isoformat()
        if not TEST_MODE:
            json.dump(state, open(STATE_FILE, "w"), indent=2)
        print(f"[INFO] FIRST RUN: seeded {len(seen)} entries silently",
              file=sys.stderr)
        return 0

    new = [e for e in entries if e["id"] not in seen]
    print(f"[INFO] {len(new)} new entries", file=sys.stderr)

    sent = 0
    for e in new[:MAX_ALERTS_PER_RUN]:
        body = fetch_article(e["link"]) if e["link"] else ""
        haystack = " ".join([e["title"], e.get("summary", ""), body])
        mentions = extract_all_mentions(haystack, cache)
        msg = fmt_alert(e, mentions)
        if send_telegram(msg):
            sent += 1
            time.sleep(1)
        seen.add(e["id"])

    if not TEST_MODE:
        state["seen"] = sorted(seen)[-5000:]
        state["updated"] = datetime.now(timezone.utc).isoformat()
        json.dump(state, open(STATE_FILE, "w"), indent=2)
        _save_cache(cache)

    print(f"[DONE] new={len(new)} sent={sent} cache_size={len(cache)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
