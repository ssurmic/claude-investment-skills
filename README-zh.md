# Claude 投资分析 Skills 系统

> 给 [Claude Code](https://docs.claude.com/claude-code) 用的投资分析自动化系统。
> Top-Down 框架：宏观 → 年度主题 → 板块 → 个股 → 入场点位 → 仓位。
> 价值 + 期权 + 宏观感知三合一，支持中英文自然语言触发。

[English Version](./README.md) · [5 分钟介绍](./INTRODUCTION-zh.md) · [English intro](./INTRODUCTION.md)

## 🤖 给 AI agent / CLI 用户

如果你是 AI agent（Claude Code、自定义 agent、定时器）或在做 CLI 包装，**先读 [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md)**。架构决策（为什么用 yfinance MCP + 直接 HTTP API + openinsider，而不是 3-MCP 全套）记录在 [`ARCHITECTURE.md`](./ARCHITECTURE.md)。它包含：
- 每个工具的中英文自然语言触发短语
- 精确的 CLI 模板和参数说明
- 用户话术 → 命令的映射例子
- 多工具组合调用的 pattern

`INVESTMENT-WORKFLOW.md` 告诉你**用哪个 skill**。`AGENT-TOOL-REFERENCE.md` 告诉你**精确怎么调用脚本**。

---

## ⚡ 一键开始（3 分钟）

**前置依赖：** macOS 或 Linux、Python 3.9+、已装 [Claude Code](https://docs.claude.com/claude-code/install)。

```bash
# 1. Clone 到 Claude Code 的 skills 目录
git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills

# 2. 跑 setup（建 Python venv，装 yfinance，验证 13 个 skills）
bash ~/.claude/skills/setup.sh

# 3. 跟 Claude 用大白话说话（中英文都行）
# 打开 Claude Code，直接说：
分析一下 NVDA          # 不用 /analyze-stock —— 自然语言就行
```

**完事。**不需要 slash 命令，skills 自己会被自然语言触发。

---

## 🏗️ 架构一览

`price-alert` skill（可选 Telegram + Anthropic API 集成）。chat 路径有**两种实现方式可互换** —— 按你想要的延迟挑一个：

```mermaid
flowchart TB
    User([👤 你])
    Phone[📱 手机 Telegram]
    ClaudeCode[💬 Claude Code<br/>你电脑]

    User -->|"用 NL 设 alert<br/>'GLW 跌到 140 通知我'"| ClaudeCode
    User <-->|"用 NL 跟 bot 聊"| Phone

    ClaudeCode -->|"git commit + push<br/>alerts.json"| Repo[(🌐 GitHub Repo<br/>alerts.json = source of truth)]

    Phone <-->|"消息"| TGAPI([📡 Telegram Bot API])

    %% 价格扫描路径 —— 永远运行
    Repo -->|"checkout"| W1["⏰ price-alerts.yml<br/>GH Actions cron<br/>每 2 min, 24/7"]
    W1 --> CheckPy[check_alerts.py]
    CheckPy <-->|"价格"| YF([📊 Yahoo Finance API])
    CheckPy -->|"alert 触发:<br/>sendMessage"| TGAPI

    %% Chat 路径 —— 二选一
    TGAPI -.->|"选项 A: getUpdates pull<br/>每 2-5 分钟"| W2["⏰ telegram-chat.yml<br/>GH Actions cron<br/>延迟 2-15 min · $0"]
    TGAPI ==>|"选项 B: HTTPS POST push<br/>即时"| Worker[["⚡ Cloudflare Worker<br/>price-alert-webhook<br/>延迟 1-3 秒 · $0"]]

    W2 --> ChatPy[chat_handler.py]
    ChatPy <-->|"NL 解析 + tool use"| Claude([🧠 Anthropic API<br/>Claude Sonnet 4.6])
    Worker <-->|"NL 解析 + tool use"| Claude

    ChatPy -.->|"git commit alerts.json"| Repo
    Worker -.->|"PUT alerts.json<br/>via Contents API"| Repo

    TGAPI -->|"推送通知"| Phone

    Secrets[🔐 Secrets<br/>GH Secrets + CF Worker Secrets]
    Secrets -.-> W1
    Secrets -.-> W2
    Secrets -.-> Worker

    classDef user fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#000
    classDef worker fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000
    classDef webhook fill:#fff9c4,stroke:#f57f17,stroke-width:3px,color:#000
    classDef api fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#000
    classDef storage fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000
    classDef secret fill:#ffebee,stroke:#d32f2f,stroke-width:2px,color:#000

    class User,Phone,ClaudeCode user
    class W1,W2,CheckPy,ChatPy worker
    class Worker webhook
    class YF,TGAPI,Claude api
    class Repo storage
    class Secrets secret
```

**两条 chat 路径，效果相同 —— 延迟不同**：

| | 选项 A: GitHub Actions polling | 选项 B: Cloudflare Worker webhook |
|---|---|---|
| **模型** | Pull（cron 主动去问"有新消息吗"）| Push（Telegram 即时把消息推过来）|
| **延迟** | 2-15 分钟 | 1-3 秒 |
| **冷启动** | Ubuntu VM ~10-30 秒 | V8 isolate ~50 毫秒 |
| **配置耗时** | 10 分钟（[SETUP-zh.md](./price-alert/SETUP-zh.md)）| 上面基础上 +5 分钟（[SETUP-WEBHOOK-zh.md](./price-alert/SETUP-WEBHOOK-zh.md)）|
| **费用** | $0 | $0（CF 免费层 10 万 req/天）|

先用选项 A。如果你**真的经常和 bot 聊**而且觉得 2-15 分钟延迟烦，再升级到 webhook。

**每月费用估算**：跳过可选的 Telegram chat bot = **$0**；中度 NL chat ~$1-4/月（Anthropic API，**两种路径一样的钱** —— Claude 调用本身一样）。完整成本细分见 [INTRODUCTION-zh.md](./INTRODUCTION-zh.md#-每月成本估算)。

每个组件的详细工作机制见 [INTRODUCTION-zh.md → 完整系统怎么工作](./INTRODUCTION-zh.md#-完整系统怎么工作--架构图进阶)。

---

## 🗣️ 自然语言怎么触发 skill 的（"魔法"）

你**不用记命令**，直接说话就行。原理：

### 机制

1. **每个 skill 在 `SKILL.md` 的 frontmatter** 里有个 `description:` 字段，列了触发短语（中英文都有）。
2. **Claude Code 拿你的输入**去匹配所有 skill descriptions，挑最匹配的。
3. **匹配上的 skill 加载完整 instructions** 并跑（拉实时数据、跑分析、返回答案）。

### 示例：`macro-warning` 怎么被触发

它的 description 里写了：
```yaml
Triggers in English ("macro warning", "regime check", "is the market at peak",
"should I take profits", "is it time to buy") or Chinese ("宏观警报",
"市场是不是顶了", "该不该减仓", "regime 怎么样", "该入场吗")
```

所以下面**任意说法**都触发同一个 skill：

| 你说 | 发生什么 |
|---|---|
| "macro warning" | → 触发 `macro-warning` |
| "is the market at peak right now?" | → 触发 `macro-warning` |
| "should I take profits?" | → 触发 `macro-warning` |
| "宏观警报" | → 触发 `macro-warning` |
| "市场是不是要顶了" | → 触发 `macro-warning` |
| "regime 怎么样" | → 触发 `macro-warning` |

### 组合触发（一句话调用多个 skill）

你可以自然地组合：

```
你: "我想在财报前买 AMD，宏观安全吗？"
→ Claude 先触发 macro-risk-check（regime 读取）
→ 再触发 earnings-prep（AMD 财报决策）
→ 也许再触发 analyze-stock（如果 regime 绿，做完整深度）
```

### 为什么这个机制稳

- **措辞变化都行** —— 不需要精确字句
- **句中切换中英文** —— "analyze NVDA, 顺便看看 macro warning" 也行
- **歧义会被澄清** —— 输入可能匹配多个 skill 时 Claude 会反问
- **Slash 命令仍然能用** —— `/analyze-stock NVDA` 是显式 fallback

完整映射（每个触发短语 → skill）在 [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md)。

---

## 💬 真实对话示例

5 个完整对话，展示实际怎么用。每个回复都用**实时数据**。

### 例 1 — 个股深度分析（英文）

```
你: analyze NVDA

Claude: [拉实时价格、估值、内部交易、期权 IV、宏观环境]

NVDA — 当前 $1,142, Forward P/E 38.2 (vs 板块中位数 26)

宏观环境: 🟠 ORANGE regime (NDX P/E 38, VIX 17 — 见 macro-warning)
年度主题: AI capex 延续到 2026；电力约束风险
板块倾斜: SMH +138% YoY = mania 区域
内部交易 (90 天): 0 buys, 4 sells = $312M (10b5-1 计划，权重低)
催化剂: 5/20 财报 (implied move ±8%), GB300 ramp, 中国市场不确定性

建议: 当前持仓 HOLD, $1,142 不加
3 档入场计划 (新仓):
  - Tier 1 (35%): $1,020-1,060 (50DMA + 20% drawdown)
  - Tier 2 (35%): $920-960 (200DMA, 历史反弹区)
  - Tier 3 (30%): $820 (38% drawdown — 周期回调 max-pain)

LEAPS 替代: Jan 2027 $1100 call @ $215, 盈亏平衡 $1315 (现价 +15%),
50% IV 给 5x 杠杆。如果想限定风险，更优。
```

### 例 2 — 加仓前宏观检查（中文）

```
你: 宏观警报，能不能加仓？

Claude: [跑 macro_pull.py 拉 8 层指标]

🟠 ORANGE regime — Composite 11/16

触发的硬规则:
  ✦ Shiller CAPE 42.05 > 38 (extreme)
  ✦ VIX 17.19 < 18 (exit-signal threshold)

8 层得分:
  🔴 估值 (2/2)  CAPE 42.05, SPX trailing PE 31.83
  🔴 波动 (2/2)  VIX 17.19, MOVE 67.25
  🟡 情绪 (1/2)  CNN F&G 66.9 (一周前 71.2，正在降温)
  🔴 信用 (2/2)  HY OAS 279 bps (complacency)
  🟡 货币 (1/2)  USD/JPY 156.62 (差 BOJ 干预区 3.4)
  🟡 宽度 (1/2)  SPX top 50 中只 44% 在 200DMA 上
  🟢 CTA  (0/2)  无公开 API
  🔴 板块 (2/2)  SMH 一年涨 +142% = mania

判断: 不建议加仓。现金 30-35%，trim AI/Semi 抛物 (-15-20%)，
买便宜 hedge (VIX 17 = put 极便宜)。

升级到 🔴 RED 触发器:
  - VIX < 14
  - F&G > 85
  - USD/JPY > 160
  - 30Y > 5.10%
```

### 例 3 — 财报前决策（中英混说）

```
你: AMD 财报后天，I'm holding 350 shares at $280 cost

Claude: [拉 AMD 实时数据、期权链、过去 8 季度历史]

AMD 财报准备 — 5/12 盘后报

Implied move (ATM straddle): ±9.2% ($30 振幅)
过去 8 季度: 6 beat / 2 miss; 平均反应 +4.1%, 范围 -12% 到 +18%
已 price in: 17% YoY 营收增长, MI400 ramp Q3/Q4 commentary
你的仓位: $98K @ $280 成本, 当前 +14% (+$13.7K 浮盈)

4 个情景 (概率加权):
  📈 Beat + raise (40%): +12-18% → $314-$330
  📊 In-line (30%):     -2 到 +5% → $275-$295
  📉 Light guide (20%): -8 到 -12% → $247-$258
  💥 Miss + cut (10%):  -15 到 -20% → $225-$238

建议: 财报前 TRIM 30% (105 股), hold 245
  原因: STCG 区间 (持有 7 个月), implied move 定价偏贵 vs realized
        部分锁定 14% 利润；剩下保留上行，万一 miss 有缓冲。
  税务: 105 × ($295-$280) = $1,575 STCG → ~$580 联邦 + 州税
```

### 例 4 — 截图组合审计

```
你: [贴组合截图]
    审一下我的组合

Claude: [解析截图，算风险指标]

组合审计 — 12 仓位, $487K 总额

集中度风险:
  🔴 NVDA 28% (>10% 红线) — 单股风险
  🟠 SMH+NVDA+TSM = 51% AI semi (板块集中)

因子暴露:
  - 高 beta 仓位: 67% (>50% 警戒线)
  - LEAPS theta drag: $890/周 (可接受)
  - 全多无对冲 (宏观翻车时脆弱)

减仓清单 (按优先级):
  1. NVDA: 减到 20% 仓位。卖 21 股 ≈ $24K。
     原因: 集中度, 抛物 +60% YoY, 宏观 ORANGE
  2. SMH: 减到 12%。卖 6 股 ≈ $3.4K。
     原因: 指数 ETF 与 NVDA 仓位重复
  3. PLTR: 全部清仓 ($18K)。
     原因: 内部交易检查显示 12 个月 0 买 41 卖

减仓后现金目标: 28% (当前 8%)
建议对冲: 1% QQQ Aug 680P @ $14 = $1,400 保护
```

### 例 5 — 主题筛选

```
你: 找未爆发的 AI 电力股

Claude: [筛公用事业 + 电力相关 + AI 数据中心曝险的标的]

Top 3 未爆发 AI Power 候选:

1. CEG (Constellation Energy) — $267
   Forward P/E: 24 (vs VST 31, NRG 28)
   1Y 涨幅: +18% (vs 板块 +35%)
   催化剂: 微软 20 年核电 PPA (2024/9 已签); 三里岛 1 号机组 2028
          重启
   内部交易: 90 天 2 buys, 0 sells = STRONG BUY 信号
   入场: 3 档 — $250 / $230 / $210

2. NRG (NRG Energy) — $94
   ...

3. PWR (Quanta Services) — $312
   电网建设的"卖铲人"，不是直接 AI 曝险但
   ...

每个候选包含: 3 档入场、仓位上限、催化日期、LEAPS 替代、下行情景。
```

---

## 🎯 这是什么

10 个专业 skills 组成的投资分析系统，给你**基金经理级别**的分析：

| Skill | 用途 | 触发关键词 |
|-------|------|----------|
| `analyze-stock` | 10 步深度分析任何股票 | "analyze X"、"X 是不是 buy"、"深度分析" |
| `macro-risk-check` | 每日宏观新闻扫描 | "宏观看一下"、"市场状态" |
| **`macro-warning`** | **每日 batch 8-层顶部预警**（NDX P/E / VIX / F&G / 信用 / 宽度 / 板块）| **"宏观警报"、"市场是不是顶了"、"该不该减仓"** |
| `find-untapped-thesis` | NOK 类未爆发筛选 | "找下一个 NOK"、"X 板块未爆发" |
| `earnings-prep` | 财报前决策框架 | "X 财报怎么处理"、"该持有还是减仓" |
| `leaps-screen` | LEAPS 长期期权选择 | "X 买什么 LEAPS"、"现货还是 LEAPS" |
| `option-wall-analysis` | 最大痛点 + 期权墙 | "X 的 max pain"、"option walls" |
| `tax-optimize` | LTCG vs STCG 决策 | "X 减仓税务"、"什么时候卖" |
| `portfolio-audit` | 完整组合风险审计 | "审一下我的组合"、"减什么仓" |
| `narrative-reversal-screen` | ORCL 风格反转筛选 | "找 ORCL 那种"、"暴跌反转" |
| `sector-rotation-analysis` | 板块热力图 + 轮动 | "板块轮动"、"该买哪个板块" |
| **`price-alert`** | **GitHub Actions + Telegram 价格 alert**（任何标的、任何阈值/百分比）| **"alert me when X hits Y"、"X 跌到 Y 通知我"** —— 见 [setup 指南](./price-alert/SETUP-zh.md) |

加上已有的：
- `review-investment-screenshot` — 截图组合速读
- `find-alpha` — 时间分级 alpha
- `schedule` — 远程定时 agent

---

## 📦 安装步骤

### 前置依赖

| 依赖 | 版本 | 安装 |
|------|------|------|
| **Claude Code** | 最新版 | https://docs.claude.com/claude-code/install |
| **Python** | 3.9+ | `brew install python3` (macOS) |
| **Git** | 任何版本 | `brew install git` |

### 必需的 MCP Servers

#### 1. yfmcp（YFinance MCP）— 必装
提供股票实时数据、期权链、新闻。

```bash
# 通过 Claude Code 安装
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp

# 或者查最新安装命令：
# https://github.com/...yfmcp
```

#### 2. WebSearch — 内置
Claude Code 已包含。用于宏观事件、新闻、合同验证。

### 可选 MCP Servers（claude.ai connectors）

| Server | 用途 | 怎么装 |
|--------|------|------|
| Notion | 把分析存到笔记 | https://claude.ai/customize/connectors |
| Gmail | 读财报会议纪要 | 同上 |
| Google Calendar | 自动设置财报提醒 | 同上 |
| Google Drive | 引用投资文档 | 同上 |

### 完整安装步骤

```bash
# 1. 装 Claude Code（如果还没装）
# 看 https://docs.claude.com/claude-code/install

# 2. 装 yfmcp MCP server
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp

# 3. Clone 这个 repo
cd ~/.claude/skills
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git .

# 4. 跑 setup
bash setup.sh

# 5. 验证
ls ~/.claude/skills/
# 应该看到: analyze-stock, macro-risk-check 等等

# 6. 测试
# 打开 Claude Code，输入：
/analyze-stock NVDA
```

---

## 🛠 目录结构

```
~/.claude/skills/
├── setup.sh                            # 一键安装脚本
├── INVESTMENT-WORKFLOW.md              # 主决策树
├── README.md                           # 英文文档
├── README-zh.md                        # 这个文件（中文）
│
├── analyze-stock/SKILL.md              # 10 步主框架
├── macro-risk-check/SKILL.md           # 每日宏观雷达
├── find-untapped-thesis/SKILL.md       # NOK 风格筛选
├── earnings-prep/SKILL.md              # 财报前分析
├── leaps-screen/SKILL.md               # LEAPS 选择
├── option-wall-analysis/SKILL.md       # Max pain + 期权墙
├── tax-optimize/SKILL.md               # LTCG/STCG 计算
├── portfolio-audit/SKILL.md            # 组合风险审计
├── narrative-reversal-screen/SKILL.md  # ORCL 风格反转
├── sector-rotation-analysis/SKILL.md   # 板块热力图
│
└── review-investment-screenshot/       # （已有）
    └── scripts/
        ├── insider_ratio.py            # v3：openinsider 主源，Form 4 code 感知，按时间分桶
        ├── cluster_buy_scan.py         # 新：扫描 openinsider /latest-cluster-buys 找 cluster 信号
        ├── quote_pull.py               # 批量实时报价
        ├── option_walls.py             # OI 集中 strikes
        └── max_pain.py                 # Max pain 计算
```

---

## 🎓 核心理念

Top-Down 宏观感知投资框架，5 大核心原则：

1. **AI = 工厂模式**，不是软件收税。Hyperscalers 像工厂买机器一样买算力。
2. **K 型分化**：板块内部赢家碾压输家。挑赢家。
3. **瓶颈环节升值**：被约束的供给环节（电力、燃料、材料）会重估。
4. **需求毁灭风险窗口**：定期监控油价、通胀、地缘政治信号。
5. **Carry trade 结构**：BOJ 政策能触发全球风险偏好级联反应。

加上纪律性原则：
- 永远查 insider trading（用 `insider_ratio.py`，不要相信 yfinance summary）
- 加仓前先看宏观（regime > 个股）
- 三档入场计划（不要"市价买入"）
- 仓位上限（单股 max 10%，高 beta max 5%）
- 现金就是 alpha（危险区 40-50%）

---

## 📝 触发示例（English + 中文）

每个 skill 都可以**用大白话**触发——不需要打 slash 命令。说什么都行，中英文随便切。

### 🆕 macro-warning（每日顶部预警）

**英文：**
- "Run macro warning"
- "Is the market at peak?"
- "Should I take profits?"
- "Regime check"

**中文：**
- "宏观警报"
- "市场是不是顶了"
- "现在该不该减仓"
- "regime 怎么样"
- "今天能不能加仓"

**设为定时任务：**
- "每天早上 8 点跑 macro-warning"
- "Set up daily macro-warning at 8am ET pre-market"

---

### 📊 analyze-stock（10 步深度分析）

**英文：** "Analyze NVDA"、"Is TSEM a buy?"、"Deep dive on FN"
**中文：** "分析一下 NVDA"、"TSEM 怎么样"、"FN 能买吗"、"深度看一下 GFS"

---

### 🔍 find-untapped-thesis（NOK 风格筛选）

**英文：** "Find me the next NOK"、"What's undervalued in AI Power"
**中文：** "找未爆发的 AI 电力股"、"光通信板块还有什么便宜的"、"找下一个 NOK"

---

### 🎯 find-alpha（3 时间维度 alpha）

**英文：** "Find alpha"、"Weekly alpha scan"、"What's the next MRVL setup?"
**中文：** "找 alpha"、"本周 alpha 扫一下"、"找下一个 MRVL"

---

### 📈 macro-risk-check（新闻型宏观）

**英文：** "Macro check"、"Is the market safe?"
**中文：** "看一下宏观"、"市场风险怎么样"、"现在能加仓吗"

---

### 💰 earnings-prep（财报前决策）

**英文：** "Earnings prep for AMD"、"Should I hold NVDA through earnings?"
**中文：** "AMD 财报前怎么看"、"NVDA 财报应该减仓吗"、"X 财报前分析"

---

### 📞 leaps-screen（长期期权）

**英文：** "LEAPS for NVDA"、"What call should I buy on TSEM?"
**中文：** "NVDA 买什么 LEAPS"、"TSEM 的长期 call"、"VST 现货还是期权"

---

### 🧱 option-wall-analysis（最大痛点+期权墙）

**英文：** "Max pain on NVDA"、"Option walls for AAPL"
**中文：** "NVDA 的 max pain"、"AAPL 期权墙"、"SPY 这周走哪里"

---

### 💼 portfolio-audit（组合风险审计）

**英文：** "Review my portfolio"、"Audit my book"、"Am I too concentrated?"
**中文：** "审一下我的组合"、"我组合风险大吗"、"该减什么仓"

---

### 🧾 tax-optimize（税务优化）

**英文：** "Should I sell NOK for tax?"、"LTCG vs STCG on NVDA"
**中文：** "X 减仓税务"、"现在卖还是等长期"、"X 减仓最省税"

---

### 🔄 sector-rotation-analysis（板块轮动）

**英文：** "Sector rotation"、"What sector to add?"
**中文：** "板块轮动"、"该买哪个板块"、"我是不是 tech 太重"

---

### 🪞 narrative-reversal-screen（暴跌反转）

**英文：** "Find beaten-down stocks with thesis"、"Comeback candidates"
**中文：** "找暴跌反转股"、"ORCL 那种反转"、"已经跌透的好股"

---

### 📸 review-investment-screenshot（截图速读）

直接发组合截图 + "看一下我的组合" 或 "what do you think?"

---

### 🔧 内部人脚本（高级功能）

**全市场 cluster buy 扫描：**
- "Find cluster buys" / "找 cluster buy" / "最近高管买入"

**单股内部人查询：**
- "Insider check on NVDA" / "TSEM 内部交易" / "X 高管在卖吗"

---

## 🚀 常用工作流

### 工作流 1：「该不该买 NVDA？」
```
1. /macro-risk-check          # 当前 regime 安全吗？
2. /analyze-stock NVDA        # 10 步深度分析
3. /option-wall-analysis NVDA # 短期价位
4. /leaps-screen NVDA         # 看看 LEAPS（如果入场点合适）
```

### 工作流 2：「该不该减仓？」
```
1. /macro-risk-check          # 看 regime
2. /portfolio-audit           # 完整审计（提供持仓）
3. /tax-optimize NOK 1000     # 每个减仓项查税
```

### 工作流 3：「AMD 明天财报怎么办？」
```
1. /earnings-prep AMD         # Implied move + 4 种情景
2. /option-wall-analysis AMD  # 锚定到哪儿
3. /tax-optimize AMD 350      # 如果减仓查税
```

### 工作流 4：「找好想法」
```
1. /macro-risk-check          # 避免坏时机
2. /find-untapped-thesis "AI Power"  # 筛选
3. /narrative-reversal-screen        # 反转标的
4. /analyze-stock [TOP_PICK]         # 深度分析头部赢家
```

---

## 📅 推荐定时任务

通过 `/schedule` skill 设置（直接说"每天早上 8 点跑 macro-warning"或 "set up daily macro warning at 8am ET"）：

| 频率 | Skill | 何时 | Cron (UTC) |
|------|-------|------|------------|
| **每个交易日早 8 点 ET** | **`macro-warning`** | **盘前 8-层顶部预警** | **`0 12 * * 1-5`** |
| 每个交易日下午 5 点 ET（可选） | `macro-warning` | 收盘后总结 | `0 21 * * 1-5` |
| 每周一早 8 点 ET | `macro-risk-check` | 新闻型 regime 读取 | `0 12 * * 1` |
| 每周五下午 4 点 ET | `find-untapped-thesis` | 找下周想法 | `0 20 * * 5` |
| 每月 1 日 | `portfolio-audit` | 完整组合审计 | `0 12 1 * *` |
| 重大事件前 24h | `macro-risk-check` | Fed/BOJ/重大财报前 | 手动 |
| 季度 | `tax-optimize` | 年末规划 | 手动 |

---

## 🔧 后台脚本

| 脚本 | 用途 | 用法 |
|------|------|------|
| `insider_ratio.py` (v3) | 严格开放市场 insider $ 比，openinsider 主源，按 Form 4 code 过滤（只算 P）| `python insider_ratio.py NVDA --window 90` |
| `cluster_buy_scan.py` | 扫描 openinsider 找市场全局 cluster buy | `python cluster_buy_scan.py --days 30 --min-value 500000 --min-insiders 3 --detail --enrich --senior-only` |
| `max_pain.py` | 按到期日的 max pain | `python max_pain.py NVDA 4` |
| `option_walls.py` | OI 集中 strikes | `python option_walls.py NVDA 4` |
| `quote_pull.py` | 批量实时报价 | `python quote_pull.py "A,B,C"` |

所有脚本使用 `/tmp/.insider_venv`（由 `setup.sh` 创建）。

### Insider 数据源（按可信度排序）
1. **openinsider.com/screener?s=TICKER** — 主源。Form 4 with codes（P=买入, S=卖出, A=授予, M=行权, F=税务, G=赠予）。免费，无需登录。
2. **secform4.com** — 备份。看 10b5-1 计划脚注。
3. **stocktitan.net SEC filings** — 可读 Form 4 描述。
4. **yfinance** — fallback。已知盲区（漏掉 NKE/UNH/PLTR 真实 cluster buy）。

---

## ⚠️ 硬性规则（不能违反）

1. **永远跑 `insider_ratio.py --window 90`**（openinsider 主源）— 不要信 yfinance 的「净买入」（把 RSU 算成买入）
2. **Form 4 code 只有 "P" 算买入** — A/M/F/G 是 RSU/行权/税务/赠予，**不是**买入信号。已验证假阳性：UNH "10 directors 4/1/2026"（全是 DSU 季度补偿）、PLTR "Karp 1.47M 股"（RSU 归属）
3. **任何 "cluster buy" 标题都要在 openinsider.com/[TICKER] 验证** — 媒体经常把补偿当成 conviction
4. **卖出要查 10b5-1**（在 secform4.com 看脚注）— 计划性 trust 卖出告诉你的不是当前观点
5. **加仓前先看宏观** — 再好的股在 red regime 里也跌
6. **仓位上限**：单股 max 10%，高 beta max 5%
7. **三档入场**：永远不要「市价买入」，必须有 50DMA / 200DMA 备份
8. **Concrete 证据 > 故事**：「AI 好」≠ 投资逻辑
9. **引用源**：每个宏观说法要带 WebSearch 链接
10. **税务感知出场**：特别是高收入者

---

## 🐛 故障排查

### 「yfmcp not found」
```bash
claude mcp list  # 看看装了哪些
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp
```

### 「Python venv 不工作」
```bash
rm -rf /tmp/.insider_venv
bash ~/.claude/skills/setup.sh
```

### 「yfinance: ModuleNotFoundError」
```bash
/tmp/.insider_venv/bin/pip install --upgrade yfinance pandas numpy
```

### 「Skills 在 Claude Code 里不显示」
- 重启 Claude Code
- 确认 SKILL.md 的 frontmatter 有 `name:` 和 `description:`
- 检查权限：`chmod -R 755 ~/.claude/skills/`

---

## 📚 进一步学习

- **主决策树**：[INVESTMENT-WORKFLOW.md](./INVESTMENT-WORKFLOW.md)
- **每个 skill 细节**：`[skill-name]/SKILL.md`
- **宏观年度框架**：见 `analyze-stock/SKILL.md` 年度主题部分
- **Insider 方法论**：见 `review-investment-screenshot/SKILL.md`（已有）

---

## 🤝 给朋友分享

```bash
# 朋友只需要跑：
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git ~/.claude/skills
bash ~/.claude/skills/setup.sh

# 完事。他们就有了你完整的投资思维系统。
```

---

## ⚖️ 免责声明

这些 skills 是**个人投资研究的工具**。**不是金融建议**。历史业绩不代表未来。实际投资决策请咨询持牌金融顾问。

这个框架有特定风格（top-down、价值导向、宏观感知、期权友好）。**不适合**：
- 日内交易
- 纯量化策略
- 纯加密组合
- 外汇交易

---

## 📜 致谢

- **框架灵感**：Buffett（安全边际）+ Druckenmiller（宏观转折）+ Stan Weinstein（趋势阶段）
- **构建工具**：Anthropic 的 Claude Code

---

**版本**：1.0
**最后更新**：2026-05-04
