---
name: nvidia-developer-firehose
description: |
  Real-time NVIDIA Developer technical-blog firehose. Polls
  developer.nvidia.com/blog/feed (Atom) every 30 min. For each new post,
  uses HEURISTIC EXTRACTION + yfinance.Search to auto-resolve every
  mentioned company → US ticker (no hand-maintained name→ticker dict),
  with a persistent ticker cache that learns over time. Surfaces names
  via Telegram, separated into 🎯 portfolio-tracked tickers vs 🔍 newly
  discovered tickers. Why it matters: NVIDIA explicitly names 800V HVDC,
  CPO, optical, power, and custom-silicon partners in these posts — the
  forward-looking design ecosystem that re-rates weeks later when sell-
  side/Substack picks it up.
  Triggers in English ("nvidia developer firehose", "scrape nvidia
  developer blog", "nvidia partner monitor") or Chinese ("NVIDIA Developer
  爬虫", "NVIDIA 博文实时", "英伟达开发者博客 firehose").
  Do NOT trigger for: AMD/Intel developer blogs, generic web scrapers,
  or any non-equity context.
---

# NVIDIA Developer Firehose

## Why this exists

NVIDIA's Technical Blog (`developer.nvidia.com/blog`) is where NVDA
publicly names the partners it's designing the next generation around —
800V HVDC chip suppliers, CPO optical module makers, custom XPU/ASIC
partners, networking/server OEMs, hyperscaler/neocloud customers. When
a partner gets named here, it's typically **weeks before** the Substack /
sell-side picks up on it. Forward-looking edge.

This firehose:
1. Polls the Atom feed every 30 min.
2. For each new post, runs **smart heuristic extraction** + **yfinance.Search**
   to auto-resolve every capitalized noun phrase → US-listed ticker.
3. **Persistent cache** (`nvdev_ticker_cache.json`) learns over time so
   newly-named partners get added automatically; never needs hand edits.
4. Sends a Telegram alert separating 🎯 **portfolio-tracked** mentions
   (high signal) from 🔍 **newly discovered** tickers (medium signal).

## Architecture

```
ATOM FEED                  CANDIDATE EXTRACT             RESOLVE
─────────                  ─────────────────             ───────
developer.nvidia.com  →    capitalized 1-4 word     →    cache HIT  →  done
/blog/feed/                phrases, minus              cache MISS →  yf.Search()
                           STOPWORDS + ALIAS                          name-overlap
                           expansion                                  US exchange?
                                                                      → cache + emit
```

**No hardcoded `name_to_ticker` dict.** A small `TRACKED_TICKERS` set
(your portfolio universe) only affects whether a hit shows up as 🎯 or 🔍.
Resolution itself is fully automatic.

**ALIAS map** handles only ambiguous short forms (e.g. `MPS` →
`Monolithic Power Systems`) so the yfinance search returns the right
company.

**STOPWORDS** filter strips NVIDIA's own products, calendar/structural
words, and common tech jargon (CUDA, TensorRT, Blackwell, GTC, etc.).

**Negative cache**: words that resolve to nothing (or non-US) are also
cached, so we never re-look up junk.

## Files

- `scripts/nvdev_firehose.py` — the engine
- (in the runtime repo)
  - `scripts/nvdev_state.json` — seen-post ids (5k cap, dedup)
  - `scripts/nvdev_ticker_cache.json` — name → {ticker,exchange,name,source}

## Workflow

The runtime repo provides a GitHub Actions workflow that runs the engine
on a `*/30 * * * *` cron with `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` as
secrets. First run silently seeds the state (no Telegram avalanche).

## Tuning

| Env var | Default | What it does |
|---|---|---|
| `MAX_ALERTS` | 8 | Cap Telegram alerts per run |
| `MAX_LOOKUPS` | 40 | Cap yfinance.Search calls per article (cache absorbs rest next run) |
| `TEST_MODE` | (unset) | If `1`, log to stderr; no Telegram, no state/cache write |
| `NVDEV_USER_AGENT` | (generic) | Override the polite UA string |

## Editing the cache

The cache JSON is human-editable. To override a wrong resolution or add
an alias by hand:

```json
{
  "some company": {"ticker": "ABCD", "exchange": "NMS", "name": "Some Company Inc.", "source": "manual"},
  "wrong match name": null
}
```

`null` = negative-cached, will be skipped on future runs.

## What an alert looks like

```
🟢🟪 NVIDIA Developer — new post
NVIDIA Transitions to 800V HVDC for 1MW AI Racks
作者: Mathias Blake et al
发布: 2025-05-20

🎯 组合内标的(高信号):
  • Infineon → IFNNY
  • MPS → MPWR
  • Navitas → NVTS
  • STMicroelectronics → STM
  • Texas Instruments → TXN
  • Eaton → ETN
  • Schneider Electric → SBGSF
  • Vertiv → VRT
  • TSMC → TSM
  • Coherent → COHR
  • Lumentum → LITE
  • Marvell → MRVL

🔍 其他识别到的可交易标的:
  • ROHM → ROHCY  (ROHM Co., Ltd.)
  • Flex Power → FLXP  (Flex-Power Inc.)

https://developer.nvidia.com/blog/...
```

## Related skills

- `strategic-partner-firehose` — SEC 8-K / 13D partner detection (downstream)
- `pr-wire-firehose` — vendor newsroom RSS (parallel signal source)
- `insider-firehose` — Form 4 buys (corroborating signal)
