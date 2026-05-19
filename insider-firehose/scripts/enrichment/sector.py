"""sector.py — classify a ticker into hot/cold sector buckets with AI focus.

Built for 2026 Q2 thematic map. AI核心 → 🔥🔥🔥 / 防守端 expanded with cold tag.

Two-pass classification:
  1. Hard-coded ticker override (e.g., AVAV → Defense Drones, MRVL → AI Networking)
  2. Industry-name regex pattern matching from yfinance `industry` field

Returns a dict with:
  - bucket: theme name (e.g., "AI Networking / Custom Silicon")
  - heat: emoji string (🔥🔥🔥 / 🔥🔥 / 🔥 / ➖ / ❄️ / ❄️❄️)
  - rationale: short Chinese explanation
  - is_ai: bool (is this part of AI primary theme)
  - is_defensive: bool (defensive recession-resistant)
"""
from __future__ import annotations

import re

# ─── Hard-coded ticker → bucket overrides (most specific) ─────────────
TICKER_OVERRIDE = {
    # 🔥🔥🔥 AI 核心
    "NVDA": "AI GPU 龙头", "AMD": "AI GPU",
    "AVGO": "AI Custom ASIC", "MRVL": "AI Networking / Custom ASIC",
    "ALAB": "PCIe/CXL Retimer (AI)", "CRDO": "AI 互联 (AEC/PAM4)",
    "CEG": "AI 核电运营", "VST": "AI 核电 IPP", "FSLR": "AI 太阳能制造",
    "GEV": "AI 电力设备", "ETN": "AI 电力管理", "HUBB": "AI 电网设备",
    "BWXT": "核反应堆 (AI 电力链)", "CCJ": "铀矿 (AI 核电)",
    "MU": "HBM 内存", "SNDK": "NAND/SSD (AI 数据中心)",
    "ANET": "AI 网络以太网", "CSCO": "AI 网络 Silicon One",
    "VRT": "AI 数据中心电力", "SMCI": "AI 服务器整机",
    "ON": "SiC 功率半导体 (AI 电力)", "WOLF": "SiC 纯玩",
    "MPWR": "AI 电源 IC", "IFNNY": "SiC 欧洲龙头",
    # 🔥🔥 已涨过但强势
    "TSLA": "Optimus 人形 + EV", "XPEV": "IRON 人形 + EV",
    "ISRG": "外科手术机器人", "SYK": "外科 + Mako 机器人",
    "OUST": "数字 LiDAR", "HSAI": "中国 LiDAR (政治风险)",
    "AEVA": "FMCW LiDAR", "MBLY": "ADAS / 自动驾驶",
    "AVAV": "国防无人机", "KTOS": "国防无人系统",
    "ACHR": "eVTOL", "JOBY": "eVTOL",
    "ZBRA": "仓储机器人 AMR", "AUR": "自动驾驶卡车",
    "PATH": "RPA 软件机器人",
    "COIN": "加密交易所 (Clarity Act)", "HOOD": "Crypto + 多元化金融",
    "CRCL": "USDC 稳定币", "BKKT": "加密基础设施",
    "GLD": "黄金 ETF", "GDX": "金矿股 ETF", "GDXU": "金矿 3x 杠杆",
    "UUUU": "铀矿 + 稀土", "EU": "铀矿 ISR",
    # 🔥 单点热度
    "SPXC": "AI 数据中心散热", "NVTS": "GaN/SiC AI",
    "ORCL": "AI 云 + Oracle Stargate", "NOK": "AI 光通信",
    "MRAM": "工业内存", "VPG": "力传感器 (机器人)",
    "ALNT": "运动控制电机", "INDI": "汽车+机器人芯片",
    "KLIC": "精密焊接机器人", "AMBQ": "超低功耗 AI 芯片",
    "FTAI": "飞行器引擎 (AI 物流)",
    "PINS": "Pinterest AI 视觉搜索", "HUBS": "SaaS CRM + AI Agent",
    "AMZN": "云 + 仓储机器人 + AI", "TMDX": "器官移植 (AI 物流)",
    "MRVL": "AI 网络弹性桥",
    # ➖ 中性
    "ARW": "电子分销 (周期性)", "NIQ": "消费者数据分析",
    "UNIT": "光纤 REIT + AI Backbone",
    # ❄️ 防守 / 冷板块
    "ICFI": "联邦政府咨询 (DOGE 风险)", "BAH": "政府咨询 (DOGE)",
    "SAIC": "国防 IT (DOGE)", "LDOS": "政府 IT (DOGE)",
    "BETR": "数字按揭 (财务高风险)", "RKT": "传统按揭",
    "FCN": "诉讼/重组咨询 (经济周期)",
    "AMKR": "封测 (半导体周期)", "FORM": "晶圆测试设备 (高位回调)",
    "TMDX": "医疗运输",
}

