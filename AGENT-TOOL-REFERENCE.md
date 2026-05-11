# Agent Tool Reference — Natural Language → CLI Contract

**For**: any AI agent (Claude Code, custom agents, CLI wrappers, schedulers) that needs to translate user utterances into precise tool invocations.

**Goal**: every tool has (1) trigger phrases in EN + CN, (2) exact command template, (3) parameter spec, (4) example mappings. New languages map to the canonical English intent and reuse the same templates.

**Loaded by**: `INVESTMENT-WORKFLOW.md`, `README.md`, `README-zh.md`. Read this first when generating any tool call.

---

## Resolution algorithm (use this for every user utterance)

```
1. Parse utterance → identify intent (single-stock check / cluster hunt / max pain / ...)
2. Extract entities (ticker symbol, days, $ threshold, etc.)
3. Look up the canonical command template from the per-tool sections below
4. Substitute entities into template
5. If ambiguous, prefer defaults documented under "Defaults" rather than asking
6. Run command, parse JSON output, format response in the user's language
```

If the utterance is in a language other than EN/CN, mentally translate to the canonical English intent first, then look up the template.

---

## Quick Lookup Table

### Direct CLI tools (Tools 1-6)

| Intent (canonical EN) | Bilingual triggers | Tool |
|---|---|---|
| **Daily macro warning / pullback radar** | EN: "macro warning / regime check / is the market at peak / should I take profits" · CN: "宏观警报 / 市场是不是顶了 / 该不该减仓 / regime 怎么样" | **`macro-warning` skill (batch-friendly)** |
| Check insider activity for stock(s) | EN: "insider check / insider trading on X / who's buying X" · CN: "X 内部交易 / X 高管买卖 / X insider 怎么样" | `insider_ratio.py` |
| Hunt market-wide cluster buys | EN: "find cluster buys / who are insiders buying / where's smart money" · CN: "找 cluster buy / 内部人在买什么 / 最近高管买入" | `cluster_buy_scan.py` |
| Live quotes + moving averages | EN: "quote X / price of X / where is X trading" · CN: "X 现在多少 / X 报价 / X 价格" | `quote_pull.py` |
| Option walls / OI clusters | EN: "option walls X / where will X pin / gamma map X" · CN: "X 期权墙 / X 期权磁吸位" | `option_walls.py` |
| Max pain calculation | EN: "max pain X / pin level X" · CN: "X 的 max pain / X OPEX 目标" | `max_pain.py` |
| **Price alerts (add/list/cancel)** | EN: "alert me when X hits Y / notify if X drops Z% / list my alerts" · CN: "X 跌到 Y 通知我 / 我的 alerts / 取消 X" | **`price-alert/` suite (Tool 6)** |

### NL-only skills (Claude Code matches via SKILL.md description)

| Intent | Bilingual triggers | Skill |
|---|---|---|
| Single-stock deep dive | EN: "analyze X / is X a buy / deep dive on X" · CN: "分析 X / X 怎么样 / X 能买吗" | `analyze-stock` |
| Pre-earnings decision | EN: "earnings prep X / should I hold X through earnings" · CN: "X 财报前怎么看 / X implied move" | `earnings-prep` |
| 3-horizon discovery | EN: "find alpha / weekly alpha scan" · CN: "找 alpha / 本周 alpha 扫一下" | `find-alpha` |
| LEAPS strike selection | EN: "LEAPS for X / stock or LEAPS for X" · CN: "X 买什么 LEAPS / X 的长期 call" | `leaps-screen` |
| Theme-laggard hunt | EN: "find untapped X / next NOK" · CN: "找未爆发的 X / 下一个 NOK" | `find-untapped-thesis` |
| Reversal screen | EN: "find reversal plays / beaten-down with thesis" · CN: "找暴跌反转股 / ORCL 那种反转" | `narrative-reversal-screen` |
| Sector rotation | EN: "sector rotation / what sector to add" · CN: "板块轮动 / 该买哪个板块" | `sector-rotation-analysis` |
| Portfolio risk audit | EN: "review my portfolio / what should I trim" · CN: "审一下我的组合 / 该减什么仓" | `portfolio-audit` |
| Tax-aware trim decision | EN: "should I sell X for tax / LTCG vs STCG on X" · CN: "X 减仓税务 / X 减仓最省税" | `tax-optimize` |
| Macro news-driven | EN: "macro check / risk on or off" · CN: "看一下宏观 / 市场风险怎么样" | `macro-risk-check` |
| Screenshot portfolio review | (paste image + "review") · (发截图 + "看一下") | `review-investment-screenshot` |

