# CTA Trigger Level Firehose

Daily radar for systematic-flow trigger levels — a public-data replication of
the sell-side CTA models (GS Futures Strats / Nomura McElligott style) that
drive headlines like *"SPX 7230 = first CTA sell trigger"*.

## What it tracks

| Signal | Mechanism | Trade meaning |
|--------|-----------|---------------|
| Momentum flip lines (1M/3M/6M/12M) | Price vs N-trading-days-ago close | Cross below = that horizon's trend signal flips negative = mechanical selling tranche |
| 50DMA (±1%) | Bank models' first-trigger zone clusters here | The "7230" type number |
| 20/100/200 DMA | Secondary tranches / long-term line | 200DMA break = trend funds flip short |
| 1M/3M realized vol | Vol-control & risk-parity sizing | RV > 20% = mechanical de-risking regardless of direction |

Indices: **SPX (^GSPC), NDX (^NDX), RTY (^RUT)**. Edit `INDICES` in
`scripts/cta_levels.py` to add more (e.g. `ES=F`, `^SOX`).

## Why it works

CTA AUM (~$300-400B) runs near-identical multi-horizon momentum models, so
trigger levels cluster industry-wide. A simple replication lands within
~0.5% of the bank numbers (validated 2026-06-11: our 50DMA 7195 vs GS first
trigger ~7230). Vol-targeting then amplifies: selling → RV up → forced
de-leverage → more selling.

## Cron

Daily post-close, weekdays (GitHub Actions, `.github/workflows/cta-firehose.yml`):
- `21:15 UTC` (17:15 ET) — settle prices in, levels for tomorrow

State (`scripts/state.json`) remembers which side of each trigger every index
closed on; a cross since the last run prepends a 🔔 **CTA TRIGGER BREACHED**
banner so the Telegram alert is impossible to miss.

## Manual run

```bash
# Print only
uv run --with yfinance --with numpy python scripts/cta_levels.py

# Dry-run the Telegram send
TEST_MODE=1 uv run --with yfinance --with numpy python scripts/cta_levels.py --telegram
```

## Reading the alert

```
🚨 1M动量线 7399 (-0.2%)      ← short-horizon CTA already selling
✅ 50DMA 7195 (+2.7%) ⭐首轮触发区 ← THE level; below = first big tranche
✅ 3M动量线 6781 (+8.9%)       ← second tranche
✅ 200DMA 6868 (+7.5%)        ← trend funds flip short below
RV: 1M 12.6% / 3M 14.9% 🆗    ← >20% = vol-control selling on top
```

Cross-check against the leaked bank numbers (@Michael_QQQ2025, The Market
Ear, ZeroHedge reposts of McElligott) — our lines are the skeleton, theirs
add positioning size ($bn per tranche).

## Caveats

- yfinance index data can lag a day after holidays; the digest prints the
  close date it used.
- This is the *price* leg only. Bank models add positioning percentile
  (how much is left to sell) — pair with the Goldman/Nomura leaks for size.
- Levels move slowly (a few points/day) but ARE path-dependent; the daily
  run keeps them honest.
