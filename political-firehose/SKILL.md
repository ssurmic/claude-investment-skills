---
name: political-firehose
description: Daily monitor for political stock trades — Congress STOCK Act PTRs and executive OGE Form 278-T filings. Telegram alerts with trade details.
---

# Political Trade Firehose

Monitors stock trades by politicians and government officials, covering two separate disclosure systems:

| System | Who | Form | Timing | Format |
|--------|-----|------|--------|--------|
| STOCK Act PTR | Congress (Senate + House) | Periodic Transaction Report | Within 45 days | JSON/XML (scrapeable) |
| OGE Form 278-T | Executive (President, Cabinet) | Periodic Transaction Report | Within 30-45 days | PDF only |

## Politicians tracked (12)

**Executive (OGE 278-T)**:
- Trump (President) — 3,642 Q1 2026 trades
- Bessent (Treasury Secretary) — macro lens on policy
- Lutnick (Commerce Secretary)

**Senate (STOCK Act)**:
- Tuberville (R-AL) — P1, most active Senate trader
- Mark Kelly (D-AZ), Dan Sullivan (R-AK), Whitehouse (D-RI)

**House (STOCK Act)**:
- Nancy Pelosi (D-CA) — P1, legendary track record
- Austin Scott (R-GA), Dan Crenshaw (R-TX) — P1
- McCaul (R-TX), Gottheimer (D-NJ), Marjorie Taylor Greene (R-GA)

Edit `scripts/politician_registry.py` to add/remove.

## Cron

Three times daily, weekdays only:
- `13:00 UTC` ( 9 AM ET) — catches overnight + pre-market OGE filings
- `17:00 UTC` ( 1 PM ET) — mid-day
- `21:00 UTC` ( 5 PM ET) — post-close

## Manual run

```bash
# Test mode (no Telegram)
TEST_MODE=1 PRIORITY_MAX=2 python3 scripts/political_firehose.py

# Congress backtest (last 30 days, all trades)
python3 scripts/backtest_congress.py

# OGE PDF backtest (known Trump filings)
python3 scripts/backtest_oge.py
```

## OGE limitations

OGE 278-T PDFs report amount ranges (not exact prices):
- J = $1K–$15K  |  K = $15K–$50K  |  L = $50K–$100K  |  M = $100K–$250K
- N = $250K–$500K  |  O = $500K–$1M  |  P1 = $1M–$5M  |  P2 = $5M–$25M  |  P3 = $25M+

No exact trade prices. No transaction cost basis.

## State

`scripts/state.json` tracks seen Congress trade keys and OGE PDF URLs.
Pre-seeded with 4 known Trump 278-T PDFs (Oct 2025, Oct 2025, Feb 2026, May 2026) to avoid flood on first run.

## Adding a politician

1. Find their name exactly as listed on disclosures (check efdsearch.senate.gov or disclosures.house.gov)
2. Add to `POLITICIANS` list in `politician_registry.py`
3. Set `system="CONGRESS"` or `system="OGE"` and correct `chamber`
