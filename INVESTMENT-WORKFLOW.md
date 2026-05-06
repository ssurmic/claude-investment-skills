# Investment Skills — Streamlined Workflow

**Version 1.2** | Built 2026-05-04, last tuned 2026-05-06

This is the master index for the investment analysis skill system. All skills work together — pick the right one for the question.

## 🤖 If you are an AI agent

**Read [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md) first** — it has natural-language → CLI mappings (EN + CN) for every script, with parameter specs and example utterance translations. Use it whenever you need to invoke a tool from a user utterance.

This file (`INVESTMENT-WORKFLOW.md`) tells you *which skill* fits a question. `AGENT-TOOL-REFERENCE.md` tells you *exactly how to call its tools*.

## 🎯 The Decision Tree

```
User question → Which skill?

"Analyze X" / "Is X a buy?" / "Deep dive on X"
   → analyze-stock (10-step master framework)

"Find me the next NOK" / "What's 未爆发 in [theme]"
   → find-untapped-thesis

"Should I hold X through earnings?"
"X reports tomorrow, what do I do?"
   → earnings-prep

"What LEAPS for X?" / "Stock or LEAPS?"
   → leaps-screen

"Where's max pain?" / "Option walls?"
"Where will X go this week?"
   → option-wall-analysis

"Macro looks shaky / regime check"
   → macro-risk-check

"Should I sell X now or wait for tax?"
   → tax-optimize

"Review my screenshot / portfolio"
   → review-investment-screenshot

"Find swing/position/LEAPS opportunities"
   → find-alpha (existing)
```

## 📚 The Skills Stack

### Tier 1 — Single-Stock Analysis
| Skill | Use case | Input |
|---|---|---|
| `analyze-stock` | Master 10-step deep dive | Ticker |
| `earnings-prep` | Pre-earnings decision | Ticker + position |
| `leaps-screen` | LEAPS selection | Ticker + thesis |
| `option-wall-analysis` | Short-term levels | Ticker |

### Tier 2 — Multi-Stock Discovery
| Skill | Use case | Input |
|---|---|---|
| `find-untapped-thesis` | NOK-style screening | Theme |
| `find-alpha` | Time-horizon based alpha | (auto) |

### Tier 3 — Portfolio Operations
| Skill | Use case | Input |
|---|---|---|
| `review-investment-screenshot` | Full portfolio audit | Screenshot |
| `tax-optimize` | Trim with tax in mind | Position + buy date |
| `macro-risk-check` | Regime read | (none) |

### Tier 4 — Automation
| Skill | Use case | Input |
|---|---|---|
| `schedule` | Recurring agents | When + what |
| `loop` | Iterative tasks | Prompt |

## 🔥 The Master Workflow (Standard Stock Analysis)

When user gives you a ticker and asks "what about X":

```
Step 1: Run macro-risk-check first
   → If RED: be very conservative on entry
   → If GREEN: proceed

Step 2: Run analyze-stock (10 steps)
   → Get the full picture

Step 3: If user is interested AND has options thesis:
   → Run leaps-screen for long-term play
   → Run option-wall-analysis for short-term levels
   → Run earnings-prep if earnings within 30 days

Step 4: If user wants to act:
   → Calculate position size
   → Check tax-optimize if trimming existing position
```

## 🎨 The Mental Model

```
         Macro Backdrop  ←─ Run macro-risk-check
              │
              ▼
        Year Theme (2026: K-shape, AI factory, 1973 risk)
              │
              ▼
         Sector Rotation
              │
              ▼
       Individual Stock  ←─ Run analyze-stock
              │
        ┌─────┼─────┐
        ▼     ▼     ▼
    Insider  Catalyst  Valuation
        │     │     │
        ▼     ▼     ▼
       Entry Plan (3-tier)
              │
        ┌─────┼─────┐
        ▼     ▼     ▼
      Stock LEAPS  Hedge
              │
              ▼
       Tax-aware execution  ←─ Run tax-optimize
              │
              ▼
        Position monitoring
              │
              ▼
       Pre-earnings prep  ←─ Run earnings-prep (recurring)
```

## 🔧 Industry Chain / Supply-Demand Mechanics (NEW)

Different sub-sectors have fundamentally different growth dynamics. Always identify the **growth model** before applying generic AI thesis:

