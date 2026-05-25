#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
investor_registry.py — Curated list of "strategic partner" names that
indicate alpha-rich SEC filings.

战略投资者名单 —— 一旦在 SEC 8-K 或 SC 13D 里看到这些名字 + 大额投资,
通常是早于 Twitter / Substack 6-18 月的真实 alpha 信号。

Tiers (按 alpha 强度排序):
  TIER_1   = 大型科技/电信巨头 (NVIDIA, MSFT, SKT, Samsung) → 最强信号
  TIER_2   = 二线企业战略投资人 (Intel Capital, Qualcomm Ventures) → 良好信号
  SOVEREIGN= 主权基金 (MGX/UAE, PIF/沙特, Temasek) → 大笔但 timeline 慢
  SMART_VC = AI/半导体专业 VC (a16z infra, Lux Capital) → narrow signal

Every entry has multiple aliases because SEC filings spell company names
inconsistently (e.g. "NVIDIA Corporation" vs "Nvidia Corp" vs "NVIDIA"
vs "NVDA Holdings").
每个条目都列多个别名 —— SEC filing 公司名拼写不统一, 必须用 regex 匹配
而不是精确字符串。

USAGE:
    from investor_registry import find_strategic_investors
    matches = find_strategic_investors(filing_text)
    # → [("tier_1", "NVIDIA Corporation"), ("sovereign", "MGX"), ...]
