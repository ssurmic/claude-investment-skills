# Price Alert — Setup Guide

> Get push notifications on your phone when any stock hits a price you care about.

[中文版 / Chinese version](./SETUP-zh.md)

---

## What you'll have when this is done

A fully automated system where you tell Claude:

```
"Alert me when GLW hits $140"
```

…and 15 minutes after the price actually hits $140, your phone buzzes with a Telegram notification:

```
🔻 PRICE ALERT: GLW

Current: $139.85
Trigger: $139.85 ≤ $140.00
52W high: $198.25 (-29.5% off)
Note: AI glass tier 1 entry
```

The whole thing runs on **GitHub Actions** (free, 24/7, no laptop required) and pushes to **Telegram** (instant on phone).

---

## What you need first

| Requirement | How to get it |
|---|---|
| **Telegram account** | Free app on iOS/Android, or telegram.org on desktop |
| **GitHub account** | github.com — free |
| **Forked / cloned this repo** | `git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills` |
| **Claude Code installed** | https://docs.claude.com/claude-code/install |

If any of these are missing, set them up first — the rest takes ~7 minutes.

---

## Part 1 — Create your Telegram bot (5 min)

### 1.1 Open Telegram and find @BotFather

In Telegram, tap the search icon and type `@BotFather`. The official one has a blue checkmark. Tap on it, then tap **Start**.

### 1.2 Run `/newbot`

Send the message `/newbot`. BotFather will reply asking for two things:

```
BotFather: Alright, a new bot. How are we going to call it?
You:       Zizhao Price Alerts        ← display name (anything; emoji OK)

BotFather: Good. Now let's choose a username for your bot.
           It must end in 'bot'.
You:       zizhao_pricealert_bot      ← unique username; must end in _bot
```

### 1.3 Save the bot token

BotFather replies with something like:

```
Done! Congratulations on your new bot. You will find it at t.me/zizhao_pricealert_bot.

Use this token to access the HTTP API:
7234567890:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxx
   ↑ this whole string is your BOT_TOKEN — save it
```

**⚠️ Treat the token like a password.** Anyone with it can send messages from your bot. Don't paste it in chats or commit it to code.

### 1.4 Get your chat_id

Telegram needs to know **which chat** to send messages to (it could be you, a group, a channel). Easiest way:

1. In Telegram, search for your bot (`zizhao_pricealert_bot`).
2. Tap **Start**, then send any message (e.g. `hello`).
3. Open in your browser (replace `<YOUR_TOKEN>` with the token from step 1.3):
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
4. You'll see a JSON response. Find the `"chat":{"id":...}` field:
   ```json
   {
     "ok": true,
     "result": [{
       "update_id": 123456789,
       "message": {
         "from": {"id": 987654321, ...},
         "chat": {
           "id": 987654321,        ← THIS NUMBER is your CHAT_ID
           "first_name": "Your name"
         },
         "text": "hello"
       }
     }]
   }
   ```

Save this number. **It can be negative** for groups (e.g. `-1001234567890`).

### 1.5 Smoke test (optional but recommended)

Before moving on, verify both values work by pasting this URL in your browser (replace both placeholders):

```
https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=Hello%20from%20setup
```

If everything's right, your phone gets a "Hello from setup" message. If you get an error, double-check both values.

---

## Part 2 — Add credentials to GitHub Secrets (2 min)

GitHub Actions needs to know your token + chat_id. **Never put them in code** — use repo secrets.

### 2.1 Open your repo's Secrets page

Replace `YOUR_USERNAME` with your GitHub username:

```
https://github.com/YOUR_USERNAME/claude-investment-skills/settings/secrets/actions
```

(Or: GitHub repo → Settings → Secrets and variables → Actions)

### 2.2 Add two secrets

Click **New repository secret** twice and add:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather (e.g. `7234567890:AAH-xxx...`) |
| `TELEGRAM_CHAT_ID` | the chat id from `/getUpdates` (e.g. `987654321`) |

After saving, secrets appear as `***` — even you can't read them back (only update or delete). The GitHub Actions runner injects them at runtime.

---

## Part 3 — Test the workflow manually (1 min)

Don't wait for cron to verify it works.

### 3.1 Run workflow on demand

Go to:
```
https://github.com/YOUR_USERNAME/claude-investment-skills/actions/workflows/price-alerts.yml
```

Click **Run workflow** → **Run workflow** (green button).

The job will start within ~10 seconds. Click into it to watch logs.

