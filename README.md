# Claude Investment Skills

> A streamlined investment analysis system for [Claude Code](https://docs.claude.com/claude-code).
> Top-down framework: Macro → Year theme → Sector → Stock → Entry → Sizing.
> Disciplined, valuation-aware, options-friendly. Triggers via natural language in English or Chinese.

[中文版本 / Chinese Version](./README-zh.md) · [5-min Introduction](./INTRODUCTION.md) · [中文介绍](./INTRODUCTION-zh.md)

## 🤖 For AI agents / CLI users

If you're an AI agent (Claude Code, custom agent, scheduler) or building a CLI wrapper, **read [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md) first**. It contains:
- Natural-language triggers in EN + CN for every tool
- Exact CLI templates with parameter specs
- Example utterance → command mappings
- Multi-tool composite patterns

`INVESTMENT-WORKFLOW.md` tells you *which skill* to pick. `AGENT-TOOL-REFERENCE.md` tells you *exactly how to invoke its scripts*. `ARCHITECTURE.md` explains *why* the data plumbing looks the way it does (yfinance MCP + direct HTTP APIs + openinsider — not a 3-MCP stack).

---

## ⚡ Quick Start (3 minutes)

**Prerequisites:** macOS or Linux, Python 3.9+, [Claude Code](https://docs.claude.com/claude-code/install) installed.

```bash
# 1. Clone to where Claude Code looks for skills
git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills

# 2. Run setup (creates Python venv, installs yfinance, verifies all 13 skills)
bash ~/.claude/skills/setup.sh

# 3. Talk to Claude in plain English (or Chinese)
# Open Claude Code, then just type:
analyze NVDA          # not /analyze-stock — natural language works
```

**That's it.** No slash commands needed. Skills trigger from natural language.

---

## 🗣️ How natural language triggers skills (the magic)

You don't memorize commands. You just talk. Here's why that works:

### The mechanism

1. **Each skill has a `description:` field** in its `SKILL.md` frontmatter listing trigger phrases (English + Chinese).
2. **Claude Code matches your input** against all skill descriptions and picks the best fit.
3. **The matched skill loads its full instructions** and runs (pulls live data, runs analysis, returns answer).

### Example: how `macro-warning` gets triggered

The skill's description includes:
```yaml
Triggers in English ("macro warning", "regime check", "is the market at peak",
"should I take profits", "is it time to buy") or Chinese ("宏观警报",
"市场是不是顶了", "该不该减仓", "regime 怎么样", "该入场吗")
```

So **all of these phrasings** invoke the same skill:

| What you say | What happens |
|---|---|
| "macro warning" | → triggers `macro-warning` |
| "is the market at peak right now?" | → triggers `macro-warning` |
| "should I take profits?" | → triggers `macro-warning` |
| "宏观警报" | → triggers `macro-warning` |
| "市场是不是要顶了" | → triggers `macro-warning` |
| "regime 怎么样" | → triggers `macro-warning` |

### Composite triggers (multiple skills in one ask)

You can chain skills naturally:

```
You: "I want to buy AMD before earnings, is the macro safe?"
→ Claude triggers macro-risk-check first (regime read)
→ then earnings-prep (AMD-specific decision)
→ then maybe analyze-stock (full deep dive if regime is green)
```

### Why this is robust

- **Phrasing variations work** — you don't need exact words
- **Bilingual works mid-sentence** — "analyze NVDA, 顺便看看 macro warning"
- **Ambiguity gets clarified** — Claude asks if your input could match multiple skills
- **Slash commands still work** — `/analyze-stock NVDA` is the explicit fallback

The full mapping (every trigger phrase → skill) is in [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md).

---

## 💬 Real Conversation Examples

Five complete conversations showing how this works in practice. Every reply uses **live data** at the time of the conversation.

### Example 1 — Stock deep dive (English)

```
You: analyze NVDA

Claude: [pulls live price, valuation, insider activity, options IV, and macro
        context, then returns]

NVDA — current $1,142, Forward P/E 38.2 (vs sector median 26)

Macro context: 🟠 ORANGE regime (NDX P/E 38, VIX 17 — see macro-warning)
Year theme: AI capex extends through 2026; power constraint risk
Sector tilt: SMH +138% YoY = mania territory
Insider activity (90d): 0 buys, 4 sells = $312M (10b5-1 plan-based, lighter)
Catalysts: 5/20 earnings (implied move ±8%), new GB300 ramp, China overhang

Recommendation: HOLD existing, no add at $1,142
3-tier entry plan if you want to start fresh:
  - Tier 1 (35%): $1,020-1,060 (50DMA + 20% drawdown)
  - Tier 2 (35%): $920-960 (200DMA, historical bounce zone)
  - Tier 3 (30%): $820 (38% drawdown — max-pain in cyclical correction)

LEAPS alternative: Jan 2027 $1100 call @ $215, breakeven $1315 (15% above
spot), gives 5x leverage at 50% IV. Stronger if you want defined risk.
```

### Example 2 — Macro check before adding (Chinese)

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

### Example 3 — Pre-earnings decision (mixed CN/EN)

```
You: AMD 财报后天，I'm holding 350 shares at $280 cost

Claude: [pulls AMD live data, options chain, 8-quarter history]

AMD Earnings Prep — reports 5/12 AMC

Implied move (ATM straddle): ±9.2% ($30 swing)
Last 8 quarters: 6 beat / 2 miss; avg reaction +4.1%, range -12% to +18%
What's priced in: 17% YoY revenue growth, MI400 ramp Q3/Q4 commentary
Your position: $98K @ $280 cost, currently +14% (+$13.7K unrealized)

4 scenarios (probability-weighted):
  📈 Beat + raise (40%): +12-18% → $314-$330
  📊 In-line (30%):     -2 to +5% → $275-$295
  📉 Light guide (20%): -8 to -12% → $247-$258
  💥 Miss + cut (10%):  -15 to -20% → $225-$238

Recommendation: TRIM 30% (105 shares) before earnings, hold 245
  Why: STCG bracket (held 7 months), implied move pricing rich vs. realized
       Lock in 14% on partial; remaining gives upside, downside cushion in
       case of miss.
  Tax note: 105 × ($295-$280) = $1,575 STCG → ~$580 federal + state
```

### Example 4 — Portfolio audit from screenshot

```
You: [pastes screenshot of portfolio]
     review my portfolio

Claude: [parses screenshot, computes risk metrics]

Portfolio Audit — 12 positions, $487K total

Concentration risks:
  🔴 NVDA 28% (>10% cap) — single-name risk
  🟠 SMH+NVDA+TSM = 51% AI semi (sector concentration)

Factor exposure:
  - High beta names: 67% of book (>50% caution threshold)
  - LEAPS theta drag: $890/week (acceptable)
  - All long, no hedges (vulnerable to macro flip)

Trim list (in priority order):
  1. NVDA: trim 8% → 20% allocation. Sell 21 shares ≈ $24K.
     Why: concentration, parabolic +60% YoY, macro ORANGE
  2. SMH: trim 5% → 12%. Sell 6 shares ≈ $3.4K.
     Why: index proxy duplicates NVDA exposure
  3. PLTR: trim full position ($18K).
     Why: insider check shows 0 buys / 41 sells past 12 months

Cash target after trims: 28% (currently 8%)
Suggested hedge: 1% in QQQ Aug 680P @ $14 = $1,400 protection
```

### Example 5 — Discovery / theme screening

```
You: 找未爆发的 AI 电力股

Claude: [screens utility + power-adjacent names with AI data center exposure]

Top 3 untapped AI Power candidates:

1. CEG (Constellation Energy) — $267
   Forward P/E: 24 (vs VST 31, NRG 28)
   1Y return: +18% (vs sector +35%)
   Catalyst: Microsoft 20-yr nuclear PPA (signed 9/2024); reactivation
            of Three Mile Island Unit 1 by 2028
   Insider: 2 buys, 0 sells past 90d = STRONG BUY signal
   Entry: 3-tier — $250 / $230 / $210

2. NRG (NRG Energy) — $94
   ...

3. PWR (Quanta Services) — $312
   Picks-and-shovels for grid build-out, not direct AI exposure but
   ...

Each candidate has: 3-tier entry, position size cap, catalyst date,
LEAPS alternative, downside scenario.
```

---

## 🎯 What This Does

10 specialized skills that work together to give you fund-manager-grade analysis:

| Skill | Purpose | Trigger Keywords |
|-------|---------|-----------------|
| `analyze-stock` | 10-step deep dive on any stock | "analyze X", "is X a buy", "deep dive" |
| `macro-risk-check` | Daily macro radar (VIX/MOVE/yields/USDJPY) — news-driven | "macro check", "regime read" |
| **`macro-warning`** | **Daily batch-mode 8-layer pullback radar** (NDX PE / VIX / F&G / credit / breadth / sectors) — quantitative | **"macro warning", "is the market at peak", "宏观警报"** |
| `find-untapped-thesis` | NOK-style screening (未爆发) | "find next NOK", "undervalued in X" |
| `earnings-prep` | Pre-earnings decision framework | "should I hold X through earnings" |
| `leaps-screen` | LEAPS selection (1-3yr options) | "what LEAPS for X", "stock or LEAPS" |
| `option-wall-analysis` | Max pain + gamma walls | "max pain on X", "option walls" |
| `tax-optimize` | LTCG vs STCG decisions | "should I sell X for tax" |
| `portfolio-audit` | Full portfolio risk audit | "review my portfolio", "what to trim" |
| `narrative-reversal-screen` | ORCL-style reversal screening | "beaten-down with thesis" |
| `sector-rotation-analysis` | Sector heat map + rotation | "what sector to rotate to" |
| **`price-alert`** | **GitHub Actions + Telegram price alerts** (any ticker, any threshold/%) | **"alert me when X hits Y", "X 跌到 Y 通知我"** — see [setup guide](./price-alert/SETUP.md) |

Plus existing skills:
- `review-investment-screenshot` — Quick portfolio review from screenshot
- `find-alpha` — Time-horizon alpha screening
- `schedule` — Recurring agents

---

## 📦 Installation

### Prerequisites

| Requirement | Version | Install |
|-------------|---------|---------|
| **Claude Code** | Latest | https://docs.claude.com/claude-code/install |
| **Python** | 3.9+ | `brew install python3` (macOS) |
| **Git** | Any | `brew install git` |

### Required MCP Servers

#### 1. yfmcp (YFinance MCP) — REQUIRED
Provides live stock data, options chains, news.

```bash
# Install via Claude Code
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp

# Or check the latest install command at:
# https://github.com/...yfmcp
```

#### 2. WebSearch — Built-in
Already available in Claude Code. Used for macro events, news, contracts.

### Optional: full-MCP stack (NOT recommended for this repo)

Some teams pair Claude with a 3-MCP investment stack:

```
- Yahoo Finance MCP   → prices, options, VIX     ✅ we use this (yfmcp)
- FRED MCP            → macro indicators          ❌ we use direct CSV instead
- SEC EDGAR MCP       → filings + Form 4          ❌ we use openinsider scrape
```

We deliberately use **only** the first one. Full reasoning in [`ARCHITECTURE.md`](./ARCHITECTURE.md). TL;DR:

- **FRED MCP**: our use case is fixed (6 macro series). Direct `fredgraph.csv` is cron-friendlier and has no MCP startup overhead.
- **EDGAR MCP**: gives raw Form 4 XML; you'd have to re-implement code-aware filtering, recency bucketing, RSU exclusion, 10b5-1 awareness — all of which our `insider_ratio.py` already does on top of openinsider's pre-parsed data.

Add EDGAR MCP later **only if** you need 10-K / 8-K / S-1 / 13D parsing (none of our current skills need it).

### Optional MCP Servers (claude.ai connectors)

| Server | Use Case | How |
|--------|----------|-----|
| Notion | Save analysis to your notebook | https://claude.ai/customize/connectors |
| Gmail | Read earnings call summaries | Same as above |
| Google Calendar | Auto-schedule earnings reminders | Same as above |
| Google Drive | Reference investment docs | Same as above |

### Step-by-Step Install

```bash
# 1. Install Claude Code (if not already)
# Follow https://docs.claude.com/claude-code/install

# 2. Install yfmcp MCP server
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp

# 3. Clone this repo
cd ~/.claude/skills
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git .

# 4. Run setup
bash setup.sh

# 5. Verify
ls ~/.claude/skills/
# Should see: analyze-stock, macro-risk-check, etc.

# 6. Test
# Open Claude Code, type:
/analyze-stock NVDA
```

---

## 🛠 What's Inside

```
~/.claude/skills/
├── setup.sh                            # One-click installer
├── INVESTMENT-WORKFLOW.md              # Master decision tree
├── README.md                           # This file (English)
├── README-zh.md                        # Chinese version
│
├── AGENT-TOOL-REFERENCE.md             # NEW v1.2: natural-language → CLI for agents/CLI
│
├── analyze-stock/SKILL.md              # 10-step master framework
├── macro-risk-check/SKILL.md           # Daily macro radar (news-driven)
├── macro-warning/SKILL.md              # NEW v1.3: daily 8-layer pullback radar (batch)
├── find-untapped-thesis/SKILL.md       # NOK-style screening
├── earnings-prep/SKILL.md              # Pre-earnings analysis
├── leaps-screen/SKILL.md               # LEAPS selection
├── option-wall-analysis/SKILL.md       # Max pain + walls
├── tax-optimize/SKILL.md               # LTCG/STCG calculator
├── portfolio-audit/SKILL.md            # Portfolio risk review
├── narrative-reversal-screen/SKILL.md  # ORCL-style hunting
├── sector-rotation-analysis/SKILL.md   # Sector heat map
│
└── review-investment-screenshot/       # (existing)
    └── scripts/
        ├── insider_ratio.py            # v3: openinsider primary, Form 4 code-aware, recency-bucketed
        ├── cluster_buy_scan.py         # NEW: scans openinsider /latest-cluster-buys for cluster signals
        ├── quote_pull.py               # Batch live quotes
        ├── option_walls.py             # Top OI clusters
        └── max_pain.py                 # Max pain calculator
```

---

## 🎓 The Philosophy

Top-down macro-aware framework with these core principles:

1. **AI = Factory mode**, not software tax. Hyperscalers buy compute like factories buy machines.
2. **K-shape divergence**: Within sectors, winners crush losers. Pick winners.
3. **Power as bottleneck**: Constrained inputs reprice upward (electricity, fuel, materials).
4. **Demand destruction risk windows**: Monitor oil/inflation/geopolitical indicators.
5. **Carry trade structures**: BOJ policy can trigger global risk-off cascades.

Combined with discipline rules:
- Always check insider trading (use `insider_ratio.py`, not yfinance summary)
- Always check macro before adding (regime > stock)
- 3-tier entry plans (no "buy at market")
- Position size caps (max 10% single name, max 5% high beta)
- Cash is the alpha (40-50% in danger zones)

---

## 📝 Examples — What to Say (English + 中文)

Every skill triggers via natural language in **either English or Chinese**. Just say it like a human — no slash commands needed (though slash works too).

### 🆕 macro-warning (daily pullback radar)

**English triggers:**
- "Run macro warning"
- "Is the market at peak?"
- "Should I take profits?"
- "Regime check"
- "Is it time to buy?"
- "What's the pullback risk today?"

**中文 triggers:**
- "宏观警报"
- "市场是不是顶了"
- "现在该不该减仓"
- "regime 怎么样"
- "今天能不能加仓"
- "市场风险大不大"

**Schedule it (daily auto-run):**
- "Set up daily macro-warning at 8am ET pre-market" → triggers `/schedule`
- "每天早上 8 点跑一次 macro-warning"

---

### 📊 analyze-stock (10-step deep dive)

**English:**
- "Analyze NVDA"
- "Is TSEM a buy?"
- "Deep dive on FN"
- "What about CEG stock?"
- "Research VST"

**中文:**
- "分析一下 NVDA"
- "TSEM 怎么样"
- "FN 能买吗"
- "深度看一下 GFS"
- "调研 VST"

---

### 🔍 find-untapped-thesis (NOK-style screening)

**English:**
- "Find me the next NOK"
- "What's undervalued in AI Power"
- "Show me cheap names in semiconductor"
- "Find untapped uranium plays"

**中文:**
- "找未爆发的 AI 电力股"
- "光通信板块还有什么便宜的"
- "找下一个 NOK"
- "X 主题筛选"

---

### 🎯 find-alpha (3-horizon discovery)

**English:**
- "Find alpha"
- "Weekly alpha scan"
- "What's the next MRVL setup?"
- "Find me 3 swing trades"

**中文:**
- "找 alpha"
- "本周 alpha 扫一下"
- "找下一个 MRVL"

---

### 📈 macro-risk-check (news-driven macro)

**English:**
- "Macro check"
- "Is the market safe?"
- "Risk on or off?"

**中文:**
- "看一下宏观"
- "市场风险怎么样"
- "现在能加仓吗"

---

### 💰 earnings-prep (pre-earnings decision)

**English:**
- "Earnings prep for AMD"
- "Should I hold NVDA through earnings?"
- "What's priced in for CRWD earnings?"
- "AMD reports tomorrow, what do I do?"

**中文:**
- "AMD 财报前怎么看"
- "NVDA 财报应该减仓吗"
- "CRWD 财报前分析"
- "X implied move"

---

### 📞 leaps-screen (long-dated options)

**English:**
- "LEAPS for NVDA"
- "What call should I buy on TSEM?"
- "Stock or LEAPS for VST?"

**中文:**
- "NVDA 买什么 LEAPS"
- "TSEM 的长期 call"
- "VST 现货还是期权"
- "FN 2027 call 推荐"

---

### 🧱 option-wall-analysis (max pain + gamma)

**English:**
- "Max pain on NVDA"
- "Option walls for AAPL"
- "Where will SPY pin this week?"

**中文:**
- "NVDA 的 max pain"
- "AAPL 期权墙"
- "SPY 这周走哪里"

---

### 💼 portfolio-audit (full risk audit)

**English:**
- "Review my portfolio"
- "Audit my book"
- "Am I too concentrated?"
- "What should I trim?"

**中文:**
- "审一下我的组合"
- "我组合风险大吗"
- "该减什么仓"

---

### 🧾 tax-optimize (LTCG vs STCG)

**English:**
- "Should I sell NOK for tax?"
- "Tax on selling AMD"
- "LTCG vs STCG on NVDA"

**中文:**
- "X 减仓税务"
- "现在卖还是等长期"
- "X 减仓最省税"

---

### 🔄 sector-rotation-analysis

**English:**
- "Sector rotation"
- "What sector to add?"
- "Am I too tech-heavy?"

**中文:**
- "板块轮动"
- "该买哪个板块"
- "我是不是 tech 太重"

---

### 🪞 narrative-reversal-screen

**English:**
- "Find beaten-down stocks with thesis"
- "Stocks at bottom that can recover"
- "Comeback candidates"

**中文:**
- "找暴跌反转股"
- "ORCL 那种反转"
- "已经跌透的好股"

---

### 📸 review-investment-screenshot

**English:** Just paste a portfolio screenshot and ask "what do you think?"

**中文:** 直接发组合截图，问"看一下我的组合"

---

### 🔧 Insider scripts (technical, advanced)

**Cluster buy hunt (market-wide):**
- "Find cluster buys"
- "Who's buying what?"
- "找 cluster buy"
- "最近高管买入"

**Single-stock insider check:**
- "Insider check on NVDA"
- "TSEM 内部交易"
- "X 高管在卖吗"

---

## 🚀 Common Workflows

### Workflow 1: "Should I buy NVDA?"
```
1. /macro-risk-check          # Is regime safe to add?
2. /analyze-stock NVDA        # 10-step deep dive
3. /option-wall-analysis NVDA # Short-term levels
4. /leaps-screen NVDA         # LEAPS option (if good entry)
```

### Workflow 2: "Should I trim my portfolio?"
```
1. /macro-risk-check          # Regime read
2. /portfolio-audit           # Full audit (provide positions)
3. /tax-optimize NOK 1000     # For each trim, check tax
```

### Workflow 3: "AMD reports tomorrow, what do I do?"
```
1. /earnings-prep AMD         # Implied move + scenarios
2. /option-wall-analysis AMD  # Where will it pin
3. /tax-optimize AMD 350      # If trimming, check tax
```

### Workflow 4: "Find me good ideas"
```
1. /macro-risk-check          # Avoid bad timing
2. /find-untapped-thesis "AI Power"  # Screening
3. /narrative-reversal-screen        # Reversal candidates
4. /analyze-stock [TOP_PICK]         # Deep dive winners
```

---

## 📅 Recommended Recurring Tasks

Set up via `/schedule` skill (just say "set up daily macro warning at 8am ET" / "每天早上 8 点跑 macro-warning"):

| Frequency | Skill | When | Cron (UTC) |
|-----------|-------|------|------------|
| **Daily 8am ET (weekdays)** | **`macro-warning`** | **Pre-market 8-layer pullback radar** | **`0 12 * * 1-5`** |
| Daily 5pm ET (weekdays, optional) | `macro-warning` | Post-close summary | `0 21 * * 1-5` |
| Weekly Monday 8am ET | `macro-risk-check` | News-driven regime read | `0 12 * * 1` |
| Weekly Friday 4pm ET | `find-untapped-thesis` | Find next ideas | `0 20 * * 5` |
| Monthly 1st | `portfolio-audit` | Full portfolio audit | `0 12 1 * *` |
| Pre-event (24h before) | `macro-risk-check` | Before Fed/BOJ/major earnings | manual |
| Quarterly | `tax-optimize` | Year-end planning | manual |

---

## 🔧 Key Scripts (under the hood)

| Script | Purpose | Usage |
|--------|---------|-------|
| `insider_ratio.py` (v3) | Strict open-market insider $ ratio. openinsider primary, yfinance fallback, Form 4 code-aware (P/S only) | `python insider_ratio.py NVDA --window 90` |
| `cluster_buy_scan.py` | Hunts market-wide cluster buys from openinsider | `python cluster_buy_scan.py --days 30 --min-value 500000 --min-insiders 3 --detail --enrich --senior-only` |
| `max_pain.py` | Max pain by expiry | `python max_pain.py NVDA 4` |
| `option_walls.py` | Top OI clusters | `python option_walls.py NVDA 4` |
| `quote_pull.py` | Batch live quotes | `python quote_pull.py "A,B,C"` |

All scripts use `/tmp/.insider_venv` (set up by `setup.sh`).

### Insider data sources (cross-verify, in trust order)
1. **openinsider.com/screener?s=TICKER** — primary. Form 4 with codes (P=Purchase, S=Sale, A=Award/Grant, M=Exercise, F=Tax, G=Gift). Free.
2. **secform4.com** — for 10b5-1 plan footnote disclosure.
3. **stocktitan.net SEC filings** — readable Form 4 narratives.
4. **yfinance** — fallback. Has known blind spots (missed real cluster buys).

---

## ⚠️ Hard Rules (Never Violate)

1. **Always run `insider_ratio.py --window 90`** (openinsider primary) — never trust yfinance "% Net Shares Purchased" headline (counts RSU as buys)
2. **Form 4 code "P" only counts as buy** — `A`/`M`/`F`/`G` are RSU/exercise/tax/gift, NOT buys. Verified false positives: UNH "10 directors" 4/1/2026 (DSU grants), PLTR "Karp 1.47M" (RSU vesting)
3. **Verify any "cluster buy" headline** at openinsider.com/[TICKER] — news routinely mislabels compensation flows
4. **For sells, check 10b5-1** at secform4.com before treating as bearish — scheduled trust sales tell you nothing about today's view
5. **Always check macro before adding** — even great stocks fail in red regime
6. **Position size caps**: max 10% single, max 5% high beta
7. **3-tier entry**: never "buy at market" without 50DMA / 200DMA fallback
8. **Concrete evidence > narrative**: "AI is good" ≠ thesis
9. **Cite sources**: every macro claim has WebSearch link
10. **Tax-aware exits**: especially for high earners

---

## 🐛 Troubleshooting

### "yfmcp not found"
```bash
claude mcp list  # Check installed
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp
```

### "Python venv not working"
```bash
rm -rf /tmp/.insider_venv
bash ~/.claude/skills/setup.sh
```

### "yfinance: ModuleNotFoundError"
```bash
/tmp/.insider_venv/bin/pip install --upgrade yfinance pandas numpy
```

### "Skills not showing up in Claude Code"
- Restart Claude Code
- Verify SKILL.md frontmatter has `name:` and `description:`
- Check ~/.claude/skills/ permissions: `chmod -R 755 ~/.claude/skills/`

---

## 📚 Learn More

- **Master decision tree**: [INVESTMENT-WORKFLOW.md](./INVESTMENT-WORKFLOW.md)
- **Agent CLI contract**: [AGENT-TOOL-REFERENCE.md](./AGENT-TOOL-REFERENCE.md)
- **Architecture decisions**: [ARCHITECTURE.md](./ARCHITECTURE.md) — why this repo uses direct APIs + 1 MCP, not 3
- **Price alerts setup**: [price-alert/SETUP.md](./price-alert/SETUP.md) — one-time Telegram bot + GitHub Secrets walkthrough
- **Each skill's details**: `[skill-name]/SKILL.md`
- **Macro framework**: See `analyze-stock/SKILL.md` Year Theme section
- **Insider methodology**: See `review-investment-screenshot/SKILL.md` (existing)

---

## 🤝 Sharing With Friends

```bash
# They run:
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git ~/.claude/skills
bash ~/.claude/skills/setup.sh

# That's it. They have your entire investment thinking system.
```

---

## ⚖️ Disclaimer

These skills are tools for **personal investment research**. They do not constitute financial advice. Past performance doesn't guarantee future results. Consult a licensed financial advisor for actual investment decisions.

The framework is opinionated — it reflects one specific style (top-down, value-aware, macro-conscious, options-friendly). It is NOT designed for:
- Day trading
- Pure quantitative strategies
- Crypto-only portfolios
- Forex trading

---

## 📜 Credits

- **Framework inspirations**: Buffett (margin of safety), Druckenmiller (macro pivots), Stan Weinstein (stage analysis)
- **Built with**: Claude Code by Anthropic

---

**Version**: 1.5
**Last updated**: 2026-05-10
**License**: [MIT](./LICENSE)

### Changelog
- **1.5 (2026-05-10)**: First public release on GitHub. Added MIT LICENSE, INTRODUCTION.md/INTRODUCTION-zh.md (5-min friendly intro), full Chinese translations of ARCHITECTURE, INVESTMENT-WORKFLOW, AGENT-TOOL-REFERENCE. Enhanced README with "How natural language triggers skills" section and 5 real conversation examples (EN + CN). Updated setup.sh to verify macro_pull.py.
- **1.4 (2026-05-09)**: `macro-warning` gets a real data backend — `scripts/macro_pull.py` with direct APIs (yfinance + FRED CSV + CNN unofficial JSON + multpl scrape). New `ARCHITECTURE.md` documenting why we use direct APIs + 1 MCP instead of 3-MCP stack.
- **1.3 (2026-05-08)**: New `macro-warning` skill — daily batch-mode 8-layer pullback radar (NDX P/E >38 / VIX <14 / F&G >85 = override YELLOW). Cron-friendly. Memory integration via `macro_history.jsonl`. Added bilingual examples section.
- **1.2 (2026-05-05)**: New `AGENT-TOOL-REFERENCE.md` — natural-language → CLI contract for AI agents. Cross-linked from all docs.
- **1.1 (2026-05-05)**: insider_ratio.py v3 (openinsider primary, Form 4 code-aware, 90d default window). New cluster_buy_scan.py. Updated all skills to reflect 8-rule insider methodology (yfinance summary broken, recency dominates, 10b5-1 awareness, BUY rarity, news false positives, yfinance blind spots, micro-buy ESPP filter).
- **1.0 (2026-05-04)**: Initial release.
