# AGENTS.md — Setup orchestration for AI coding agents

**Who reads this**: any AI agent (Claude Code, OpenAI Codex, Cursor, custom CLI agents) that a user invokes to *set up* this repo. Triggered when the user has pasted this repo's URL or said something like "help me install / configure / set up these skills".

**Who does NOT read this**: agents that just need to *invoke* tools after install — they read [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md).

This file is the canonical agent guide. Codex looks for `AGENTS.md`, Claude Code also looks for `CLAUDE.md`, Cursor looks for `.cursor/rules/*`. Anything else should symlink or include this file.

[中文版 / Chinese version](./AGENTS-zh.md)

---

## Index — when to read what

| Document | When the agent reads it |
|---|---|
| **AGENTS.md (this file)** | Orchestrating a fresh install or upgrade — step-by-step walkthrough |
| [`README.md`](./README.md) | Explaining "what this is" / architecture context to the user |
| [`INTRODUCTION.md`](./INTRODUCTION.md) | Deeper architecture, cost breakdown, tech-stack questions |
| [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md) | After install — translating user NL into CLI commands for analysis skills |
| [`INVESTMENT-WORKFLOW.md`](./INVESTMENT-WORKFLOW.md) | Picking which analysis skill matches a user's investment question |
| [`price-alert/SETUP.md`](./price-alert/SETUP.md) | Concrete step-by-step polling setup (button-by-button screens) |
| [`price-alert/SETUP-WEBHOOK.md`](./price-alert/SETUP-WEBHOOK.md) | Webhook upgrade walkthrough, layered on top of SETUP.md |
| [`price-alert/EXAMPLES.md`](./price-alert/EXAMPLES.md) | Post-install — showing the user what NL phrasings work |

**Rule of thumb**: this file tells you *what to do*; the linked SETUP docs are the *exact button-by-button details*. Follow this file's flow, but when a step says "do Part 3 of SETUP-WEBHOOK.md", open that section and walk the user through verbatim.

**`AGENT-TOOL-REFERENCE.md` coverage**: 6 CLI tools (`insider_ratio.py`, `cluster_buy_scan.py`, `quote_pull.py`, `option_walls.py`, `max_pain.py`, `price-alert/` suite) + a Skill Catalog mapping all 13 NL-only skills (analyze-stock, earnings-prep, find-alpha, leaps-screen, etc.) to their bilingual trigger phrases. Read its Skill Catalog section after setup so you know what NL utterances map to which skill.

---

## Mental model — what runs where (read before doing anything)

Before walking the user through setup, internalize the component map. Most setup confusion comes from agents (and users) thinking GitHub Actions is the engine. **It is not.** GitHub is a small storage + cron layer. The intelligence runs on the user's laptop inside Claude Code.

```
LOCAL (user's laptop)
  ├── Claude Code              ← the AI brain (reads NL, picks skills)
  ├── ~/.claude/skills/        ← THIS REPO, cloned here
  │   ├── */SKILL.md           ← markdown instructions Claude follows
  │   ├── */scripts/*.py       ← Python helpers Claude executes
  │   └── price-alert/alerts.json  ← edited by user OR by bot
  └── (analysis skills like analyze-stock NEVER call out to GitHub —
       they fetch yfinance + openinsider directly from the laptop)

GITHUB (small role: storage + cron, NO AI here in the price-scan loop)
  ├── repo storage             ← alerts.json source of truth
  ├── price-alerts.yml         ← cron 2 min: read alerts.json → check prices →
  │                              Telegram push. PURE PYTHON, no Claude API call.
  └── telegram-chat.yml        ← (Option A only) cron 2-5 min: poll Telegram →
                                  Claude API → modify alerts.json.

TELEGRAM
  └── @bot                     ← receives push notifications, sends user chat

CLOUDFLARE WORKER (Option B chat path only — replaces telegram-chat.yml)
  └── webhook                  ← instant Telegram-POST receiver → Claude API → alerts.json
```

**Where each "moving average" gets computed**:
- "What's NVDA's 50DMA right now?" (analysis) → user's laptop (Claude calls `quote_pull.py`)
- "Alert me when NVDA crosses 50DMA" (cron-driven alert) → GitHub Actions runner (`check_alerts.py`)
- "Set this alert via bot" (chat) → wherever the chat path lives (GH cron OR CF Worker)