If `alerts.json` is empty, you'll see:
```
Checking 0 active alerts at 2026-05-10T...
Summary: 0 fired, 0 skipped, 0 not triggered
```

That's a green check ✅ — your wiring is correct, you just have nothing to monitor yet.

### 3.2 Smoke-test alert (force a fire)

To verify the Telegram path end-to-end, set a guaranteed-trigger alert:

```bash
cd ~/.claude/skills
/tmp/.insider_venv/bin/python price-alert/scripts/add_alert.py SPY below 99999 \
    --note "Smoke test — should fire immediately"

git add price-alert/alerts.json
git commit -m "test: smoke-test alert (delete after)"
git push
```

Then click **Run workflow** again. Within ~30s you should get a Telegram message like:

```
🔻 PRICE ALERT: SPY
Current: $737.62
Trigger: $737.62 ≤ $99999.00
...
```

After you confirm Telegram works, clean up:

```bash
/tmp/.insider_venv/bin/python price-alert/scripts/cancel_alert.py --all
git add price-alert/alerts.json
git commit -m "test: clean up smoke-test alert"
git push
```

---

## Part 4 — Add real alerts

Now use the skill. Just talk to Claude:

```
You: Set alert for GLW at $140 — note "AI glass tier 1"
You: 通知我 NVDA 跌 10%
You: Watch SMH at $480, drop 5% from now
```

Claude calls the right script, commits the change, pushes. The cron picks it up next cycle.

To audit:
```
You: list my active alerts
```

To cancel:
```
You: cancel my GLW alert
You: cancel all alerts
```

---

## How the cron works

The workflow file at `.github/workflows/price-alerts.yml`:

```yaml
on:
  schedule:
    - cron: '*/15 13-21 * * 1-5'   # every 15 min, 13-21 UTC, weekdays
  workflow_dispatch:               # manual trigger button
```

Translation:
- **Every 15 minutes** during US trading hours (9am–5pm ET, weekdays)
- **Manual trigger** available any time via the Actions tab

Why these hours? Pre-market starts ~4am ET but volume is thin and prices wobble. After-hours can move on news, but most alerts are about regular-session levels. The 9am–5pm ET window catches what matters with minimal noise.

To change the schedule, edit the cron line:
- `*/5 13-21 * * 1-5`  → every 5 min (more notifications, more compute)
- `0 14,18,21 * * 1-5` → 3x/day (open, midday, close)
- `*/30 * * * *`       → every 30 min, 24/7 (good for crypto if you adapt)

---

## Cost

Free.

| Resource | Limit | Our usage |
|---|---|---|
| GitHub Actions (free public repo) | 2,000 min/month | ~50 min/month at every-15-min cron |
| Telegram API | unlimited messages | a few per week |
| yfinance | rate-limited but not metered | well under any limit |

If you make the repo private, GitHub Actions has a 2,000 min/month free limit. Public repos are unlimited.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Workflow fails with "TELEGRAM_BOT_TOKEN not set" | Secrets weren't added; redo Part 2 |
| Workflow runs but no Telegram message | Test with the smoke-test URL from 1.5 — confirms token+chat_id are correct |
| `getUpdates` returns empty array `"result": []` | Send a message to your bot first, then refetch |
| Telegram says "chat not found" | Wrong chat_id, OR you never tapped Start on the bot |
| Cron doesn't fire on schedule | GitHub schedules can be delayed up to 15 min on busy hours; verify by checking Actions log timestamp |
| Alert fires but stays fired forever | By design — `cancel_alert.py <id> --rearm` to re-arm |

---

## Architecture summary

```
You ──"alert me at $140"──→ Claude
                              │
                              ▼
                   add_alert.py → alerts.json
                              │
                              ▼
                       git commit + push
                              │
                              ▼
              ┌─────GitHub Actions cron─────┐
              │  every 15 min during US hrs │
              │                             │
              │  python check_alerts.py     │
              │   1. read alerts.json       │
              │   2. fetch yfinance prices  │
              │   3. evaluate conditions    │
              │   4. POST Telegram bot API  │
              │   5. mark fired=true        │
              │   6. commit alerts.json     │
              └──────────────┬──────────────┘
                             │
                             ▼
                  📱 Telegram push notification
```

No server. No paid service. No laptop required.

---

## Sharing with friends

If a friend wants this:
1. They fork or clone your repo.
2. They follow Parts 1-3 above on their own GitHub + Telegram.
3. Their alerts are private — separate `alerts.json` per fork.

The bot token + chat_id stay in their GitHub Secrets, never in code.
