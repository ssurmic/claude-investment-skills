---
name: earnings-prep
description: Pre-earnings analysis: pulls consensus, implied move from ATM straddle, historical 8-quarter reactions, what's already priced in, 4 scenarios with probability weighting, position-specific recommendations (hold/trim/hedge/add). Triggers in English ("X reports tomorrow", "should I hold X through earnings", "earnings prep for X", "what's priced in for X earnings", "X earnings expected move") or Chinese ("X 财报前怎么看", "X 财报怎么处理", "X 财报应该减仓吗", "X implied move", "X 财报前分析").
---

# Earnings Prep — Pre-Earnings Decision Framework

## 🔍 Pre-flight checklist — run BEFORE building scenarios or making recommendations

Earnings reactions are ±8-20%. That's not where to skip the discipline layers.

1. **Macro regime** — trigger `macro-warning` skill first. In 🔴 RED regime, even a 20% beat can sell off (AMD 2/3/2026 beat 23%, dropped -17.31%). RED regime → recommend trim/hedge only, no adds regardless of expected reaction.
2. **Insider 60d window** — `~/.claude/skills/review-investment-screenshot/scripts/insider_ratio.py TICKER --window 60` (60d catches pre-earnings ad-hoc activity that 90d dilutes). Pre-earnings C-suite distribution = they know something. Never trust yfinance "% Net Shares" headline (RSU pollutes it). Form 4 code "P" only counts as buy.
3. **Position context first** — if user already holds, lead with their position size + cost basis + holding period. Generic "buy/sell" without position context is useless.
4. **3-tier entry if recommending add** — Don't say "buy after earnings". Map T1 = post-earnings reaction level, T2 = 50DMA support, T3 = 200DMA / pre-earnings level. NEVER "buy at market" on earnings hype.
5. **Tax for trims** — If trimming a position held < 12 months, run `tax-optimize` for STCG vs LTCG impact. STCG ~25-37% federal vs LTCG 15-20%. Often changes the recommendation (hold 30 more days → save 10%).
6. **Sizing** — ≤ 10% single name; if recommending add post-earnings, current allocation must allow it.

**"Look carefully" rule**: the most common pre-earnings mistake is treating "beat consensus" as automatic upside. Always answer "what's already priced in" (Step 4 below) — if Forward P/E expanded 30% in 3 months, the beat is already discounted.

