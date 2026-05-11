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

## Part 1.6 — Save credentials to your local `.env` file

Before pushing anything to GitHub, save your credentials **locally** in a `.env` file that is **never committed**.

```bash
cd ~/.claude/skills/price-alert
cp .env.example .env
# Open .env in your editor (nano, vim, VSCode, etc.) and paste:
#   TELEGRAM_BOT_TOKEN=<your real token>
#   TELEGRAM_CHAT_ID=<your real chat_id>
```

The repo's `.gitignore` already excludes `.env` — `git status` will NOT show it. **Verify before any commit**:

```bash
git -C ~/.claude/skills status --short | grep -i "\.env"
# Expected output: nothing (or only .env.example which is safe to commit)
```

If you accidentally see `.env` listed as a tracked or staged file, **STOP** and remove it from staging.

### Why .env exists if GitHub Actions doesn't read it

| Use case | Where credentials come from |
|---|---|
| **Local testing** (`python check_alerts.py` on your laptop) | reads `.env` automatically |
| **GitHub Actions cron** (the actual production path) | reads from repo Secrets (set in Part 2) |

`.env` is purely for **your machine** — testing scripts before pushing alerts to the live cron.

### ⚠️ If you ever leaked a token

If your token appears anywhere outside `.env` (screenshot, chat, repo, paste bin, anywhere), it is compromised:

1. Open @BotFather → `/mybots` → select your bot → **API Token** → **Revoke current token**
2. BotFather gives a new token
3. Update `.env` AND GitHub Secrets with the new value
4. Old token instantly stops working — no further action needed

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

## Troubleshooting — issues we hit during real setup

These are the actual problems encountered during the first full-flow setup. Follow this debug sequence if anything breaks.

### 🐛 #1 `getUpdates` returns `{"ok": true, "result": []}` — most common

**Cause**: Your bot hasn't received any messages yet. Telegram's `getUpdates` only returns recent messages sent TO the bot, so until the bot receives at least one message, the result array is empty.

**Symptoms**:
```json
{"ok": true, "result": []}
```

**Fix** (30 seconds):
1. Open Telegram → search for **your bot's username** (e.g. `@DuckyduckyTradeBot`)
2. Tap the bot, then tap the blue **START** button (or send `/start`)
3. Send any text message (e.g. `hello`)
4. **Refresh** the `getUpdates` URL — now `result` should have entries

**Why this trips people up**: The Telegram docs assume you've already been chatting with the bot. The very first setup has nothing to fetch.

---

### 🐛 #2 `chat.id` vs `from.id` confusion

The JSON response has TWO `id` fields:

```json
"message": {
  "from": {"id": 1435438296, ...},   ← user's user_id (sender)
  "chat": {"id": 1435438296, ...}    ← chat_id ← USE THIS ONE
}
```

For **private chats** they happen to be equal. For **group/channel chats** they differ — `from.id` is the sender's user_id, `chat.id` is the chat the bot lives in.

**Rule**: Always use `chat.id`. It's the canonical answer regardless of chat type.

**Group chats**: `chat.id` will be NEGATIVE (e.g. `-1001234567890`). That negative sign is part of the value — keep it.

---

### 🐛 #3 Leaked your token by mistake?

Tokens can leak via screenshots, chat messages, terminal scrollback, git commits, paste bins. If yours appears anywhere outside `.env` + GitHub Secrets:

1. Telegram → @BotFather → `/mybots` → select your bot → **API Token** → **Revoke current token**
2. BotFather instantly issues a new token; the old one becomes invalid
3. Update both your local `.env` AND GitHub repo Secrets with the new value

**Prevention rules**:
- Never paste a token into a chat (including AI chats — the conversation may be exported)
- Never screenshot the token area of BotFather; if you do, immediately revoke after
- `git status` before every commit; verify `.env` is NOT listed
- `git -C ~/.claude/skills check-ignore -v price-alert/.env` should return a `.gitignore` line — that confirms gitignore is working

---

### 🐛 #4 `.env` vs `.env.example` — what to commit?

| File | Status | What's in it |
|---|---|---|
| `.env.example` | ✅ **committed** to git | template with `PASTE_YOUR_TOKEN_HERE` placeholders |
| `.env` | ❌ **gitignored**, never committed | YOUR real token + chat_id |

Workflow:
```bash
cp .env.example .env       # one-time setup: copy template
# edit .env with your real values
# .env is now ignored — git status won't show it
```

Verify it's ignored:
```bash
git -C ~/.claude/skills check-ignore -v price-alert/.env
# Expected: ".gitignore:35:.env\tprice-alert/.env"
```

If `check-ignore` returns nothing or shows the file in `git status` as untracked, **something is wrong** — fix gitignore before any commit.

---

### 🐛 #5 Workflow fails with "TELEGRAM_BOT_TOKEN not set"

The script ran but Telegram credentials weren't found. Two paths:

- **Local run**: `.env` file missing or in wrong location. Should be at `price-alert/.env` (same level as `SKILL.md`).
- **GitHub Actions run**: Repo Secrets weren't added or named wrong. Names must be EXACTLY `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (case-sensitive, no leading/trailing spaces).

Quick verify locally:
```bash
cd ~/.claude/skills/price-alert
python -c "
import os, sys
sys.path.insert(0, 'scripts')
from check_alerts import _load_dotenv
from pathlib import Path
_load_dotenv(Path('.env'))
print('TOKEN set:', bool(os.environ.get('TELEGRAM_BOT_TOKEN')))
print('CHAT set: ', bool(os.environ.get('TELEGRAM_CHAT_ID')))
"
```

---

### 🐛 #6 Telegram says "chat not found"

Two possible causes:

1. **Wrong chat_id** — re-do the `getUpdates` flow above; copy the `chat.id` value exactly (preserve the negative sign for group chats).
2. **You never tapped Start on the bot** — even with the right chat_id, the bot can't initiate conversation. The user must start the chat first.

Smoke test with browser URL:
```
https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=test
```
Returns `{"ok":true,...}` → working. Returns `{"ok":false,"description":"chat not found"}` → fix above.

---

### 🐛 #7 Other workflow misfires

| Symptom | Fix |
|---|---|
| Workflow runs but no Telegram message | Smoke-test the URL above first; isolates whether problem is bot creds or check_alerts.py |
| Cron doesn't fire on schedule | GitHub schedules can be delayed up to ~15 min during peak hours; check Actions log timestamps |
| Alert fires but stays fired forever | By design — `python cancel_alert.py <id> --rearm` to re-arm an alert after it triggered |
| `add_alert.py` succeeded but Actions doesn't pick it up | You forgot to commit + push `alerts.json` after running add_alert.py |

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