# ─── Bucket → heat + flags ───────────────────────────────────────────
BUCKET_META = {
    # 🔥🔥🔥 AI 核心 (3 fires)
    "AI GPU 龙头":             ("🔥🔥🔥", "AI 训练核心硬件，所有 hyperscaler 必采", True, False),
    "AI GPU":                  ("🔥🔥🔥", "GPU + MI300 推理加速", True, False),
    "AI Custom ASIC":          ("🔥🔥🔥", "Meta/Google/Amazon 自研芯片必经厂", True, False),
    "AI Networking / Custom ASIC": ("🔥🔥🔥", "横跨网络层+计算层，稀缺位置", True, False),
    "AI 核电运营":             ("🔥🔥🔥", "OpenAI/Anthropic 都签了核电 PPA", True, True),
    "AI 核电 IPP":             ("🔥🔥🔥", "Meta + AWS 已签 3,800MW", True, True),
    "AI 数据中心电力":         ("🔥🔥🔥", "NVIDIA Kyber + 800VDC 官方合作", True, False),
    "HBM 内存":                ("🔥🔥🔥", "AI 算力瓶颈，需求 5 倍暴增", True, False),
    "AI 服务器整机":           ("🔥🔥🔥", "AI 算力直接组装受益", True, False),
    "AI 网络以太网":           ("🔥🔥🔥", "AI 集群以太网替代 InfiniBand", True, False),
    # 🔥🔥 强势
    "AI Networking 弹性桥":    ("🔥🔥🔥", "NVLink Fusion + Custom ASIC + 光电", True, False),
    "AI 网络弹性桥":           ("🔥🔥🔥", "NVLink Fusion + Custom ASIC + 光电", True, False),
    "AI 互联 (AEC/PAM4)":      ("🔥🔥", "AEC 主动电缆 + PAM4 DSP", True, False),
    "PCIe/CXL Retimer (AI)":   ("🔥🔥", "AI 服务器物理层铲子", True, False),
    "AI 太阳能制造":           ("🔥🔥", "美国制造+IRA 45X 抵免", True, True),
    "AI 电力设备":             ("🔥🔥", "电网+燃气轮机双引擎", True, True),
    "AI 电力管理":             ("🔥🔥", "电力管理龙头", True, True),
    "AI 电网设备":             ("🔥🔥", "变压器/开关柜，电网现代化", True, True),
    "核反应堆 (AI 电力链)":    ("🔥🔥", "核电零部件供应链", True, True),
    "铀矿 (AI 核电)":          ("🔥🔥", "AI 核电采购浪潮上游受益", True, False),
    "AI 云 + Oracle Stargate": ("🔥🔥", "$553B 合同 backlog", True, False),
    "AI 网络 Silicon One":     ("🔥🔥", "估值不对称的 AI 受益", True, True),
    "AI 光通信":               ("🔥🔥", "Infinera 并表 + 光骨干", True, False),
    "AI 电源 IC":              ("🔥🔥", "NVIDIA 800VDC 合作", True, False),
    "SiC 功率半导体 (AI 电力)":("🔥🔥", "SST + EV + AI 数据中心", True, False),
    "SiC 纯玩":                ("🔥🔥", "纯 SiC 弹性最大", True, False),
    "SiC 欧洲龙头":            ("🔥🔥", "200mm SiC 量产领先", True, False),
    "NAND/SSD (AI 数据中心)":  ("🔥🔥", "AI 数据中心存储需求", True, False),
    "Optimus 人形 + EV":       ("🔥🔥", "Tesla Optimus 人形机器人", True, False),
    "IRON 人形 + EV":          ("🔥🔥", "XPeng IRON 2026 量产", True, False),
    "外科手术机器人":          ("🔥🔥", "da Vinci 全球装机 11,000+", True, True),
    "外科 + Mako 机器人":      ("🔥🔥", "Mako Shoulder 新发布", True, True),
    "加密交易所 (Clarity Act)":("🔥🔥", "5/14 参议院过关 +9% pop", True, False),
    "Crypto + 多元化金融":     ("🔥🔥", "Prediction markets +320%", True, False),
    "USDC 稳定币":             ("🔥🔥", "Clarity Act 通过=暴涨", True, False),
    # 🔥 单点
    "AI 数据中心散热":         ("🔥", "OlympusMAX HVAC 锁定 hyperscaler", True, False),
    "GaN/SiC AI":              ("🔥", "Navitas 已被 pump", True, False),
    "数字 LiDAR":              ("🔥", "NVIDIA Hyperion 设计赢", True, False),
    "中国 LiDAR (政治风险)":   ("🔥", "1260H 名单风险", True, False),
    "FMCW LiDAR":              ("🔥", "Daimler/Porsche/Nikon 设计赢", True, False),
    "ADAS / 自动驾驶":         ("🔥", "VW/Audi 设计赢但 Tesla 竞争", True, False),
    "国防无人机":              ("🔥🔥", "Switchblade + 国防预算红利", False, True),
    "国防无人系统":            ("🔥🔥", "无人战斗机/航空", False, True),
    "eVTOL":                   ("🔥", "电动垂直起降", False, False),
    "仓储机器人 AMR":          ("🔥", "Fetch Robotics + Vulcan", True, False),
    "自动驾驶卡车":            ("🔥", "Volvo+DSV+McLane 商业化", True, False),
    "RPA 软件机器人":          ("➖", "软件 RPA 被 AI agent 替代风险", False, False),
    "加密基础设施":            ("🔥", "ICE 系托管 + 业务转型", True, False),
    "黄金 ETF":                ("🔥", "Real yield 高位但长期保值", False, True),
    "金矿股 ETF":              ("🔥", "金价回调中等机会", False, True),
    "金矿 3x 杠杆":            ("🔥", "3x ETN 高弹性 (谨慎)", False, False),
    "铀矿 + 稀土":             ("🔥", "稀土战略+核电铀", True, False),
    "铀矿 ISR":                ("🔥", "微盘高弹性", False, False),
    "Pinterest AI 视觉搜索":   ("🔥", "Performance+ AI 广告", True, False),
    "SaaS CRM + AI Agent":     ("🔥", "Customer Agent 9K 客户", True, False),
    "云 + 仓储机器人 + AI":    ("🔥🔥", "Sequoia/Sparrow/Vulcan", True, False),
    "AEC + 光通信":            ("🔥🔥", "1.6T 光模块 + AEC", True, False),
    "Optimus 人形":            ("🔥🔥", "人形机器人量产", True, False),
    "AI 数据中心 + 卫星":      ("🔥🔥", "AI 计算 + 数据中心 + 卫星", True, False),
    "SaaS + AI 转型":          ("🔥", "AI Agent + 营销转型", True, False),
    "美股 + AI 转型":          ("🔥", "AI 转型中", True, False),
    "消费者数据分析":          ("🔥", "consumer behavior data + AI tail wind", True, False),
    "光纤 REIT + AI Backbone": ("🔥", "Windstream merger + AI 光纤合同", True, False),
    "工业内存":                ("🔥", "MRAM 工业级", False, False),
    "力传感器 (机器人)":       ("🔥", "humanoid 必需零件", True, False),
    "运动控制电机":            ("🔥", "工业电机", True, False),
    "汽车+机器人芯片":         ("🔥", "汽车+机器人 SoC", True, False),
    "精密焊接机器人":          ("🔥", "已涨过，半导体封测", False, False),
    "超低功耗 AI 芯片":        ("🔥", "Edge AI", True, False),
    "飞行器引擎 (AI 物流)":    ("🔥", "AI 物流间接受益", False, False),
    "器官移植 (AI 物流)":      ("🔥", "TMDX 重叠医疗", False, True),
    "医疗运输":                ("🔥", "器官移植物流", False, True),
    # ➖ 中性
    "电子分销 (周期性)":       ("➖", "电子分销周期股，已在高位", False, False),
    # ❄️ 冷板块
    "联邦政府咨询 (DOGE 风险)": ("❄️", "Trump DOGE 砍合同", False, True),
    "政府咨询 (DOGE)":         ("❄️", "Trump DOGE 砍合同", False, True),
    "国防 IT (DOGE)":          ("❄️", "国防 IT 但 DOGE 阴影", False, True),
    "政府 IT (DOGE)":          ("❄️", "Trump DOGE 削减预算", False, True),
    "数字按揭 (财务高风险)":   ("❄️❄️", "BETR 重负债+高烧钱", False, False),
    "传统按揭":                ("❄️", "高利率压制按揭需求", False, False),
    "诉讼/重组咨询 (经济周期)":("➖", "经济衰退反而受益但需 confirm", False, True),
    "封测 (半导体周期)":       ("➖", "半导体周期顶高位", False, False),
    "晶圆测试设备 (高位回调)": ("➖", "1Y +267% 已涨过", False, False),
}