**When you explain this to the user, lead with**: "All real investment thinking happens on your laptop. GitHub is just a JSON file + a cron job that pushes Telegram messages. Cloudflare (if you set it up) is just a faster version of that cron. You're not delegating decisions to a server."

This framing dissolves the common worry "is this thing trading for me?" — the answer is no, it's pinging your phone with research-grade triggers.

---

## Phase 1 — PREP (do this *before* touching anything)

Classify the user's situation first. Ask each question only if you can't already infer the answer from context (file paths in their message, OS hints, prior conversation).

### PREP questionnaire

Mentally run through this. Surface only the unknowns to the user.

| Question | Why it matters | If "I don't know" |
|---|---|---|
| **OS?** | macOS / Linux / WSL all work; Windows-native is not supported | Run `uname -s` |
| **Python ≥ 3.9?** | Required for analysis skills | Run `python3 --version` |
| **Node.js installed?** | Required only for Flow D (webhook) | Run `node --version` |
| **Claude Code installed?** | Required for natural-language skill triggering | Run `claude --version` |
| **Telegram account on phone?** | Required for price alerts (any path) | They'd need to install Telegram |
| **GitHub account?** | Required to fork + run workflows | github.com/signup |
| **Cloudflare account?** | Required ONLY for Flow D | Free signup at cloudflare.com |
| **Goal: alerts-only, or chat with bot?** | Determines whether Anthropic API path is enabled | Default: alerts-only ($0/mo) |
| **OK with public GitHub repo?** | Public = unlimited free GH Actions; private = 2000 min/mo cap | Default: public |
| **What's the chat latency tolerance?** | <3 sec → Flow D needed; minutes OK → Flow C is enough | Default: Flow C |

### Decision tree

```
User said "set me up from scratch":
  ↓ wants price alerts?
  ├─ NO  → Flow A only (analysis skills only) ── stop, $0/mo
  └─ YES → Flow A + B (polling alerts)
           ↓ wants to chat with bot in NL?
           ├─ NO  → stop, $0/mo
           └─ YES → A + B + C (polling chat) ── stop, ~$1-4/mo
                    ↓ needs sub-3-sec response?
                    ├─ NO  → stop
                    └─ YES → A + B + C + D (webhook upgrade) ── still ~$1-4/mo

User said "alerts are slow" / "make chat instant":
  → Already has A+B+C, jump straight to Flow D

User said "it's broken / not working":
  → Skip flows, go to GOTCHAS matrix
```

---

## Phase 2 — DETECTION (utterance → flow matching)

Match the user's first message to a flow. Bilingual triggers below:

| Utterance (EN / CN) | Flow to start |
|---|---|
| "set me up", "install this", "how do I install" / "帮我装一下", "怎么配置", "从零开始" | **Flow A** |
| "set up alerts", "add price alerts", "telegram notifications" / "配 alert", "搞 Telegram 通知", "加价格提醒" | **Flow A → B** |
| "let me chat with bot", "talk to bot in plain language" / "和 bot 聊天", "用 NL 跟 bot 说话" | **Flow A → B → C** |
| "make it real-time", "switch to webhook", "1-second response", "webhook upgrade" / "升级 webhook", "实时回复", "秒回" | **Flow D** (assumes A+B+C done) |
| "it's broken", "no reply", "I'm getting an error", "btoa error", "403 error" / "不工作了", "报错了", "没回应" | **GOTCHAS** matrix |
| "what does it do?", "is this for me?", "how much does it cost?" / "这是干啥的", "多少钱", "适合我吗" | Read aloud from `INTRODUCTION.md` — don't install yet |

If matching is ambiguous (e.g. "I want stock alerts" — alerts-only vs. + chat?), **ask exactly one disambiguating question, not many**. Default to *less* setup unless the user signals more.

---

## Phase 3 — FLOWS (step-by-step)

Steps are designed to be copy-pasteable. If a command fails, jump to the matching gotcha by number — don't improvise.

### Flow A — Core install (analysis skills only)

**Goal**: user can ask Claude Code "analyze NVDA" / "macro warning" / "审一下我的组合" and get answers. No Telegram, no cron.

```
A1. Verify Claude Code:        claude --version
A2. Clone repo:                git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills
A3. Run setup:                 bash ~/.claude/skills/setup.sh
A4. Install yfmcp:             claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp
A5. Verify in Claude Code:     type `analyze NVDA` — expect 10-step deep-dive output
```

