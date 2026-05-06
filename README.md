# Claude Investment Skills

> A streamlined investment analysis system for Claude Code.
> Top-down framework: Macro → Year theme → Sector → Stock → Entry → Sizing.
> Disciplined, valuation-aware, options-friendly. Triggers via natural language in English or Chinese.

[中文版本 / Chinese Version](./README-zh.md)

## 🤖 For AI agents / CLI users

If you're an AI agent (Claude Code, custom agent, scheduler) or building a CLI wrapper, **read [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md) first**. It contains:
- Natural-language triggers in EN + CN for every tool
- Exact CLI templates with parameter specs
- Example utterance → command mappings
- Multi-tool composite patterns

`INVESTMENT-WORKFLOW.md` tells you *which skill* to pick. `AGENT-TOOL-REFERENCE.md` tells you *exactly how to invoke its scripts*.

---

## ⚡ Quick Start (3 minutes)

```bash
# 1. Clone or copy this folder to ~/.claude/skills/
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git ~/.claude/skills

# 2. Run setup script
bash ~/.claude/skills/setup.sh

# 3. Try it in Claude Code
/analyze-stock NVDA
```

---

## 🎯 What This Does

10 specialized skills that work together to give you fund-manager-grade analysis:

| Skill | Purpose | Trigger Keywords |
|-------|---------|-----------------|
| `analyze-stock` | 10-step deep dive on any stock | "analyze X", "is X a buy", "deep dive" |
| `macro-risk-check` | Daily macro radar (VIX/MOVE/yields/USDJPY) | "macro check", "regime read" |
| `find-untapped-thesis` | NOK-style screening (未爆发) | "find next NOK", "undervalued in X" |
| `earnings-prep` | Pre-earnings decision framework | "should I hold X through earnings" |
| `leaps-screen` | LEAPS selection (1-3yr options) | "what LEAPS for X", "stock or LEAPS" |
| `option-wall-analysis` | Max pain + gamma walls | "max pain on X", "option walls" |
| `tax-optimize` | LTCG vs STCG decisions | "should I sell X for tax" |
| `portfolio-audit` | Full portfolio risk audit | "review my portfolio", "what to trim" |
| `narrative-reversal-screen` | ORCL-style reversal screening | "beaten-down with thesis" |
| `sector-rotation-analysis` | Sector heat map + rotation | "what sector to rotate to" |

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
├── analyze-stock/SKILL.md              # 10-step master framework
├── macro-risk-check/SKILL.md           # Daily macro radar
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

Set up via `/schedule` skill:

| Frequency | Skill | When |
|-----------|-------|------|
| Weekly Monday 8am ET | `macro-risk-check` | Pre-market regime read |
| Weekly Friday 4pm ET | `find-untapped-thesis` | Find next ideas |
| Monthly 1st | `portfolio-audit` | Full portfolio audit |
| Pre-event (24h) | `macro-risk-check` | Before Fed/BOJ/major earnings |
| Quarterly | `tax-optimize` | Year-end planning |

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

**Version**: 1.1
**Last updated**: 2026-05-05

### Changelog
- **1.1 (2026-05-05)**: insider_ratio.py v3 (openinsider primary, Form 4 code-aware, 90d default window). New cluster_buy_scan.py. Updated all skills to reflect 7-rule insider methodology (yfinance summary broken, recency dominates, 10b5-1 awareness, BUY rarity, news false positives, yfinance blind spots).
- **1.0 (2026-05-04)**: Initial release.