"""
from __future__ import annotations

import re
from typing import Iterable

# ─── Tier 1: 顶级战略投资人 / Top-tier strategic investors ─────────────────
# 这些公司投钱 = 直接 alpha 信号 (PENG / SGH 类型)
# These companies' investments = direct alpha signal (PENG/SGH pattern)
TIER_1: dict[str, list[str]] = {
    # ─ US 美国巨头 ─
    "NVIDIA": [
        "NVIDIA Corporation", "NVIDIA Corp", "NVIDIA Inc", "Nvidia Corporation",
        "Nvidia, Inc.",
        # NVentures = NVIDIA 公司风投部门 (NVIDIA's corporate VC arm)
        "NVentures",
        "NVIDIA Strategic Investments",
    ],
    "Microsoft": [
        "Microsoft Corporation", "Microsoft Corp", "Microsoft, Inc.",
        "M12",  # Microsoft's VC arm
    ],
    "Google_Alphabet": [
        "Alphabet Inc", "Alphabet Inc.", "Google LLC", "Google Inc",
        "GV LLC", "Google Ventures",  # GV = Google Ventures
        "CapitalG",  # late-stage growth fund
    ],
    "Amazon_AWS": [
        "Amazon.com, Inc.", "Amazon.com Inc", "Amazon Web Services",
        "Amazon Industrial Innovation Fund",
    ],
    "Meta": [
        "Meta Platforms", "Meta Platforms, Inc.", "Meta Platforms Inc",
        "Facebook, Inc.",  # 老名字 (still used in some filings)
    ],
    "Apple": [
        "Apple Inc", "Apple Inc.", "Apple Computer Inc",
    ],
    "Oracle": [
        "Oracle Corporation", "Oracle Corp",
    ],
    "Broadcom": [
        "Broadcom Inc", "Broadcom Inc.", "Broadcom Corporation",
    ],
    "AMD": [
        "Advanced Micro Devices", "Advanced Micro Devices, Inc.", "AMD Inc",
    ],
    "Tesla": [
        "Tesla, Inc.", "Tesla Inc",
    ],

    # ─ AI labs / 大模型实验室 (the new CapEx deployers — compute buyers) ─
    # 这些是 AI 算力的最终买家. 一旦公开供应商 8-K 里出现它们的名字 =
    # CapEx 资金流向该供应商的硬信号 (e.g. AMD-OpenAI warrants 8-K).
    "OpenAI": [
        "OpenAI", "OpenAI, Inc.", "OpenAI Global", "OpenAI OpCo",
    ],
    "Anthropic": [
        "Anthropic", "Anthropic PBC", "Anthropic, PBC",
    ],
    "xAI": [
        "xAI Corp", "xAI Holdings", "X.AI",  # avoid bare "xAI" — too short, false-positive prone
    ],
    "Mistral": [
        "Mistral AI",
    ],
    "SafeSuperintelligence": [
        "Safe Superintelligence",
    ],

    # ─ Neoclouds / GPU 云 (CapEx-heavy GPU buildout buyers) ─
    "CoreWeave": [
        "CoreWeave", "CoreWeave, Inc.",
    ],
    "Nebius": [
        "Nebius Group", "Nebius B.V.",
    ],
    "Lambda": [
        "Lambda Labs", "Lambda, Inc.",  # avoid bare "Lambda" — AWS Lambda false hits
    ],
    "Crusoe": [
        "Crusoe Energy", "Crusoe Energy Systems",
    ],
    "TogetherAI": [
        "Together Computer", "Together AI",
    ],

    # ─ 韩国 Korean tech (PENG-style 投资来源 / PENG-style strategic sources) ─
    "SK_Telecom": [
        "SK Telecom", "SK telecom", "SK Telecom Co., Ltd.",
        "SKT", "SK Telecom Co Ltd",
    ],
    "SK_Hynix": [
        "SK hynix", "SK Hynix", "SK Hynix Inc.", "SK hynix Inc",
        "SK Hynix America",
    ],
    "Samsung": [
        "Samsung Electronics", "Samsung Electronics Co., Ltd.",
        "Samsung Catalyst Fund",  # Samsung VC
        "Samsung Ventures",
        "Samsung NEXT",
    ],
    "LG": [
        "LG Electronics", "LG Display", "LG Energy Solution",
        "LG Technology Ventures",
    ],

    # ─ 台湾 + 日本 Taiwan + Japan ─
    "TSMC": [
        "Taiwan Semiconductor Manufacturing", "TSMC",
        "TSMC Global",
    ],
    "SoftBank": [
        "SoftBank Group", "SoftBank Corp", "Softbank Vision Fund",
        "SVF Investments",  # SoftBank Vision Fund alias
    ],
    "Sony": [
        "Sony Group", "Sony Corporation", "Sony Innovation Fund",
    ],

    # ─ 欧洲 Europe ─
    "ASML": [
        "ASML Holding", "ASML Holding N.V.", "ASML US",
    ],
    "SAP": [
        "SAP SE", "SAP America Inc",
    ],
}

# ─── Tier 2: 二线战略投资人 / Secondary strategic ─────────────────────────
TIER_2: dict[str, list[str]] = {
    "Intel_Capital": [
        "Intel Corporation", "Intel Corp", "Intel Capital",
    ],
    "Qualcomm": [
        "Qualcomm Incorporated", "Qualcomm Inc",
        "Qualcomm Ventures",
    ],
    "Salesforce": [
        "Salesforce, Inc.", "Salesforce.com",
        "Salesforce Ventures",
    ],
    "Dell": [
        "Dell Technologies", "Dell Inc", "Dell EMC",
    ],
    "HPE": [
        "Hewlett Packard Enterprise", "HPE Pathfinder",
    ],
    "Cisco": [
        "Cisco Systems", "Cisco Systems, Inc.",
        "Cisco Investments",
    ],
    "IBM": [
        "International Business Machines",
        "IBM Ventures",
    ],
    "Adobe": [
        "Adobe Inc", "Adobe Systems",
    ],
    "ServiceNow": [
        "ServiceNow, Inc.",
    ],
    "Workday": [
        "Workday Ventures",
    ],
}

# ─── Sovereign: 主权财富基金 / Sovereign wealth funds ───────────────────
# 这些金额通常 $500M+, 表明 "国家级" 战略
# These typically deploy $500M+, indicating nation-state strategic intent
SOVEREIGN: dict[str, list[str]] = {
    "MGX": [
        # MGX = UAE/Abu Dhabi sovereign tech fund (Stargate co-investor)
        "MGX",
        "MGX Fund Management",
    ],
    "Mubadala": [
        "Mubadala Investment",
        "Mubadala Capital",
    ],
    "ADIA": [
        "Abu Dhabi Investment Authority",
        "ADIA",
    ],
    "PIF_Saudi": [
        "Public Investment Fund",
        "Public Investment Fund of Saudi Arabia",
        "PIF",  # ambiguous, validate in context
    ],
    "Temasek": [
        "Temasek Holdings",
        "Temasek International",
    ],
    "GIC": [
        "GIC Private Limited",
        "Government of Singapore Investment",
    ],
    "CPPIB": [
        "Canada Pension Plan Investment Board",
        "CPP Investments",
    ],
}

# ─── Smart Money VC: AI/半导体专业 VC ─────────────────────────────────
# 专注 deep tech 的顶级 VC, 信号窄但精
# Deep-tech focused top VCs - narrow but high-precision signal
SMART_VC: dict[str, list[str]] = {
    "a16z": [
        "Andreessen Horowitz",
        "AH Capital Management",
    ],
    "Lux_Capital": [
        "Lux Capital",
    ],
    "Sequoia": [
        "Sequoia Capital",
    ],
    "Founders_Fund": [
        "Founders Fund",
    ],
    "Khosla": [
        "Khosla Ventures",
    ],
    "Coatue": [
        "Coatue Management",
    ],
    "Tiger_Global": [
        "Tiger Global",
    ],
}


def _compile_pattern(name: str) -> re.Pattern:
    """
    Compile a case-insensitive whole-word match for an investor name.
    编译大小写不敏感的整词匹配 regex。

    Why \b boundaries: prevent "Microsoft" matching "MicrosoftReseller" or
    "PIF" matching "PIFER" or random substrings.
    用 \b 边界: 防止 "Microsoft" 误配 "MicrosoftReseller" 这种子串。
    """
    return re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)


# Pre-compile all patterns once at module load for speed
# 模块加载时一次性编译所有 pattern, 加速
_ALL_PATTERNS: list[tuple[str, str, re.Pattern]] = []
for tier_name, registry in [
    ("tier_1", TIER_1),
    ("tier_2", TIER_2),
    ("sovereign", SOVEREIGN),
    ("smart_vc", SMART_VC),
]:
    for canonical_key, aliases in registry.items():
        for alias in aliases:
            _ALL_PATTERNS.append((tier_name, canonical_key, _compile_pattern(alias)))


def find_strategic_investors(text: str) -> list[tuple[str, str]]:
    """
    Scan text for any strategic investor mentions.
    在 text 中搜索所有战略投资人名字。

    Args:
        text: filing body text (8-K body or 13D content)

    Returns:
        List of (tier, canonical_name) tuples. Deduped — if "NVIDIA" and
        "NVIDIA Corporation" both appear, returns only one match for NVIDIA.
        返回去重后的 (tier, canonical_name) 列表。

    Example:
        >>> matches = find_strategic_investors("...SK Telecom invested $200M...")
        >>> matches
        [('tier_1', 'SK_Telecom')]
    """
    if not text:
        return []

    seen: set[tuple[str, str]] = set()
    results: list[tuple[str, str]] = []

    for tier, canonical, pattern in _ALL_PATTERNS:
        key = (tier, canonical)
        if key in seen:
            continue
        if pattern.search(text):
            seen.add(key)
            results.append(key)

    return results


# Tier weights for scoring (used by analysis.py)
# Tier 权重 (analysis.py 评分用)
TIER_WEIGHT: dict[str, int] = {
    "tier_1": 3,      # Strongest signal (NVIDIA, MSFT, etc.)
    "sovereign": 2,   # Large checks but slower thesis
    "tier_2": 2,      # Solid signal (Intel Capital, etc.)
    "smart_vc": 1,    # Narrow signal
}


# Emoji per tier for Telegram display
# 每个 tier 在 Telegram 显示的 emoji
TIER_EMOJI: dict[str, str] = {
    "tier_1": "🐉",
    "sovereign": "👑",
    "tier_2": "🦅",
    "smart_vc": "🦊",
}