**Stop conditions**:
- A1 fails → guide user to https://docs.claude.com/claude-code/install
- A2 fails because `~/.claude/skills` already has content → stop and ask user: "Overwrite, merge, or use a different path?"
- A5 returns generic text (not a 10-step format) → skills didn't load. Check `ls ~/.claude/skills/analyze-stock/SKILL.md`.

### Flow B — Price alerts via GitHub Actions polling

Add Telegram push when a stock crosses a threshold. No bidirectional chat yet.

**Prereq**: Flow A complete.

```
B1. Create Telegram bot:
    - In Telegram, message @BotFather
    - Send /newbot, follow prompts
    - Pick a username ending in `bot`
    - COPY the token (format: 123456789:ABCdef-Ghi...)

B2. Get your chat_id:
    - Send any message to your new bot from your phone
    - Visit https://api.telegram.org/bot<TOKEN>/getUpdates  (replace <TOKEN>)
    - Find "chat":{"id":<NUMBER>} — that number is your chat_id

B3. Fork the repo to your GitHub:
    https://github.com/ssurmic/claude-investment-skills/fork

B4. Set GitHub Secrets on the fork:
    Open https://github.com/<USERNAME>/claude-investment-skills/settings/secrets/actions/new
    Create:
      TELEGRAM_BOT_TOKEN  ← from B1
      TELEGRAM_CHAT_ID    ← from B2

B5. Confirm cron is running:
    Open the Actions tab on the fork — `price-alerts.yml` should run every 2 min.

B6. Smoke test with a guaranteed-fire alert:
    cd ~/.claude/skills/price-alert
    cat > alerts.json <<'EOF'
    {"alerts":[{"id":"test-1","ticker":"SPY","condition":{"op":"below","threshold":999999},"note":"smoke test","active":true,"fired":false}]}
    EOF
    git add alerts.json && git commit -m "smoke test" && git push

    Within 2-15 min, the user's phone should buzz with a Telegram alert.
    Then cancel: edit alerts.json or run cancel_alert.py.
```

**Stop conditions**:
- B1 token has no colon `:` → user copied wrong string. Re-message BotFather.
- B2 `getUpdates` returns empty `result: []` → user didn't message the bot first. Send any text from phone, retry.
- B6 phone gets nothing after 20 min → check Actions tab for failed runs; most likely `TELEGRAM_CHAT_ID` is wrong or quoted.

### Flow C — Bidirectional chat via polling (Option A)

The user can text the bot in plain English/Chinese and it adds/lists/cancels alerts automatically. Uses Claude API via cron polling — latency 2-15 min.

**Prereq**: Flow A + B complete.

```
C1. Get Anthropic API key:
    - https://console.anthropic.com → API Keys → Create Key
    - COPY the sk-ant-api03-... string immediately
    - CRITICAL: Settings → Billing → add $5+ credits (trial credits don't cover tool use — see G6)

C2. Add ANTHROPIC_API_KEY to GitHub Secrets:
    Same path as B4, secret name EXACTLY: ANTHROPIC_API_KEY

C3. Enable the chat workflow:
    On the fork: Actions tab → "Telegram Chat Handler" → click Enable
    Polling starts within ~5 min.

C4. Smoke test from phone:
    Text the bot: "What alerts do I have?"
    Within 2-15 min, expect a reply listing current alerts.
```

**Stop conditions**:
- C4 silence > 20 min → see GOTCHAS G5 (silent failure).
- C4 returns "credit balance too low" → see G6.

### Flow D — Webhook upgrade (Option B, Cloudflare Worker)

Replace polling chat with a Cloudflare Worker webhook. Latency drops 2-15 min → 1-3 sec. Still $0.

**Prereq**: Flow A + B + C complete and **verified working**. Do not run Flow D before Flow C is verified — it's much easier to debug each layer in sequence.