| Growth Model | Examples | Predictability | When to buy |
|---|---|---|---|
| **Long-cycle infra** | Power utilities (CEG/EQT/AEP), pipelines (ET/WMB), materials (APD/LIN) | 🟢🟢 Highest | When sector is laggard |
| **Independent capacity** | Memory (MU), HDD (WDC), some semis | 🟢 High | Mid-cycle |
| **Demand-elastic + pricing power** | GPUs (NVDA), ASICs (AVGO/MRVL) | 🟢 High | Pre-cycle |
| **Recurring SaaS/ARR** | Oracle DB, EDA (CDNS/SNPS) | 🟢🟢 Highest | Anytime if priced right |
| **Cyclical commodity** | Copper, oil, DRAM/NAND cycles | 🟡 Medium | At cycle bottom only |
| **Capacity-bottlenecked downstream** | Optical modules (LITE/FN), OSAT (AMKR/ASE) | 🔴 Low | After 缺料 dust settles |
| **Single-customer concentration** | Neocloud (CRWV/APLD) | 🔴 Low | Avoid unless extreme value |

**Critical insight**: Same "AI thesis" can have very different earnings trajectories.
- Memory rides AI AND has own capacity expansion → predictable beats
- Optical rides AI BUT is capacity-bottlenecked by GPU schedule → "缺料" disappointments

**Where to find best predictability for the price**:
1. AI Power (CEG/EQT/AEP) — locked PPAs, no earnings surprise risk
2. Memory (MU/WDC) — sold out for years, capex visible
3. Materials (APD/LIN) — multi-decade contracts

**Use this matrix**: Run `sector-rotation-analysis` for full breakdown of each sub-sector's mechanics.

## 🏆 The Winning Patterns (Recognize These)

### Pattern 1: Untapped thesis (BUY)
- Forward P/E < 25
- 1Y return < 50%
- Real catalyst (concrete contracts, not narrative)
- Institutional ownership < 30%
- **Skill**: find-untapped-thesis → analyze-stock

### Pattern 2: Narrative reversal (BUY)
- Stock down -30% to -50% from 52W high
- Worst-case priced in
- Catalyst still intact
- Reversal signal (50DMA up-cross, first higher low, insider buying)
- **Skill**: narrative-reversal-screen → analyze-stock → leaps-screen

### Pattern 3: Top distribution (SELL/AVOID)
- Stock at 52W high
- Insider 100% selling (CEO + CFO + Director)
- 1Y > 200%
- Even great earnings → -10% to -20% (priced in)
- **Skill**: review-investment-screenshot → tax-optimize

### Pattern 4: Beat-but-priced-in earnings (HEDGE)
- Earnings beat consensus
- Guide in-line, no upward revision
- Stock up 60%+ in 30 days pre-earnings
- Implied move >7%
- **Skill**: earnings-prep (recommend hedge with put)

### Pattern 5: Macro tail risk (CASH UP)
- USD/JPY < 153 (yen carry unwind starting)
- VIX > 22
- 30Y > 5.10%
- BOJ rate hike imminent
- **Skill**: macro-risk-check (raise cash to 30-40%)

## 🚨 The Hard Rules (Never Violate)

1. **Always run `insider_ratio.py --window 90`** (openinsider primary) — never trust yfinance summary
2. **Form 4 code "P" only counts as buy** — `A`/`M`/`F` are RSU/exercise/tax, NOT buy signals (verified false positive: UNH "10 directors" 4/1/2026 was DSU grants)
3. **Verify any "cluster buy" headline** at openinsider.com/[TICKER] before believing — news routinely conflates compensation with conviction
4. **For scheduled sales**, check secform4.com for 10b5-1 footnote before treating as bearish signal
5. **Always check macro before adding** — even great stocks fail in red regime
6. **Position size cap**: max 10% single stock, max 5% high-beta
7. **3-tier entry**: never "buy at market" without 50DMA / 200DMA fallback
8. **Concrete evidence > narrative**: "AI is good" ≠ thesis
9. **Cite all sources**: every macro claim has WebSearch link
10. **Tax-aware exits**: especially for high earners
11. **Hedge > sell** for short-term taxable positions

## 📅 Recommended Recurring Schedule (use `schedule` skill)

| Frequency | Skill | When |
|---|---|---|
| Weekly Monday 8am ET | `macro-risk-check` | Pre-market regime read |
| Weekly Friday 4pm ET | `find-untapped-thesis` | Find next ideas |
| Monthly 1st | `review-investment-screenshot` | Full portfolio audit |
| Pre-event | `earnings-prep` | 7d before any held earnings |
| Pre-Fed/BOJ | `macro-risk-check` | 24h before |
| Quarterly | `tax-optimize` | Year-end + each quarter |

