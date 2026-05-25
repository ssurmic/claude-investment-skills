#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pr_wire.py — Press-release wire poller (the FASTEST signal — beats the 8-K).

新闻稿 wire 轮询器 —— 最快的信号, 经常比 8-K 早几秒到几分钟.

═══════════════════════════════════════════════════════════════════════
  WHY / 为什么
═══════════════════════════════════════════════════════════════════════

A strategic deal usually hits the PR wire (BusinessWire/GlobeNewswire) and
the company's own newsroom the INSTANT it's announced — often seconds before
the matching 8-K is disseminated by EDGAR. For the absolute earliest read on
"NVIDIA invests in X" / "AMD partners with Y" / a hyperscaler order, the
newsroom RSS is the edge.

战略交易通常在 EDGAR 8-K 之前几秒~几分钟就上了 PR wire 和公司 newsroom.
要抢最早的"NVDA 投了谁 / AMD 和谁合作 / hyperscaler 下单", 盯 newsroom RSS.

═══════════════════════════════════════════════════════════════════════
  FEEDS / 数据源
═══════════════════════════════════════════════════════════════════════

  TARGETED  = a specific company's own newsroom (NVDA/AMD). Every new item is
              high-signal → alert on all.
  BROAD     = a wide wire (GlobeNewswire public companies). High volume →
              only alert when title/summary matches the strategic-investor
              registry OR an AI-infrastructure keyword.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TEST_MODE