```
D1. Install wrangler:
    npm install -g wrangler
    wrangler --version   # should print 4.x or higher
    wrangler login       # opens browser, OAuth via Cloudflare

D2. Create GitHub fine-grained PAT (READ G3 BEFORE DOING THIS):
    https://github.com/settings/personal-access-tokens/new
    - Token name:           price-alert-webhook
    - Expiration:           90 days
    - Repository access:    "Only select repositories" → pick the fork
    - Repository permissions → Contents → "Read and write"  ← THE most common mistake
    - Generate token → COPY the github_pat_... string (only shown once)

D3. Set Cloudflare Worker secrets:
    cd ~/.claude/skills/price-alert/webhook
    wrangler secret put TELEGRAM_BOT_TOKEN     # paste B1 token
    wrangler secret put TELEGRAM_CHAT_ID       # paste B2 chat_id
    wrangler secret put ANTHROPIC_API_KEY      # paste C1 key
    wrangler secret put GITHUB_TOKEN           # paste D2 PAT
    wrangler secret put GITHUB_REPO            # paste <user>/claude-investment-skills

    wrangler secret list    # confirm 5 secrets

D4. Deploy the worker (first time picks subdomain — see G2):
    wrangler deploy
    # Note the final URL: https://price-alert-webhook.<subdomain>.workers.dev

D5. Point Telegram at the webhook:
    TOKEN="<B1 token>"
    URL="https://price-alert-webhook.<subdomain>.workers.dev"
    curl -F "url=$URL" "https://api.telegram.org/bot$TOKEN/setWebhook"
    # Expected: {"ok":true,"description":"Webhook was set"}
    curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
    # url field must match $URL; last_error_message must be empty

D6. Disable polling workflow (optional, recommended):
    gh workflow disable telegram-chat.yml --repo <user>/claude-investment-skills

D7. End-to-end smoke test from phone:
    "list my alerts"   → expect reply in 1-3 seconds.
```

**Stop conditions**:
- D2 PAT permissions skipped Contents → see G3.
- D4 subdomain prompt rejects input → see G2.
- D5 `setWebhook` returns `last_error_message: SSL error` → see G1.
- D7 silence > 30 sec → see G5.

---

## Phase 4 — GOTCHAS (numbered for direct reference)

Each gotcha: cue (what user sees), cause, fix.

### G1 — Telegram shows "SSL error" right after first webhook deploy

**Cue**: `curl ".../getWebhookInfo"` shows `"last_error_message":"SSL error..."` within 1-2 min of first `wrangler deploy`.

**Cause**: Cloudflare provisioned the URL faster than DNS propagated. Telegram tried to POST, failed, and is now backing off.

**Fix**: wait 2 min, then force retry:
```bash
curl "https://api.telegram.org/bot$TOKEN/deleteWebhook"
curl -F "url=$URL" "https://api.telegram.org/bot$TOKEN/setWebhook"
```

### G2 — wrangler refuses single-letter subdomain

**Cue**: First `wrangler deploy` prompts `What would you like your workers.dev subdomain to be?` and rejects `y`, `n`, `1`, etc.

**Cause**: Cloudflare requires 3-63 chars, letters/digits/hyphens only, no leading/trailing hyphens, globally unique. Single letters are reserved/taken.

**Fix**: pick the user's GitHub username. Common picks (`bot`, `john`, `worker`) are all taken — get distinctive. Subdomain is **permanent per account** — confirm with user before submitting.

### G3 — Worker logs "GitHub commit failed: 403 Resource not accessible by personal access token"

**Cue**: Bot replies `⚠️ Error: GitHub commit failed: 403...` — OR — `wrangler tail` shows that error in logs.

