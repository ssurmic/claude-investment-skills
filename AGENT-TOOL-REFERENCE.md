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

| Intent (canonical EN) | Bilingual triggers | Tool |
|---|---|---|
| Check insider activity for stock(s) | EN: "insider check / insider trading on X / who's buying X" · CN: "X 内部交易 / X 高管买卖 / X insider 怎么样" | `insider_ratio.py` |
| Hunt market-wide cluster buys | EN: "find cluster buys / who are insiders buying / where's smart money" · CN: "找 cluster buy / 内部人在买什么 / 最近高管买入" | `cluster_buy_scan.py` |
| Live quotes + moving averages | EN: "quote X / price of X / where is X trading" · CN: "X 现在多少 / X 报价 / X 价格" | `quote_pull.py` |
| Option walls / OI clusters | EN: "option walls X / where will X pin / gamma map X" · CN: "X 期权墙 / X 期权磁吸位" | `option_walls.py` |
| Max pain calculation | EN: "max pain X / pin level X" · CN: "X 的 max pain / X OPEX 目标" | `max_pain.py` |

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