"""
from __future__ import annotations

import os
import re
import sys
import json
import time
import html
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "pr_wire_state.json"

# Reuse the strategic-investor registry (cross-skill, like partner_firehose).
# 复用战略投资人 registry.
_PARTNER_SCRIPTS = SCRIPT_DIR.parent.parent / "strategic-partner-firehose" / "scripts"
if _PARTNER_SCRIPTS.exists():
    sys.path.insert(0, str(_PARTNER_SCRIPTS))
try:
    from investor_registry import find_strategic_investors, TIER_EMOJI  # noqa: E402
except ImportError:
    def find_strategic_investors(_):  # type: ignore
        return []
    TIER_EMOJI = {}  # type: ignore

USER_AGENT = os.environ.get(
    "PR_WIRE_USER_AGENT", "ssurmiczizhao@gmail.com pr-wire-firehose/1.0")
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
TEST_MODE = os.environ.get("TEST_MODE", "") == "1"

# (source_label, url, mode). mode = "targeted" (alert all) | "broad" (filter)
# 加 feed 就在这里加一行. targeted=全推, broad=匹配才推.
FEEDS: list[tuple[str, str, str]] = [
    ("NVIDIA Newsroom", "https://nvidianews.nvidia.com/releases.xml", "targeted"),
    ("AMD Newsroom", "https://ir.amd.com/news-events/press-releases/rss", "targeted"),
    ("GlobeNewswire (public cos)",
     "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/"
     "GlobeNewswire%20-%20News%20about%20Public%20Companies", "broad"),
]

# AI-infrastructure keywords for filtering BROAD feeds.
# 宽 feed 用的 AI 基建关键词 — 命中才推, 否则太吵.
_AI_KEYWORDS = re.compile(
    r"\b(artificial intelligence|\bA\.?I\.?\b|data ?center|GPU|accelerat|"
    r"\bHBM\b|advanced packaging|co-?packaged optic|liquid cool|800\s?V|"
    r"1\.6\s?T|hyperscal|neocloud|inference|training cluster|supercomputer|"
    r"silicon photonic|CoWoS|NVLink|InfiniBand|Ethernet fabric|"
    r"foundry|wafer|transformer shortage|switchgear|substation)\b",
    re.IGNORECASE,
)


def load_state() -> set[str]:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()).get("seen", []))
        except Exception:
            pass
    return set()


def save_state(seen: set[str]) -> None:
    seen_list = list(seen)
    if len(seen_list) > 5000:
        seen_list = seen_list[-5000:]
    STATE_FILE.write_text(json.dumps(
        {"seen": seen_list, "updated": datetime.now(timezone.utc).isoformat()},
        indent=2) + "\n")


def _txt(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_feed(xml_text: str) -> list[dict]:
    """Parse RSS 2.0 or Atom into [{id,title,link,summary}, ...]."""
    out: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out

    # RSS 2.0: <channel><item><title/><link/><guid/><description/>
    for item in root.iter("item"):
        title = _txt(item.find("title"))
        link = _txt(item.find("link"))
        guid = _txt(item.find("guid")) or link
        desc = _txt(item.find("description"))
        if title:
            out.append({"id": guid, "title": html.unescape(title),
                        "link": link, "summary": html.unescape(desc)})
    if out:
        return out

    # Atom: <entry><title/><link href/><id/><summary/>
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("a:entry", ns):
        title = _txt(entry.find("a:title", ns))
        id_ = _txt(entry.find("a:id", ns))
        link_el = entry.find("a:link", ns)
        link = link_el.get("href") if link_el is not None else ""
        summary = _txt(entry.find("a:summary", ns)) or _txt(entry.find("a:content", ns))
        if title:
            out.append({"id": id_ or link, "title": html.unescape(title),
                        "link": link, "summary": html.unescape(summary)})
    return out


def send_telegram(msg: str) -> bool:
    if TEST_MODE:
        print("─── TEST_MODE: would send ───\n" + msg + "\n─── end ───",
              file=sys.stderr)
        return True
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[WARN] no Telegram creds; not sent:\n{msg}", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat_id, "text": msg,
        "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=20)
    if r.status_code == 200:
        return True
    r2 = requests.post(url, json={
        "chat_id": chat_id, "text": msg, "disable_web_page_preview": True}, timeout=20)
    return r2.status_code == 200


def format_alert(source: str, item: dict, investors: list) -> str:
    lines = []
    if investors:
        tier, canon = investors[0]
        emoji = TIER_EMOJI.get(tier, "📰")
        lines.append(f"{emoji}⚡ *PR WIRE — {canon.replace('_', ' ')}*")
    else:
        lines.append("📰⚡ *PR WIRE — AI INFRA*")
    lines.append(f"_{source}_")
    lines.append("")
    lines.append(f"*{item['title']}*")
    summ = item.get("summary", "")
    if summ:
        summ = re.sub(r"<[^>]+>", "", summ)
        lines.append(summ[:240] + ("…" if len(summ) > 240 else ""))
    if item.get("link"):
        lines.append(f"\n[Read ›]({item['link']})")
    return "\n".join(lines)


def main() -> int:
    seen = load_state()
    total_new = 0
    total_alerts = 0

    for source, url, mode in FEEDS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            # Pass raw bytes so ElementTree honors the XML encoding declaration
            # (avoids latin-1 mojibake on UTF-8 smart quotes).
            items = parse_feed(r.content)
        except Exception as e:
            print(f"[WARN] feed failed {source}: {e}", file=sys.stderr)
            continue

        print(f"[INFO] {source}: {len(items)} items", file=sys.stderr)
        for item in items:
            uid = f"{source}|{item['id']}"
            if uid in seen:
                continue
            seen.add(uid)
            total_new += 1

            blob = f"{item['title']} {item.get('summary', '')}"
            investors = find_strategic_investors(blob)
            relevant = bool(_AI_KEYWORDS.search(blob))

            if mode == "broad":
                # Wide wire: fire only if a tracked name OR an AI keyword hits.
                if not investors and not relevant:
                    continue
            else:
                # Targeted newsroom (NVDA/AMD): self-name always matches, so gate
                # on AI-infra relevance to drop gaming/events/consumer noise.
                if not relevant:
                    continue

            if send_telegram(format_alert(source, item, investors)):
                total_alerts += 1
                print(f"[ALERT] {source}: {item['title'][:70]}", file=sys.stderr)
                time.sleep(0.5)

    if not TEST_MODE:
        save_state(seen)
    print(f"[DONE] new={total_new} alerts={total_alerts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