## 🛠 Underlying Tools

### MCP Servers
- `mcp__yfmcp__*` — yfinance data (price, options, news, info)
- `WebSearch` — macro events, news, contracts
- `WebFetch` — IR pages, SEC filings

### Insider Data Sources (in order of trust)
1. **openinsider.com** — primary. Form 4 with transaction codes (P/S/A/M/F/G). Free, no auth. Used by both scripts below.
2. **secform4.com** — backup. Shows 10b5-1 plan footnote disclosures.
3. **stocktitan.net** — readable Form 4 narratives.
4. **yfinance** `get_insider_transactions()` — fallback only. Has known blind spots (missed real cluster buys at NKE/UNH/PLTR).

### Scripts (in `~/.claude/skills/review-investment-screenshot/scripts/`)
- **`insider_ratio.py`** (v3) — strict open-market $ ratio. Default `--window 90`, `--source openinsider` (default), `--source both` for cross-verification. Form 4 code-aware (only `P` counts as buy).
- **`cluster_buy_scan.py`** — hits openinsider.com/latest-cluster-buys to find market-wide MRVL/CEVA-style cluster buys. Use `--days 30 --min-value 500000 --min-insiders 3 --detail --enrich --senior-only`.
- `quote_pull.py` — batch live quotes + MAs
- `option_walls.py` — top OI clusters
- `max_pain.py` — max pain calculation

### Python Environment
- `/tmp/.insider_venv` — Python 3.9 + yfinance
- Setup: `bash ~/.claude/skills/setup.sh` (one-click; installs yfinance + verifies scripts)

## 📖 Year Theme Framework

**Generic macro framework** (apply each year — populate with current themes):

Annual themes to map every stock against:
- **K-shape divergence** — Within sectors, winners crush losers; pick the winner side
- **AI = factory mode** — Hyperscalers buy compute like factories buy machines (capex >> opex)
- **Power as bottleneck** — Whichever input is supply-constrained (electricity, fuel, materials) reprices upward
- **Demand destruction risk windows** — Monitor oil/inflation/recession indicators
- **Carry trade structures** — Track JPY borrowing flows, BOJ policy

**Update annually**: Replace with current-year specific themes when calendar rolls. Track:
- Top 3-5 macro risks for the year
- Top 3-5 sub-sector tailwinds
- Specific named stocks fitting each theme

## 🔄 Future Improvements (TODO)

- [ ] Add `narrative-reversal-screen` skill (ORCL-style)
- [ ] Add `sector-rotation-analysis` skill
- [ ] Add `portfolio-audit` skill (formalize from review-screenshot)
- [ ] Add `bond-yield-analysis` script (for term premium tracking)
- [ ] Add `calendar-events.py` (auto-pull next 30 days events)
- [ ] Sync to GitHub repo `claude-investment-skills`
- [ ] Add example `examples/` folder with real cases

## 💬 Memory References

User's memory system at `/Users/zzizhao/.claude/projects/-Volumes-workplace-invest/memory/`:
- `user_investment_reviews.md` — review preferences
- `feedback_insider_methodology.md` — insider methodology
- `macro_framework_2026.md` — Annual macro theme framework (update yearly)
- `feedback_insider_methodology.md` — 7 rules: openinsider primary, code-aware (P only), 10b5-1 awareness, recency weighting, BUY-rarity, news-headline skepticism, yfinance blind spots
- (To add) `user_position_thesis.md` — current position theses

## 📜 Operating Philosophy

> "Selling early isn't the worst outcome — missing the next bottom is."
> — Locked profits at +20% are recoverable; missing a -25% buying opportunity is not.

> "Hold the high-conviction core. Trim leverage and noise."
> — Never fully de-risk a winning long-term thesis on macro fear alone.

> "Long-cycle structural trends are measured in years, not quarters."
> — Don't let one earnings miss invalidate a multi-year thesis.

> "Paradigm shifts are non-reversible — but valuations rotate within them."
> — Real innovation persists; mean reversion still applies to multiples.

## ✅ How To Use This Document

1. **First-time user**: Read this top-to-bottom, then try one skill
2. **Recurring user**: Just refer to "Decision Tree" section
3. **Sharing with friends**: Send them this doc + the skills folder
4. **Updating**: Add new skills here when created, update theme yearly

---

**Built with**: Claude Code — top-down macro-aware investment skill system