**Cause**: **PAT was created with Contents: Read-only**, not Read+Write. The worker can `GET` alerts.json (public repos don't even need auth) but every `PUT` (commit) fails. This is the **#1 most common Flow D failure**.

**Fix**:
1. https://github.com/settings/personal-access-tokens
2. Click `price-alert-webhook` → click "Edit" next to "Access on \<user\>"
3. Repository access → "Only select repositories" → pick the fork
4. Repository permissions → Add `Contents` → set to **Read and write**
5. Click **Update**
6. **Token string stays the same** — no need to redo `wrangler secret put GITHUB_TOKEN`

**Detect proactively**: before deploying Flow D, test the PAT with this no-op PUT:
```bash
SHA=$(curl -s -H "Authorization: Bearer $PAT" \
  "https://api.github.com/repos/$REPO/contents/price-alert/alerts.json" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['sha'])")
B64=$(curl -s "https://api.github.com/repos/$REPO/contents/price-alert/alerts.json" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['content'].replace('\n',''))")
curl -X PUT -H "Authorization: Bearer $PAT" \
  "https://api.github.com/repos/$REPO/contents/price-alert/alerts.json" \
  -d "{\"message\":\"PAT diag\",\"content\":\"$B64\",\"sha\":\"$SHA\",\"branch\":\"main\"}"
```
Response must contain `"commit":` — anything containing `"403"` or `"Resource not accessible"` means the PAT needs G3 fix.

### G4 — Worker replies `⚠️ Error: btoa() can only operate on characters in the Latin1 range`

**Cue**: Bot's error reply contains "btoa()" and "Latin1".

**Cause**: Outdated `worker.ts`. Current main uses `TextEncoder`/`TextDecoder` to round-trip non-Latin1 chars (Chinese notes, em-dashes, emoji).

**Fix**:
```bash
cd ~/.claude/skills && git pull
cd price-alert/webhook && wrangler deploy
```

### G5 — Bot doesn't reply at all (no error, just silence)

**Cue**: User sends Telegram message, nothing happens for 30+ sec, no error message either.

**Cause** — three possibilities, debug in this order:
1. Webhook not actually set → Telegram queues but doesn't deliver
2. Worker URL typo or wrong subdomain
3. Worker code crashed silently in the async `waitUntil` path

**Fix sequence**:
```bash
# 1. Confirm webhook is registered
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
# url field should match the deployed worker URL exactly

# 2. Live-tail worker logs
cd ~/.claude/skills/price-alert/webhook
wrangler tail
# Have user send a Telegram message from their phone.
# If NO log line appears → webhook URL wrong, redo D5.
# If an incoming request appears + an exception → match the error against G3/G4/G6.
```

### G6 — Anthropic API returns "credit balance too low"

**Cue**: Bot replies `⚠️ Error: Anthropic API error: 400 ... credit balance...`.

**Cause**: API key is valid but the account has no paid credits. **Trial credits do NOT cover tool use** — this is a common surprise.

**Fix**: console.anthropic.com → Settings → Billing → add $5+. Suggest enabling auto-reload at $5 trigger so it never runs out.

### G7 — Local `git push` rejected after webhook commits new alerts

**Cue**: `git push` fails with `! [rejected] (fetch first)` after webhook handled a chat message.

**Cause**: The webhook just committed an updated `alerts.json` via the GitHub Contents API. Local main is behind remote main.

**Fix**:
```bash
git pull --rebase origin main
git push
```

Never use `git push --force` to "fix" this — it would overwrite the webhook's commits.

### G8 — Duplicate alerts after manually retrying telegram-chat workflow

**Cue**: User triggered the polling workflow twice via "Run workflow" button and now has 2x of the same alert.

**Cause**: Telegram update offset race — both runs processed the same getUpdates response.

**Fix**: cancel one via the bot ("cancel the duplicate"). Don't manually re-run the workflow; let the cron drive it. With Flow D (webhook), this gotcha disappears entirely.

### G9 — `wrangler login` opens browser but auth doesn't complete

**Cue**: Browser opens, OAuth screen shows, user clicks Authorize, but `wrangler` CLI keeps waiting.

**Cause**: usually a corporate VPN or browser blocking the callback to `localhost:8976`.

**Fix**: try `wrangler login` from a non-VPN session. If still stuck, use API token: Cloudflare dashboard → My Profile → API Tokens → create "Edit Cloudflare Workers" template → `export CLOUDFLARE_API_TOKEN=<token>` and skip `wrangler login`.

---

## Phase 5 — VERIFICATION commands

Run these to confirm state at each milestone:

| Check | Command | Expected |
|---|---|---|
| Repo cloned correctly | `ls ~/.claude/skills/setup.sh` | file exists |
| yfmcp installed | `claude mcp list \| grep yfmcp` | one line |
| Telegram bot reachable | `curl "https://api.telegram.org/bot$TOKEN/getMe"` | `{"ok":true,...}` |
| GH Actions enabled | `gh workflow list --repo <user>/claude-investment-skills` | both workflows listed |
| GitHub Secrets set | `gh secret list --repo <user>/claude-investment-skills` | shows secret names (values hidden) |
| Cloudflare worker deployed | `curl https://price-alert-webhook.<sub>.workers.dev` | `price-alert webhook — POST only` |
| Worker secrets set | `wrangler secret list` (in `webhook/` dir) | 5 entries |
| Webhook registered + healthy | `curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"` | `url` non-empty, no `last_error_message` |
| PAT can write to repo | G3 no-op PUT diagnostic | response contains `"commit":` |

---

## Phase 6 — HANDOFF (when to stop and ask the user)

**Always pause and ask** (don't auto-decide) before:
- Forking a repo if a fork might already exist
- Overwriting `~/.claude/skills/` if non-empty
- Picking a workers.dev subdomain (permanent for the account)
- Adding credit to Anthropic API (real money)
- Deleting workflows or webhooks
- Force-pushing to main
- Changing Cloudflare account settings beyond the worker scope

**Can proceed silently** for:
- `git pull` / `npm install` / `pip install`
- Reading files, listing dirs, checking versions
- Setting GitHub Secrets via API (encrypted, reversible)
- Re-running `wrangler deploy` (idempotent)
- Editing the user's local working tree (Edit tool, etc.)

---

## Phase 7 — POST-INSTALL

After the user's chosen flow completes successfully:

1. **Recap what got set up** — concise summary with the worker URL (if Flow D), the bot @handle, and which workflows are active.
2. **Try it now** — give one example phrasing from `EXAMPLES.md` in the user's language:
   - EN: "alert me when NVDA hits $1200"
   - CN: "NVDA 跌到 1200 通知我"
3. **Cost expectation** — repeat the $0-$4/mo figure with a one-line breakdown.
4. **Where to find more**:
   - `EXAMPLES.md` — 50+ NL phrasings for alert setup
   - `AGENT-TOOL-REFERENCE.md` — tool-invocation contracts for the analysis skills
   - `INTRODUCTION.md` — architecture deep-dive if they want to understand internals

Then **hand off**. Your job is done. Future utterances are runtime, not setup — switch to AGENT-TOOL-REFERENCE.md mode.

---

## Appendix A — Required-credentials checklist

Show this to the user before starting Flow D so they can gather everything once:

```
□ GitHub fork URL                                                     (Flow B Step B3)
□ Telegram bot token from @BotFather                                  (Flow B Step B1)
□ Telegram chat_id from getUpdates                                    (Flow B Step B2)
□ Anthropic API key from console.anthropic.com (+ $5 credits!)        (Flow C Step C1)
□ Cloudflare account (free signup)                                    (Flow D prereq)
□ Node.js installed locally                                           (Flow D prereq)
□ GitHub fine-grained PAT (Contents: Read AND Write) on the fork      (Flow D Step D2)
```

If any are missing, **stop and gather them first**. Switching between "gather mode" and "execute mode" mid-flow leaves brittle half-states that are hard to debug.

---

## Appendix B — Files modified at each phase

If you need to undo or audit:

| Phase | Files written / changed |
|---|---|
| Flow A | `~/.claude/skills/` (clone), `/tmp/.insider_venv/` (venv), `~/.claude.json` (mcp registration) |
| Flow B | GitHub fork's Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), `price-alert/alerts.json` (commits) |
| Flow C | GitHub fork's Secrets (`ANTHROPIC_API_KEY`), `price-alert/tg_state.json` (auto-commits) |
| Flow D | Cloudflare Worker (`price-alert-webhook` deployment), Worker secrets (5 entries), Telegram webhook URL setting, GitHub PAT (new fine-grained token) |

---

## Versioning

This file targets repo version **1.6** (post-webhook). When a major flow changes (e.g. new chat path, new alert type), bump version + add a "Migrating from N → N+1" section.

If a step here diverges from `SETUP.md` or `SETUP-WEBHOOK.md`, **the SETUP files are authoritative** for exact button-by-button details — they have screenshots and screen-by-screen text. This file is the orchestration layer; SETUP files are the verbatim screens.

---

## Quick map for the hurried agent

User pasted the URL of this repo and said "set it up". Do this:

1. `cat AGENTS.md` (this file) → identify flow
2. `cat README.md` if you need to answer "what is this" first
3. PREP questionnaire → only ask the unknowns
4. Walk through the chosen flow's steps, one at a time
5. After each step, run the matching verification command
6. On any error → match against GOTCHAS table by error string
7. After last step → POST-INSTALL recap, then hand off to `AGENT-TOOL-REFERENCE.md`