See [README's Hard Rules](../README.md#%EF%B8%8F-hard-rules-never-violate) for the full anti-pattern list.

---

## Goal

Answer 3 questions:
1. **What's the market expecting?** (consensus + implied move)
2. **What's the historical pattern?** (last 8 quarters reactions)
3. **What should I do with my position?** (hold / trim / hedge / add)

## The 5-Step Workflow

### Step 1 — Pull consensus + guidance

**Tools:**
- `WebSearch`: "[ticker] Q[X] FY[YEAR] earnings consensus revenue EPS"
- `mcp__yfmcp__yfinance_get_ticker_info` for current price + earnings date

**Capture:**
| Item | Value |
|---|---|
| Earnings date | YYYY-MM-DD (BMO/AMC) |
| Revenue consensus | $X.XB (+Y% YoY) |
| EPS consensus | $X.XX (+Y% YoY) |
| Company self-guide | $X.XB ± $Y |
| Last quarter beat/miss | Beat by X% / Missed |
| Days away | N |

### Step 2 — Calculate implied move

**Method 1 (preferred): ATM straddle**
- Pull option chain for **first expiry after earnings**
- Find ATM call + ATM put
- Implied move % = (call mid + put mid) / current price × 100
- Convert to $ range: current ± implied move

**Method 2: WebSearch fallback**
- `WebSearch`: "[ticker] earnings expected move implied volatility"

**Output:**
```
Current: $XXX
Implied move: ±X.X%
Expected range: $YYY - $ZZZ
```

### Step 3 — Historical 8-quarter reactions

Pull last 8 quarter reactions. Use `optionsai.com`, `optionslam.com`, or WebSearch.

**Output table:**
| Date | Result | One-day reaction | Notes |
|---|---|---|---|
| 8 quarters back | Beat/Miss | +X% / -X% | Why |
| 7 | ... | ... | ... |
| ... | ... | ... | ... |
| Last quarter | Beat 23% | **-17.31%** | Despite beat (AMD pattern) |

**Key statistics:**
- Average absolute move: X.X%
- Win rate: Y/8 (Z%)
- Largest up: +X% / Largest down: -X%
- **Recent trend**: Last 3-4 quarters skew (often more important than 8q average)

### Step 4 — Predictability assessment (NEW)

Before scenario building, assess **earnings predictability** based on growth model:

| Growth Model | Earnings Predictability | Implication |
|---|---|---|
| **Capacity-bottlenecked** (Optical, OSAT) | 🔴 Low | High variance, "shipments < demand" common |
| **Demand-elastic** (GPU, ASIC) | 🟡 Medium | Can beat but expectations also high |
| **Independent capex** (Memory, Storage) | 🟢 High | Capacity locked, contracts visible |
| **Long-cycle infra** (Power, Materials) | 🟢🟢 Highest | Backlog-driven, low surprise |
| **Recurring SaaS/ARR** | 🟢🟢 Highest | Quarterly steady |

**For each model, watch for these red flags pre-earnings**:
- **Capacity-bottlenecked**: "缺料" / component shortage rumors → likely miss on operational metrics even if EPS beats (FN pattern 5/4/2026)
- **Demand-elastic**: "guide in-line" without raise → "beat but priced in" (AMD pattern)
- **Cyclical**: Inventory buildup at customers → next-quarter weak guide
- **Recurring**: Customer churn news → revenue miss

### Step 5 — What's priced in vs not?

**Critical analysis** — this is what separates pros from amateurs.

**Question 1**: What's already in the price?
- Current Forward P/E vs historical avg
- Distance from 50DMA / 200DMA
- 1Y price change
- If +50% in 3 months → expectations极高

**Question 2**: What's NOT in the price?
- Specific business optionalities
- Geographic recovery (e.g., NVDA China = $0 priced in)
- New product cycles
- M&A rumors

**Examples:**
- **NVDA 5/2026**: China = $0 priced in → any China good news = pure upside
- **ORCL 6/2026**: Capex concerns priced in → any FCF improvement = upside
- **AMD 5/2026**: MI400 + OpenAI已 priced in → 需要"上修指引"才能涨

### Step 5 — Build 4 scenarios with weighting

| Scenario | Probability | Conditions | Reaction | Target Price |
|---|---|---|---|---|
| 🚀 Mega-bull | X% | Big beat + raise + new catalyst | +12 to +20% | $YYY |
| 🟢 Bull | X% | Solid beat + in-line guide | +3 to +8% | $YYY |
| 🟡 Flat/-Sell | X% | Beat but priced-in | -3 to -10% | $YYY |
| 🔴 Bear | X% | Miss or guide cut | -10 to -20% | $YYY |

**Weighted average price** = Σ(probability × target)
**If weighted < current** → 期望值是负的，市场已 priced in 利好

## Position-Specific Recommendations

Based on the 4 scenarios, give SPECIFIC action:

### Already long the stock?
| Pre-earnings setup | Action |
|---|---|
| Already +30%+ in last month | Trim 25-50% before |
| At 1Y high + earnings ≤7d | Trim 25-50% (Rule #5 from review-screenshot) |
| Healthy trend, not parabolic | Hold + set 50DMA stop |
| Below 50DMA, beaten down | Hold, low expectations = upside skew |
| Insider distributed pre-earnings | Trim, they know something |

### Want to make a directional bet?
| Setup | Strategy |
|---|---|
| Bullish + IV reasonable | Long call (1-2 weeks out) |
| Bullish + IV very high | Call spread (cap upside, reduce cost) |
| Bullish + already long stock | Buy upside call as add (don't sell stock) |
| Bearish + IV high | Put spread (cheaper than naked put) |
| Uncertain but want to play vol | Strangle or straddle (rare, expensive) |

### Want to hedge existing long position?
| Setup | Hedge |
|---|---|
| Want full protection | Long put at ATM (expensive but full hedge) |
| Want protection at lower cost | Put spread (gives up tail) |
| Have core, willing to sell at +X% | Covered call (income, caps upside) |
| Want to stay in but reduce delta | Sell some shares + use proceeds for puts |

## Output format

```markdown
# [TICKER] Earnings Prep — [Date]
**Earnings: [Date BMO/AMC] | Days away: N**

## TL;DR
[One paragraph: what to do with current position + size]

## Consensus
| Revenue | EPS | YoY |

## Implied Move
- ATM straddle: ±X.X%
- Range: $YYY - $ZZZ

## Historical Pattern (Last 8 Quarters)
[Table]
- Avg abs move: X.X%
- Win rate: Y/8

## What's Priced In
- ✅ Already in price: [list]
- ❌ NOT priced in: [list — these are upside catalysts]

## 4 Scenarios
| Scenario | Prob | Reaction | Target |
| Mega-bull | X% | +X% | $Y |
| Bull | X% | +X% | $Y |
| Flat | X% | -X% | $Y |
| Bear | X% | -X% | $Y |
**Weighted avg target: $X (vs current $Y) → +/-Z%**

## My Recommendation
- **If I'm long [N shares]**: [trim X / hold / add Y]
- **If I'm not in**: [skip / play call spread / wait]
- **Specific orders**: [exact ticker, qty, price, type]

## Watch list (next 24h)
- [Pre-market reaction signals]
- [Key levels: $X = breakout, $Y = breakdown]
```

## Hard rules

1. **Pre-flight before recommending.** Skip the checklist at top = incomplete call. Macro + insider 60d + position context are not optional.
2. **Never recommend "hold through earnings" without setting a stop.** Implied move is real money.
3. **Compare last 3-4 quarters more heavily than 8q avg.** Pattern recently changed = more relevant.
4. **Big beats sometimes lead to big drops.** AMD 2/3/2026: EPS beat 23% → -17.31%. Always check "is this priced in".
5. **In 🔴 RED macro regime, no new longs** regardless of earnings setup — trim/hedge only. Document the regime call in the output.
6. **IV crush is real.** Buy options 5+ days out, sell into earnings hype.
7. **Never sell naked puts on stocks you wouldn't own.** Sell put = "I want to buy at $X". If $X isn't a level you'd actually buy at, don't sell.
8. **Cite implied move source.** Either ATM straddle calculation or WebSearch with link.
9. **When user is already long**: lead with their position, not generic analysis.
10. **3-tier entry for any add recommendation.** "Buy at market post-earnings" = wrong answer. Always map T1/T2/T3.
11. **Tax-aware trims.** If position held < 12 months, surface STCG impact in the recommendation, not as footnote.

## Common pitfalls

| Pitfall | Example | Lesson |
|---|---|---|
| "Earnings will beat, stock will rise" | AMD 2/3/26 (beat 23%, -17.31%) | Beat alone is not enough |
| "Sell put before earnings = easy money" | Multiple times | Until it's not, then you lose 10x premium |
| Ignoring IV crush | Bought ATM call before earnings | Need stock to move > implied + IV crush |
| Not checking insider | Dropping after CFO sold $5M pre-earnings | Insider sold for a reason |
| Only checking 8q avg | Recent trend was -10%, -8%, -17% | Trend > average |

## Tool cheat-sheet

| Need | Tool |
|---|---|
| Current price + earnings date | `mcp__yfmcp__yfinance_get_ticker_info` |
| Option chain for straddle | `mcp__yfmcp__yfinance_get_option_chain` |
| Historical earnings reactions | `WebSearch`: "optionslam [ticker] earnings history" |
| Implied move | Calculate from straddle OR `WebSearch`: "[ticker] expected move" |
| Consensus | `WebSearch`: "[ticker] Q[X] earnings consensus" |
| Insider pre-earnings | `~/.claude/skills/review-investment-screenshot/scripts/insider_ratio.py "TICKER" --window 60` (60d window catches pre-earnings ad-hoc activity; default is 90d) |

## When to invoke

- **User asks**: "Should I hold X through earnings?"
- **User asks**: "X reports tomorrow, what do I do?"
- **User asks**: "Should I sell put before earnings?"
- **Auto**: 7 days before any earnings of a stock the user holds
- **Auto**: Day-of for any stock with options position expiring within 1 month of earnings
