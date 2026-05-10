# Introduction — What is this repo?

> 5-minute read for people who just found this and want to know if it's for them.

[中文版 / Chinese Version](./INTRODUCTION-zh.md)

---

## What this is

A set of **investment analysis skills** for [Claude Code](https://docs.claude.com/claude-code) — Anthropic's AI coding assistant. After installing this repo, you can talk to Claude in plain English (or Chinese) and have it pull live market data, analyze stocks, screen for ideas, prep for earnings, and audit your portfolio — all with a fund-manager-grade discipline.

It's not a trading bot. It's a **thinking partner** that pulls live data, runs disciplined frameworks, and gives you opinionated takes — so you make better decisions faster.

---

## What you can ask it

You don't memorize commands. You just talk. A few real examples:

```
You: "analyze NVDA"
→ Claude pulls NVDA's macro context, valuation, insider activity, catalysts,
  and gives you a 3-tier entry plan with LEAPS option suggestions.

You: "macro warning"
→ Claude scans 8 macro layers (NDX P/E, VIX, F&G, credit spreads, breadth,
  yen carry, sector rotation, CTA flows) and returns a regime tag with
  specific position-sizing actions.

You: "audit my portfolio" (paste a screenshot)
→ Claude computes concentration risk, factor exposures, hedge effectiveness,
  and gives you a trim list with $ amounts and reasons.

You: "AMD reports tomorrow, what do I do?"
→ Claude pulls implied move, 8-quarter history, scenarios, and gives
  you a hold/trim/hedge recommendation tailored to your position.

You: "找未爆发的 AI 电力股" (Chinese: find untapped AI Power names)
→ Claude screens for low Forward P/E + lagging 1Y returns + concrete
  catalyst + low institutional ownership, returns top 3 candidates.
```

The system understands both **English** and **Chinese**. You can switch mid-conversation.

---

## Why this exists

Most investment AI tools are one of two extremes:

1. **Autonomous bots** — opaque, overconfident, often wrong, hard to audit
2. **Generic chatbots** — shallow takes, hallucinated numbers, no live data

This repo is the middle path:

- **Live data**, not training data — every answer pulls from yfinance, FRED, openinsider in real time
- **Deterministic Python where it matters** (insider analysis, macro scoring) — auditable, testable, repeatable
- **Opinionated frameworks** that codify expensive lessons (insider rules from real misses, macro thresholds from real cycles)
- **Top-down discipline** — macro before stock, regime before adding, valuation before momentum
- **Bilingual by design** — every trigger phrase exists in EN + CN

---

## The skills (one-line summary)

| Skill | What it does |
|---|---|
| `analyze-stock` | 10-step deep dive on any US-listed stock |
| `macro-risk-check` | News-driven daily macro scan (VIX, yields, USDJPY) |
| `macro-warning` | 8-layer batch-mode pullback radar (CAPE, F&G, breadth, sectors) |
| `find-alpha` | Weekly screen across 3 horizons (swing / position / LEAPS) |
| `find-untapped-thesis` | "Next NOK" screening — undervalued names within a theme |
| `narrative-reversal-screen` | Beaten-down stocks with intact catalyst, finding bottoms |
| `sector-rotation-analysis` | 11-sector heat map + rotation pairs |
| `earnings-prep` | Pre-earnings: implied move, scenarios, hold/trim/hedge call |
| `leaps-screen` | Long-dated options strike selection with payoff math |
| `option-wall-analysis` | Max pain + gamma walls for short-term levels |
| `portfolio-audit` | Concentration / factor / Greeks / stress-test review |
| `tax-optimize` | LTCG vs STCG decision with state-aware math |
| `review-investment-screenshot` | Quick portfolio review from a screenshot |
| `price-alert` | Set parameterized price alerts; GitHub Actions + Telegram push (any ticker, any threshold/%). See [SETUP.md](./price-alert/SETUP.md) for one-time bot setup. |

Plus shared scripts (under the hood):
- `insider_ratio.py` — Form-4-aware insider buy/sell analysis
- `cluster_buy_scan.py` — market-wide cluster buy hunter
- `macro_pull.py` — direct-API macro indicator puller
- `max_pain.py`, `option_walls.py`, `quote_pull.py` — options helpers

---

## Install (3 minutes)

You need: macOS or Linux, Python 3.9+, [Claude Code](https://docs.claude.com/claude-code/install) already installed.

```bash
# 1. Clone to where Claude Code looks for skills
git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills

# 2. Run setup (creates Python venv, installs yfinance, verifies everything)
bash ~/.claude/skills/setup.sh

# 3. Talk to Claude
# Open Claude Code, then just type:
analyze NVDA
```

That's it. The setup script verifies all 13 skills are in place and the helper scripts work.

---

## How natural language → skill works (the magic)

You don't type slash-commands. You just talk. Here's why that works:

1. **Each skill has a `description:` field** in its frontmatter listing trigger phrases (English + Chinese).
2. **Claude Code matches your input** against all skill descriptions and picks the best fit.
3. **The matched skill loads its full instructions** and runs (pulling data, running analysis, returning the answer).

For example, the `macro-warning` skill description includes:
```
Triggers in English ("macro warning", "regime check", "is the market at peak",
"should I take profits", "is it time to buy") or Chinese ("宏观警报",
"市场是不是顶了", "该不该减仓", "regime 怎么样", "该入场吗")
```

So **any of these phrasings** invokes the same skill. You don't need to remember exact words. If your phrasing is close, it'll match. If ambiguous, Claude asks.

This also works for **composite phrasings**:
- "I want to buy AMD before earnings, is the macro safe?" → triggers `macro-risk-check` + `earnings-prep` in sequence.

The full mapping is in [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md).

---

## What this repo is NOT

- ❌ A trading bot — no orders are placed, ever
- ❌ Financial advice — these are research tools
- ❌ A backtest engine — focused on real-time research, not historical sim
- ❌ Crypto-focused — built for US equities + ETFs + options
- ❌ Day-trading — designed for swing / position / LEAPS horizons
- ❌ A black box — every number cites a source URL

---

## Where to go next

Pick the document that matches your role:

- **Investor / casual user** → keep reading [`README.md`](./README.md) for example prompts and workflows
- **AI agent / CLI integrator** → read [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md) for exact CLI contracts
- **Skill developer** → read [`ARCHITECTURE.md`](./ARCHITECTURE.md) for design decisions and data source reasoning
- **Skill picker** → read [`INVESTMENT-WORKFLOW.md`](./INVESTMENT-WORKFLOW.md) for the master decision tree
- **Each skill's mechanics** → read the skill's own `SKILL.md`

---

## Disclaimer

These tools are for **personal investment research**. They do not constitute financial advice. Past performance doesn't guarantee future results. Consult a licensed financial advisor for actual investment decisions.

The framework is opinionated — it reflects one specific style (top-down, valuation-aware, macro-conscious, options-friendly). It is **not** designed for day trading, pure quantitative strategies, crypto-only portfolios, or forex.