# ─── Industry regex fallback when ticker not in override ─────────────
INDUSTRY_PATTERNS = [
    (r"semiconductor", "🔥🔥", "半导体 AI 受益", True, False),
    (r"software.*infrastructure", "🔥🔥", "Infrastructure SaaS / Agent 战", True, False),
    (r"software.*application", "🔥", "Application SaaS 转型期", True, False),
    (r"information technology services|consulting services",
        "❄️", "IT/咨询服务 (DOGE/经济敏感)", False, True),
    (r"utilities.*independent power|utilities.*regulated electric",
        "🔥🔥", "电力公司 AI 红利", True, True),
    (r"medical devices|medical instruments",
        "🔥", "医疗设备 (含手术机器人)", True, True),
    (r"aerospace.*defense", "🔥🔥", "国防航空 (国防预算红利)", False, True),
    (r"uranium", "🔥", "铀矿 AI 核电链", True, False),
    (r"gold", "🔥", "黄金对冲", False, True),
    (r"capital markets|financial conglomerates",
        "🔥", "金融科技 + Clarity Act", True, False),
    (r"banks.*regional", "➖", "区域银行 (中性)", False, True),
    (r"banks.*diversified", "➖", "综合银行 (中性)", False, True),
    (r"insurance.*property", "➖", "P&C 保险 (中性)", False, True),
    (r"mortgage", "❄️", "按揭 (高利率压制)", False, False),
    (r"reit.*office|office", "❄️❄️", "办公 REIT (远程办公冲击)", False, False),
    (r"reit.*residential", "➖", "住宅 REIT", False, True),
    (r"reit.*industrial|reit.*specialty",
        "🔥", "工业/特殊 REIT (含数据中心)", True, False),
    (r"retail.*specialty|retail.*apparel",
        "❄️", "特殊零售 (高基数压力)", False, False),
    (r"consumer.*staples|household products|packaged foods|beverages",
        "➖", "消费必需品 (防守)", False, True),
    (r"restaurants", "❄️", "餐饮链 (高劳动力成本)", False, False),
    (r"airlines", "❄️", "航空 (高负债+燃油)", False, False),
    (r"oil.*gas.*exploration|oil & gas e&p",
        "❄️", "油气勘探 (油价回调期)", False, False),
    (r"oil.*gas.*midstream", "➖", "油气中游 (相对稳)", False, True),
    (r"healthcare.*plans", "➖", "医疗保险 (政策不稳)", False, True),
    (r"biotechnology", "🔥", "生物科技 (AI 药物发现)", True, False),
    (r"drug manufacturers.*major", "🔥", "大药企 (AI + Ozempic 类)", True, True),
    (r"electronic.*components", "🔥", "电子元件 (AI 链)", True, False),
    (r"specialty industrial machinery|industrial machinery|industrial distribution",
        "🔥", "工业机械 (含机器人)", True, False),
    (r"communication equipment", "🔥", "通信设备 (AI 网络)", True, False),
    (r"interactive media|internet content",
        "🔥", "互联网媒体 (AI 广告)", True, False),
    (r"asset management", "➖", "资管 (中性)", False, True),
]