Detailed triggers + entry rules for the NL skills are in the [**Skill Catalog**](#skill-catalog--nl-only-skills-not-cli-tools) section below.

---

## Tool 1: `insider_ratio.py` — single/multi-ticker insider check

### Triggers (natural language)

**English**: "insider trading on X", "is X being bought by insiders", "who's buying X", "check insider activity for X", "insider ratio X", "X insider check", "are insiders selling X", "form 4 on X"

**Chinese**: "X 内部交易", "X 高管在卖吗", "X insider 怎么样", "X 高管买卖", "查一下 X 的 insider", "X 这只股的高管动作", "最近 X 高管有买入吗"

**Multi-ticker triggers**: "insider check on X, Y, Z" / "扫一下 X Y Z 的高管"

### Canonical command

```bash
uv run --with yfinance python ~/.claude/skills/review-investment-screenshot/scripts/insider_ratio.py "TICKER1,TICKER2,..." [flags]
```

### Parameters

| Flag | Type | Default | When to override |
|---|---|---|---|
| (positional) | comma-separated tickers | required | Always pass uppercase, comma-separated, no spaces |
| `--window N` | days | `90` | User says "last month" → 30; "last week" → 7; "last quarter" → 90; "last year" → 365 |
| `--since YYYY-MM-DD` | date | derived from --window | When user gives an explicit start date (e.g. "since the crash on April 8") |
| `--source openinsider` | source | `openinsider` (default) | Keep default unless user explicitly asks otherwise |
| `--source yfinance` | source | — | Only when openinsider is unreachable |
| `--source both` | source | — | High-stakes calls / when user says "cross-verify" / "double check" |
| `--min-buy-size N` | dollars | `25000` | User says "include all buys" → 0; "only big buys" → 100000; "conviction only" → 250000 |

### Output schema (JSON, per ticker)

```
{
  TICKER: {
    name, last, fwd_pe, target, fiftyTwoWeekHigh,
    om_buy_count, om_sell_count,
    om_buy_total_$, om_sell_total_$,
    buy_buckets_$:  {0-30d, 30-90d, 90-180d, >180d},
    sell_buckets_$: {0-30d, 30-90d, 90-180d, >180d},
    recent_90d_buy_$, recent_90d_sell_$,
    all_recent_buyers, meaningful_recent_buyers,
    meaningful_buy_total_$, micro_buy_total_$,
    buy_to_sell_ratio,
    verdict,                       # ALWAYS read this first
    top_buys,                      # sorted by VALUE desc
    top_meaningful_buys,           # ≥min-buy-size only
    top_sells
  }
}
```

### Verdict ladder (what to tell the user)

| Verdict string | Meaning | User-facing summary |
|---|---|---|
| `RECENT CLUSTER BUY ✅✅✅` | 3+ insiders ≥$25K each, $500K+ aggregate | "Strong cluster buy signal — multiple senior insiders coordinated" |
| `RECENT STRONG BUY ✅✅` | meaningful buy ≥ 2× recent sell | "Strong buy signal" |
| `RECENT BUY-LEAN ✅` | meaningful buy ≥ recent sell | "Mild buy lean" |
| `MICRO-BUYS ONLY` | all buys <$25K | "Only ESPP/automated micro-buys — low signal" |
| `RECENT HEAVY DISTRIBUTION 🔴` | buy < 10% of sell | "Heavy distribution" |
| `RECENT INSIDERS-ONLY-SELLING 🔴` | 0 buys, sells exist | "Insiders selling — verify 10b5-1 at secform4.com" |
| `OLD SELLS ONLY` | no recent activity, old sells | "Neutral — old 10b5-1 likely" |
| `NO ACTIVITY (in window)` | nothing in window | "No insider activity in window" |
| `MIXED` | other | "Mixed signal" |

### Common pattern mappings

| User says | → Command |
|---|---|
| "Insider check on NVDA" | `insider_ratio.py "NVDA" --window 90` |
| "扫一下 NVDA, AMD, AVGO 的内部交易" | `insider_ratio.py "NVDA,AMD,AVGO" --window 90` |
| "TSM 最近高管在买吗，深度看一下" | `insider_ratio.py "TSM" --window 90 --source both` |
| "Are insiders buying CRM, only conviction-level" | `insider_ratio.py "CRM" --window 90 --min-buy-size 100000` |
| "Show me ALL insider activity at TSM, even small" | `insider_ratio.py "TSM" --window 90 --min-buy-size 0` |
| "Insider check on PLTR since Feb 1" | `insider_ratio.py "PLTR" --since 2026-02-01` |
| "1 year of insider history for AMKR" | `insider_ratio.py "AMKR" --window 365` |

---

## Tool 2: `cluster_buy_scan.py` — market-wide cluster buy hunter

### Triggers (natural language)

**English**: "find cluster buys", "where are insiders buying", "smart money is loading up where", "cluster buy scan", "find next MRVL setup", "weekly insider buy scan", "any cluster buys recently", "show me clusters this month"

**Chinese**: "找 cluster buy", "内部人在买什么", "最近哪些股票被高管买入", "扫一下市场 cluster buy", "找下一个 MRVL", "高管集中买入扫描", "这个月有哪些 cluster"

### Canonical command

```bash
uv run --with yfinance python ~/.claude/skills/review-investment-screenshot/scripts/cluster_buy_scan.py [flags]
```

### Parameters

| Flag | Type | Default | When to override |
|---|---|---|---|
| `--days N` | days | `30` | "this week" → 7; "this quarter" → 90; "this year" → 365 |
| `--min-value N` | dollars | `250000` | User wants stricter ("only big clusters") → 1000000; looser ("include small caps") → 100000 |
| `--min-insiders N` | count | `2` | "true cluster only" → 3; "any 2+ buying" → 2 (default) |
| `--detail` | flag | off | Add when user wants per-insider breakdown ("show me who specifically is buying"). Costs extra HTTP calls. |
| `--enrich` | flag | off | Add when user wants price/PE/52wHigh context. Default to ON for analysis questions, OFF for lists. |
| `--senior-only` | flag | off | Add when user says "only CEO/CFO/Chair clusters" / "high-conviction only" / "顶级管理层 cluster". Forces --detail. |

### Output schema

```
{
  params: {...},
  n_clusters: int,
  clusters: [
    {
      ticker, company, industry,
      n_insiders, total_buy_$,
      trade_date, filing_date,
      price, qty,
      // if --detail:
      buyers: [{date, insider, title, value, is_senior}],
      senior_buyer_count: int,
      // if --enrich:
      price_now, fwd_pe, fiftyTwoWeekHigh, mcap, target, pct_off_52wHigh
    }
  ]
}
```

### Common pattern mappings

| User says | → Command |
|---|---|
| "Find cluster buys this month" | `cluster_buy_scan.py --days 30 --min-value 250000 --min-insiders 2 --enrich` |
| "Show me only the high-conviction clusters" | `cluster_buy_scan.py --days 30 --min-value 1000000 --min-insiders 3 --senior-only --enrich` |
| "Quick cluster scan, no detail" | `cluster_buy_scan.py --days 30 --min-value 500000 --min-insiders 3` |
| "Who are the senior insiders buying right now" | `cluster_buy_scan.py --days 30 --min-value 250000 --min-insiders 2 --senior-only --enrich` |
| "本周有什么 cluster buy" | `cluster_buy_scan.py --days 7 --min-value 250000 --min-insiders 2 --enrich` |
| "AI 板块有 cluster buy 吗" | First run scan, then filter results by industry containing "Semiconductor"/"Computer"/"Software". Tool itself doesn't filter by industry — agent post-filters. |

### Performance note

`--detail` and `--senior-only` issue N+1 HTTP requests (one per ticker). For 30+ clusters this can take 30-60s. Default to OFF unless user explicitly wants per-insider info.

---

## Tool 3: `quote_pull.py` — batch quotes + moving averages

### Triggers

**English**: "current price of X", "quote X", "where is X trading", "X stock price now", "pull quotes for X, Y, Z", "live price"

**Chinese**: "X 现在多少", "X 报价", "X 价格", "X 现价", "拉一下 X Y Z 的价格"

### Canonical command

```bash
uv run --with yfinance python ~/.claude/skills/review-investment-screenshot/scripts/quote_pull.py "TICKER1,TICKER2,..."
```

### Parameters

Just comma-separated tickers, no flags. Always uppercase.

### Common pattern mappings

| User says | → Command |
|---|---|
| "Quote NVDA" | `quote_pull.py "NVDA"` |
| "Pull MSFT, AAPL, GOOGL" | `quote_pull.py "MSFT,AAPL,GOOGL"` |
| "AMD AVGO MRVL 现价" | `quote_pull.py "AMD,AVGO,MRVL"` |

---

## Tool 4: `option_walls.py` — open interest clusters

### Triggers

**English**: "option walls for X", "OI clusters X", "where will X pin this week", "gamma map X", "support and resistance options X", "key strikes X"

**Chinese**: "X 期权墙", "X 主要 strike", "X 这周走哪里", "X 期权磁吸位", "X 关键 strike"

### Canonical command

```bash
uv run --with yfinance python ~/.claude/skills/review-investment-screenshot/scripts/option_walls.py TICKER [n_expiries]
```

### Parameters

| Position | Type | Default | When to override |
|---|---|---|---|
| 1 | ticker | required | Single ticker, uppercase |
| 2 | int | typically 4 | More for "look out months" / "next 6 expirations" |

---

## Tool 5: `max_pain.py` — max pain calculation

### Triggers

**English**: "max pain X", "X max pain", "pin level X", "where will X close OPEX"

**Chinese**: "X 的 max pain", "X OPEX 目标", "X 收盘锚点"

### Canonical command

```bash
uv run --with yfinance python ~/.claude/skills/review-investment-screenshot/scripts/max_pain.py TICKER [n_expiries]
```

---

## Skill: `macro-warning` — daily 8-layer pullback radar

### Triggers (natural language)

**English**: "macro warning", "macro check", "regime check", "is the market at peak", "should I take profits", "is it time to buy", "pullback risk", "market top", "daily macro radar"

**Chinese**: "宏观警报", "宏观检查", "regime 怎么样", "市场是不是顶了", "该不该减仓", "现在能不能加仓", "市场风险大不大", "顶部信号"

### Canonical invocation

This is a **skill**, not a CLI script. Invoke via:
- Slash command: `/macro-warning`
- Or instruct agent: "Run the macro-warning skill"
- Or via `/schedule` for batch

### What it does

8-layer composite scoring (0-16) with output regime tag:
1. Valuation (NDX P/E >38, SPX P/E, Shiller CAPE, Buffett Indicator)
2. Volatility (VIX, MOVE, VVIX, VIX/VVIX ratio)
3. Sentiment (CNN F&G, AAII, NAAIM, P/C ratio)
4. Credit (HY OAS, IG OAS, yield curve, 30Y)
5. Currency (DXY, USD/JPY, BOJ pricing)
6. Breadth (% above 200DMA, A/D, new highs/lows, McClellan)
7. CTA / vol-target positioning
8. Sector rotation tilt (XLU/XLK, defensive vs cyclical)

Override rules: NDX P/E >38 OR VIX <14 OR F&G >85 = automatic YELLOW minimum.

### Output

Single regime tag (🟢 GREEN / 🟡 YELLOW / 🟠 ORANGE / 🔴 RED) + 8-layer breakdown table + delta-vs-yesterday + specific position-sizing actions + sector tilt + catalyst watch.

### Recommended scheduling

Pre-market alert (8am ET, weekdays):
```bash
# Via /schedule skill
cron: "0 12 * * 1-5"   # 8am ET = 12 UTC
prompt: "Run macro-warning skill. If regime flipped or NDX PE crossed 38, emphasize the change."
```

Post-close summary (5pm ET, weekdays):
```bash
cron: "0 21 * * 1-5"
```

### Common patterns

| User says | → Action |
|---|---|
| "Run macro warning" | Execute full 8-layer scan, output report |
| "Is the market at top?" | Same as above, lead with valuation + sentiment layers |
| "Should I add now?" | Same, but lead with action items (add/hold/trim) |
| "宏观警报" | Same, output in Chinese |
| "Set up daily macro alert" | Use /schedule to create the cron above |

### Memory integration

After each run, the skill writes to `~/.claude/projects/-Volumes-workplace-invest/memory/macro_history.jsonl` with date + regime + key indicators. This lets future runs compute deltas ("VIX rising 3 days in a row", "NDX PE crossed 38 today").

---

## Multi-tool composite patterns

For complex user requests, chain tools. Examples:

### "Should I buy X?" (full single-stock analysis)

Run in parallel:
```bash
insider_ratio.py "X" --window 90 &
quote_pull.py "X" &
option_walls.py X 4 &
wait
```
Then invoke the `analyze-stock` skill for synthesis.

### "Find me cluster buys + verify each one"

```bash
# Step 1: discover
cluster_buy_scan.py --days 30 --min-value 500000 --min-insiders 3 --enrich
# Step 2: for each ticker found, verify
insider_ratio.py "TICKER1,TICKER2,..." --window 90 --source both
```

### "AI sector cluster scan"

```bash
# Step 1: market-wide
cluster_buy_scan.py --days 30 --min-value 250000 --min-insiders 2 --enrich
# Step 2: agent post-filters results by industry contains:
# "Semiconductors" / "Computer" / "Software" / "Internet" / "Electronic"
# Step 3: deep-verify the AI subset
insider_ratio.py "FILTERED_TICKERS" --window 90
```

### "Pre-earnings prep on X"

Invoke the `earnings-prep` skill, which internally calls:
```bash
insider_ratio.py "X" --window 60 &     # 60d to catch pre-earnings activity
option_walls.py X 4 &                  # near-term pin levels
quote_pull.py "X" &                    # current price + MAs
wait
# Then WebSearch for consensus + implied move
```

---

## Tool 6: `price-alert/` suite — alert management

Adds/lists/cancels parameterized price alerts. Backed by GitHub Actions cron scanner + Telegram push. Two interaction modes — pick by context:

### Mode A: User talks to Claude Code directly (CLI scripts on local)

```bash
# Add
uv run --with yfinance python ~/.claude/skills/price-alert/scripts/add_alert.py TICKER OP VALUE [--note "..."]
#  OP = below | above | drop | rise | drop_intraday | rise_intraday | below_ma_50 | above_ma_50 | below_ma_200 | above_ma_200

# List
python ~/.claude/skills/price-alert/scripts/list_alerts.py [--active | --all | --fired]

# Cancel
python ~/.claude/skills/price-alert/scripts/cancel_alert.py TARGET [--rearm]
# TARGET = ticker, alert id, or "ALL"
```

After any add/cancel, **commit + push `alerts.json`** so GitHub Actions sees the change.

### Mode B: User texts the Telegram bot (no local CLI)

The user just sends NL to their `@<name>_bot`. The chat path (polling `chat_handler.py` or webhook `worker.ts`) parses with Claude Sonnet 4.6 + tool use and modifies `alerts.json` directly via GitHub Contents API. **No CLI invocation from the agent's side** — the user's message is the API.

If the user is asking the *Claude Code agent* (not the bot) to set an alert "for me", use Mode A. If they're asking how to set alerts from their phone, point them to Mode B examples in [`price-alert/EXAMPLES.md`](./price-alert/EXAMPLES.md).

### Triggers (natural language)

**English**: "alert me when X hits Y", "notify me if X drops Z%", "set a price alert", "watch X at Y", "alert if X breaks 50DMA", "list my alerts", "cancel X alert", "show fired alerts"

**Chinese**: "X 跌到 Y 通知我", "X 涨到 Y 提醒", "设个 alert", "盯一下 X", "X 跌破 50DMA 提醒我", "列出我的 alert", "取消 X", "我的 alerts"

### Common pattern mappings

| Utterance | Tool call (Mode A) |
|---|---|
| "alert me when GLW hits $140" | `add_alert.py GLW below 140` |
| "notify me if NVDA drops 10%" | `add_alert.py NVDA drop 10` |
| "alert if AMD drops 5% in one day" | `add_alert.py AMD drop_intraday 5` |
| "VST 跌破 50DMA 提醒我" | `add_alert.py VST below_ma_50 0` |
| "watch SPY at $500, with note 'macro flip warning'" | `add_alert.py SPY below 500 --note "macro flip warning"` |
| "list my alerts" / "我的 alerts" | `list_alerts.py --active` |
| "cancel GLW" / "取消 GLW" | `cancel_alert.py GLW` |
| "re-arm the GLW alert that fired yesterday" | `cancel_alert.py <id> --rearm` |

### Compound conditions

Schema doesn't support AND/OR within one alert. Decompose **OR** into multiple alerts ("X below 140 OR X drops 5% intraday" → 2 `add_alert.py` calls). **AND** is not supported — user gets two alerts and decides themselves.

### Hard rules

1. **Alerts are triggers to research, not buy signals.** When an alert fires and the user asks "should I add?", run `analyze-stock` + `macro-warning` + insider 30d before answering. See [`price-alert/SKILL.md`](./price-alert/SKILL.md) "Alert fired — what to do BEFORE adding" for the full checklist.
2. **Always include `--note` when context is meaningful.** It shows in the Telegram message and helps the user remember why they set it weeks later. ("AI glass tier 1 entry", "macro flip warning", etc.)
3. **Don't auto-add alerts during `analyze-stock`** unless the user explicitly asks. Suggest them, but let user confirm.

---

## Skill Catalog — NL-only skills (not CLI tools)

The 5 Tools above (and Tool 6) are direct script invocations. The skills below are **pure NL skills** triggered by Claude Code's matching against `description:` fields in each SKILL.md. There's no separate CLI command — Claude Code loads the SKILL.md and follows its instructions.

When a user utterance matches one of these, the agent should: (1) confirm the skill name, (2) gather any obvious parameters from the utterance, (3) let Claude Code load and execute the skill — don't try to manually run the workflow steps.

### Quick triggers

| Skill | EN triggers | CN triggers | When the agent invokes it |
|---|---|---|---|
| `analyze-stock` | "analyze X", "is X a buy", "deep dive on X", "research X" | "分析一下 X", "X 怎么样", "X 能买吗", "深度看 X", "调研 X" | Single-stock decision; user wants the 10-step framework |
| `macro-risk-check` | "macro check", "regime read", "risk on/off", "is the market safe" | "看一下宏观", "市场风险", "现在能加仓吗" | News-driven daily macro (less batch-friendly than macro-warning) |
| `find-untapped-thesis` | "find me the next X", "what's undervalued in Y theme", "find untapped Z plays" | "找未爆发的 X 股", "Y 板块还有什么便宜的", "找下一个 NOK" | Theme-based screening for laggards |
| `narrative-reversal-screen` | "find reversal plays", "stocks at bottom that can recover", "beaten-down with thesis" | "找暴跌反转股", "ORCL 那种反转", "底部反弹候选" | Capitulation-then-recovery setups (ORCL pattern) |
| `sector-rotation-analysis` | "sector rotation", "what sector to add", "am I too tech heavy" | "板块轮动", "该买哪个板块", "我是不是 tech 太重" | 11-sector heatmap + rotation pairs |
| `earnings-prep` | "X reports tomorrow", "should I hold X through earnings", "earnings prep for X", "what's priced in for X" | "X 财报前怎么看", "X 财报应该减仓吗", "X implied move", "X 财报前分析" | Pre-earnings decision: implied move + scenarios + position action |
| `leaps-screen` | "LEAPS for X", "what call should I buy on X", "stock or LEAPS for X", "long-term options X" | "X 买什么 LEAPS", "X 的长期 call", "X 现货还是期权", "X 2027 call 推荐" | Long-dated options strike selection with payoff math |
| `option-wall-analysis` | "max pain on X", "option walls X", "where will X pin", "gamma map X" | "X 的 max pain", "X 期权墙", "X 期权磁吸位", "X 这周走哪里" | Short-term (≤4 weeks) levels for stocks with active options |
| `portfolio-audit` | "review my portfolio", "audit my book", "am I too concentrated", "what should I trim" | "审一下我的组合", "我组合风险大吗", "该减什么仓" | Full risk review from positions list or screenshot |
| `tax-optimize` | "should I sell X for tax", "tax on selling X", "LTCG vs STCG on X" | "X 减仓税务", "现在卖还是等长期", "X 减仓最省税" | LTCG vs STCG decision with state-aware math |
| `price-alert` | (covered as Tool 6 above) | (covered as Tool 6 above) | Set parameterized price/MA alerts via cron + Telegram |
| `review-investment-screenshot` | (paste portfolio screenshot + "review") | (发组合截图 + "看一下") | Quick portfolio review from a screenshot |
| `find-alpha` | "find alpha", "weekly alpha scan", "find me 3 swing trades", "what's the next MRVL" | "找 alpha", "本周 alpha 扫一下", "找下一个 MRVL" | 3-horizon (swing/position/LEAPS) discovery, weekly cadence |

### Pre-flight discipline (all skills above enforce this)

Every skill that recommends a buy/add/trim runs the same Pre-flight checklist (codified in each SKILL.md):

1. **Macro regime** (trigger `macro-warning`)
2. **Insider strict** (`insider_ratio.py --window 90`)
3. **Valuation** (Forward P/E vs sector median)
4. **3-tier entry** (T1 / T2 / T3, never "buy at market")
5. **Sizing** (≤ 10% single, ≤ 50% high-beta total)
6. **Tax** (run `tax-optimize` if trim < 12mo)

If a skill's output skips any layer, the agent should flag it and request a redo. The user's methodology is "macro → stock → entry → sizing → tax" — every recommendation must touch all 5.

### "Look carefully" rule (applies across all skills)

The single most common failure mode is the agent giving a fast generic answer because the user asked casually. The user's preference is **brutal honesty with explicit numbers** (% allocation, $ P&L impact, post-tax delta). When in doubt, slow down and run the checklist — the user prefers a slower correct answer over a fast surface-level one. This is codified in user memory and in each SKILL.md.

---

## Bilingual entity extraction patterns

| Entity in user utterance | How to extract |
|---|---|
| Ticker symbol | Uppercase tokens 1-5 letters (sometimes prefixed with $). Examples: NVDA, $NVDA, BRK.B |
| Days/window | "last week"=7, "last month"=30, "last quarter"=90, "this year"=365, "上周"=7, "上个月"=30, "最近三个月"=90 |
| Dollar threshold | "big"="conviction"="significant" → 100000+; "small"="any" → 25000; "only large"="serious" → 1000000 |
| Senior filter | "CEO"/"CFO"/"founder"/"chairman" mentioned → set --senior-only; "高管"/"创始人"/"董事长" → --senior-only |

---

## Setup precondition

All scripts assume `/tmp/.insider_venv` exists with yfinance + pandas + numpy. If a fresh install:

```bash
bash ~/.claude/skills/setup.sh
```

If a script returns `ModuleNotFoundError`, re-run setup. If openinsider fetch fails (network), `insider_ratio.py` falls back to yfinance automatically with a `"fallback": "used yfinance (openinsider unreachable)"` field in output.

---

## Adding new tools

When adding a new script, append to this file with the same template:
1. Triggers (EN + CN)
2. Canonical command
3. Parameters table
4. Output schema
5. Common pattern mappings

Keep verb-leading triggers ("find / check / scan / hunt / show") rather than noun-leading — easier to recognize from utterances.