DEFAULT_META = ("➖", "未分类板块", False, False)


def classify_sector(ticker: str, sector: str | None, industry: str | None) -> dict:
    """Classify ticker/sector/industry into hot/cold bucket.

    Returns dict with bucket, heat, rationale, is_ai, is_defensive.
    Always returns a valid dict (never None).
    """
    t = (ticker or "").upper()
    ind = (industry or "").lower()

    # Pass 1: hard-coded ticker override
    if t in TICKER_OVERRIDE:
        bucket = TICKER_OVERRIDE[t]
        if bucket in BUCKET_META:
            heat, rationale, is_ai, is_def = BUCKET_META[bucket]
        else:
            heat, rationale, is_ai, is_def = DEFAULT_META
        return {
            "bucket": bucket,
            "heat": heat,
            "rationale": rationale,
            "is_ai": is_ai,
            "is_defensive": is_def,
        }

    # Pass 2: industry regex
    for pattern, heat, rationale, is_ai, is_def in INDUSTRY_PATTERNS:
        if re.search(pattern, ind):
            return {
                "bucket": industry or sector or "未分类",
                "heat": heat,
                "rationale": rationale,
                "is_ai": is_ai,
                "is_defensive": is_def,
            }

    # Fallback
    return {
        "bucket": industry or sector or "未分类",
        "heat": DEFAULT_META[0],
        "rationale": DEFAULT_META[1],
        "is_ai": False,
        "is_defensive": False,
    }
