# AGENTS.md —— AI 编码 agent 的 setup 编排指南

**谁读这个**：任何 AI agent（Claude Code、OpenAI Codex、Cursor、自定义 CLI agent）—— 用户想让它帮**安装/配置**这个 repo 时。触发场景：用户粘贴了这个 repo 的 URL，或者说了类似"帮我装一下 / 配一下 / 把这些 skill 搞起来"。

**谁不读这个**：装完之后想**调用工具**的 agent —— 读 [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md)。

这个文件是 agent 的权威指南。Codex 找 `AGENTS.md`，Claude Code 也找 `CLAUDE.md`，Cursor 找 `.cursor/rules/*`。其他名字应该 symlink 或 include 这个文件。

[English version](./AGENTS.md)

---

## 索引 —— 啥时候读啥

| 文档 | 啥时候 agent 读 |
|---|---|
| **AGENTS.md（本文件）** | 编排全新安装或升级 —— 一步步走 |
| [`README.md`](./README.md) | 给用户解释"这是干啥的" / 架构 |
| [`INTRODUCTION.md`](./INTRODUCTION.md) | 更深入的架构、成本、tech stack 问题 |
| [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md) | 装完之后 —— 把用户 NL 翻译成分析 skill 的 CLI 命令 |
| [`INVESTMENT-WORKFLOW.md`](./INVESTMENT-WORKFLOW.md) | 用户的投资问题该匹配哪个 skill |
| [`price-alert/SETUP.md`](./price-alert/SETUP.md) | Polling setup 的逐按钮详细步骤 |
| [`price-alert/SETUP-WEBHOOK.md`](./price-alert/SETUP-WEBHOOK.md) | Webhook 升级（在 SETUP.md 基础上）|
| [`price-alert/EXAMPLES.md`](./price-alert/EXAMPLES.md) | 装完之后 —— 给用户展示有哪些 NL 说法可用 |

**经验规则**：本文件告诉你**该做什么**；链接的 SETUP 文档是**精确的按钮级细节**。按本文件的 flow 走，遇到"做 SETUP-WEBHOOK.md 的 Part 3"时，打开那一节跟用户逐字走。

**`AGENT-TOOL-REFERENCE.md` 覆盖范围**：6 个 CLI 工具（`insider_ratio.py`、`cluster_buy_scan.py`、`quote_pull.py`、`option_walls.py`、`max_pain.py`、`price-alert/` 套件）+ Skill Catalog 把全部 13 个纯 NL skill（analyze-stock、earnings-prep、find-alpha、leaps-screen 等）映射到中英 trigger 短语。Setup 完成后读它的 Skill Catalog 章节，掌握"用户说什么 → 触发哪个 skill"。

---

## 心智模型 —— 啥跑在哪（动手之前先内化这个）

引导用户走 setup 之前，先在脑里建好组件分工。**大多数 setup 困惑来自把 GitHub Actions 当成"引擎"** —— 不是。GitHub 只是小小的存储 + cron 层。智能跑在用户电脑的 Claude Code 里。

```
本地（用户电脑）
  ├── Claude Code              ← AI 大脑（读 NL，挑 skill）
  ├── ~/.claude/skills/        ← 本仓库，clone 到这
  │   ├── */SKILL.md           ← Claude 照着走的 markdown 指令
  │   ├── */scripts/*.py       ← Claude 执行的 Python 帮手
  │   └── price-alert/alerts.json  ← 用户或 bot 都能改
  └── （analyze-stock 这种分析 skill **从不**调远端 GitHub ——
       它们直接从本地拉 yfinance + openinsider）

GITHUB（小角色：存储 + cron，**价格扫描 loop 里没有 AI**）
  ├── repo 存储                ← alerts.json source of truth
  ├── price-alerts.yml         ← cron 2 分钟: 读 alerts.json → 查价 →
  │                              推 Telegram。**纯 Python，不调 Claude API**
  └── telegram-chat.yml        ← （仅选项 A）cron 2-5 分钟: poll Telegram →
                                  调 Claude API → 改 alerts.json

TELEGRAM
  └── @bot                     ← 收推送、收发用户聊天

CLOUDFLARE WORKER（仅选项 B chat 路径 —— 替换 telegram-chat.yml）
  └── webhook                  ← 即时收 Telegram POST → 调 Claude API → 改 alerts.json
```

**各种"移动平均线"在哪算**：
- "NVDA 当前 50DMA 是多少？"（分析）→ 用户电脑（Claude 调 `quote_pull.py`）
- "NVDA 跌破 50DMA 提醒我"（cron 驱动的 alert）→ GitHub Actions runner（`check_alerts.py`）
- "用 bot 设这个 alert"（chat）→ chat 路径所在处（GH cron 或 CF Worker）

**给用户解释时，开头就说**："所有真正的投资思考都在你电脑上做。GitHub 只是一个 JSON 文件 + 一个推 Telegram 的 cron。Cloudflare（如果你装了）只是更快版本的同一件事。**你没有把决策权交给服务器**。"

这个 framing 化解了常见的"这玩意会自己交易吗"的担心 —— 答案是不会，它只是在你手机上推送研究级别的触发提醒。

---

## 阶段 1 —— PREP（动手**之前**做这个）

先分类用户的情况。每个问题只在你**没法从上下文推断**时才问（用户消息里的文件路径、OS 提示、之前的对话都算上下文）。

### PREP 问卷

心里跑一遍，只把**未知项**问出来。

| 问题 | 为啥重要 | 如果"我不知道" |
|---|---|---|
| **OS？** | macOS / Linux / WSL 都行；Windows 原生不支持 | 跑 `uname -s` |
| **Python ≥ 3.9？** | 分析 skill 需要 | 跑 `python3 --version` |
| **装了 Node.js？** | 仅 Flow D（webhook）需要 | 跑 `node --version` |
| **装了 Claude Code？** | NL 触发 skill 需要 | 跑 `claude --version` |
| **手机有 Telegram？** | 价格 alert（任何路径）必需 | 让他装 Telegram |
| **GitHub 账号？** | fork + 跑 workflows 必需 | github.com/signup |
| **Cloudflare 账号？** | 仅 Flow D 需要 | cloudflare.com 免费注册 |
| **目标：只要 alert，还是要跟 bot 对话？** | 决定是否启用 Anthropic API 路径 | 默认：只要 alert（$0/月）|
| **OK 用 public GitHub repo？** | Public = GH Actions 免费无限；private = 2000 min/月上限 | 默认 public |
| **聊天延迟容忍度？** | <3 秒 → 需要 Flow D；几分钟也行 → Flow C 够 | 默认 Flow C |

### 决策树

```
用户说"从零开始装":
  ↓ 要价格 alert 吗？
  ├─ 不要 → 只 Flow A（仅分析 skill）── 停在这，$0/月
  └─ 要   → Flow A + B（polling alert）
           ↓ 要跟 bot NL 对话吗？
           ├─ 不要 → 停，$0/月
           └─ 要   → A + B + C（polling chat）── 停，~$1-4/月
                    ↓ 需要 <3 秒回复吗？
                    ├─ 不需要 → 停
                    └─ 需要   → A + B + C + D（webhook 升级）── 还是 ~$1-4/月

用户说"alert 慢" / "聊天搞快点":
  → 已经有 A+B+C 了，直接跳 Flow D

用户说"坏了 / 不工作了":
  → 跳过 flow，直接 GOTCHAS 矩阵
```

---

## 阶段 2 —— DETECTION（用户说什么 → 走哪个 flow）

匹配用户的第一条消息到对应 flow。双语触发：

| 用户说（EN / CN）| 开始的 Flow |
|---|---|
| "set me up", "install this" / "帮我装一下", "怎么配置", "从零开始" | **Flow A** |
| "set up alerts", "telegram notifications" / "配 alert", "搞 Telegram 通知", "加价格提醒" | **Flow A → B** |
| "let me chat with bot" / "和 bot 聊天", "用 NL 跟 bot 说话" | **Flow A → B → C** |
| "make it real-time", "switch to webhook", "1-second response" / "升级 webhook", "实时回复", "秒回" | **Flow D**（前提：A+B+C 已完成）|
| "it's broken", "btoa error", "403 error" / "不工作了", "报错了", "没回应" | **GOTCHAS** 矩阵 |
| "what does it do?", "how much does it cost?" / "这是干啥的", "多少钱", "适合我吗" | 先从 `INTRODUCTION.md` 念给用户听 —— 别急着装 |

匹配模糊时（例如"我要股票 alert" —— 只要 alert 还是要 chat？）**只问一个澄清问题，不要问一堆**。模糊时默认**少装**而非多装。

---

## 阶段 3 —— FLOWS（一步步走）

步骤设计成可复制粘贴。命令失败时，按编号跳到对应 gotcha —— **不要瞎改**。

### Flow A —— 核心安装（仅分析 skill）

**目标**：用户在 Claude Code 里说"analyze NVDA" / "macro warning" / "审一下我的组合" 能得到答案。不用 Telegram，不用 cron。

```
A1. 验证 Claude Code:           claude --version
A2. Clone repo:                git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills
A3. 跑 setup:                  bash ~/.claude/skills/setup.sh
A4. 装 yfmcp:                  claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp
A5. 在 Claude Code 里验证:      输入 `analyze NVDA` —— 期望 10 步深度分析输出
```

**停止条件**：
- A1 失败 → 引导到 https://docs.claude.com/claude-code/install
- A2 失败因为 `~/.claude/skills` 已有内容 → 停下问用户："覆盖、合并、还是用别的路径？"
- A5 返回通用文字（不是 10 步格式）→ skill 没加载。检查 `ls ~/.claude/skills/analyze-stock/SKILL.md`。

### Flow B —— GitHub Actions polling 的价格 alert

加 Telegram 推送通知（股价穿越阈值时）。**还没有**双向对话。

**前提**：Flow A 完成。

```
B1. 创建 Telegram bot:
    - Telegram 里找 @BotFather
    - 发 /newbot, 按提示走
    - 用户名必须以 `bot` 结尾
    - 复制 token（格式: 123456789:ABCdef-Ghi...）

B2. 拿你的 chat_id:
    - 用手机给你新的 bot 发任意消息
    - 访问 https://api.telegram.org/bot<TOKEN>/getUpdates（替换 <TOKEN>）
    - 找 "chat":{"id":<NUMBER>} —— 那个数字就是 chat_id

B3. Fork 这个 repo 到你的 GitHub:
    https://github.com/ssurmic/claude-investment-skills/fork

B4. 给 fork 设 GitHub Secrets:
    打开 https://github.com/<USERNAME>/claude-investment-skills/settings/secrets/actions/new
    创建:
      TELEGRAM_BOT_TOKEN  ← 来自 B1
      TELEGRAM_CHAT_ID    ← 来自 B2

B5. 确认 cron 在跑:
    fork 的 Actions tab —— `price-alerts.yml` 应该每 2 min 跑一次。

B6. 用"必触发" alert 烟雾测试:
    cd ~/.claude/skills/price-alert
    cat > alerts.json <<'EOF'
    {"alerts":[{"id":"test-1","ticker":"SPY","condition":{"op":"below","threshold":999999},"note":"smoke test","active":true,"fired":false}]}
    EOF
    git add alerts.json && git commit -m "smoke test" && git push

    2-15 min 内手机应该收到 Telegram 推送。
    然后取消: 改 alerts.json 或跑 cancel_alert.py。
```

**停止条件**：
- B1 token 里没有冒号 `:` → 用户复制错了。重新跟 BotFather 聊。
- B2 `getUpdates` 返回 `result: []` → 用户没先给 bot 发消息。从手机发任意文字，重试。
- B6 20 min 还没收到 → 看 Actions tab 失败的 run；大概率 `TELEGRAM_CHAT_ID` 写错或带引号。

### Flow C —— Polling 双向聊天（选项 A）

用户能用中/英自然语言跟 bot 聊（"GLW 跌到 140 通知我"），bot 自动加/列/取消 alert。用 Claude API + cron polling —— 延迟 2-15 min。

**前提**：Flow A + B 完成。

```
C1. 拿 Anthropic API key:
    - https://console.anthropic.com → API Keys → Create Key
    - 立刻复制 sk-ant-api03-... 那串
    - 关键: Settings → Billing → 充 $5+ 信用额度
      （trial 信用不覆盖 tool use —— 见 G6）

C2. 把 ANTHROPIC_API_KEY 加到 GitHub Secrets:
    路径同 B4, secret 名字精确: ANTHROPIC_API_KEY

C3. 启用 chat workflow:
    fork 的 Actions tab → "Telegram Chat Handler" → 点 Enable
    ~5 min 内 polling 开始。

C4. 手机烟雾测试:
    给 bot 发: "我有哪些 alert?"
    2-15 min 内应该回复列出当前 alert。
```

**停止条件**：
- C4 静默 > 20 min → 见 GOTCHAS G5（silent failure）。
- C4 返回 "credit balance too low" → 见 G6。

### Flow D —— Webhook 升级（选项 B，Cloudflare Worker）

把 polling chat 换成 Cloudflare Worker webhook。延迟从 2-15 min 掉到 1-3 秒。还是 $0。

**前提**：Flow A + B + C 已完成**且验证 work**。**别在 Flow C 验证前跑 Flow D** —— 一层层调试容易得多。

```
D1. 装 wrangler:
    npm install -g wrangler
    wrangler --version   # 应该是 4.x 或更新
    wrangler login       # 开浏览器, 走 OAuth

D2. 创建 GitHub fine-grained PAT（做之前先读 G3！）:
    https://github.com/settings/personal-access-tokens/new
    - Token name:           price-alert-webhook
    - Expiration:           90 天
    - Repository access:    "Only select repositories" → 选 fork
    - Repository permissions → Contents → "Read and write"  ← 最常踩的坑
    - Generate token → 立刻复制 github_pat_... 字符串（只显示一次）

D3. 设 Cloudflare Worker secrets:
    cd ~/.claude/skills/price-alert/webhook
    wrangler secret put TELEGRAM_BOT_TOKEN     # 粘 B1 token
    wrangler secret put TELEGRAM_CHAT_ID       # 粘 B2 chat_id
    wrangler secret put ANTHROPIC_API_KEY      # 粘 C1 key
    wrangler secret put GITHUB_TOKEN           # 粘 D2 PAT
    wrangler secret put GITHUB_REPO            # 粘 <user>/claude-investment-skills

    wrangler secret list    # 确认 5 个 secrets

D4. 部署 worker（首次会问 subdomain —— 见 G2）:
    wrangler deploy
    # 记下最终 URL: https://price-alert-webhook.<subdomain>.workers.dev

D5. 把 Telegram 指向 webhook:
    TOKEN="<B1 的 token>"
    URL="https://price-alert-webhook.<subdomain>.workers.dev"
    curl -F "url=$URL" "https://api.telegram.org/bot$TOKEN/setWebhook"
    # 期望: {"ok":true,"description":"Webhook was set"}
    curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
    # url 字段必须等于 $URL; last_error_message 必须为空

D6. 关掉 polling workflow（可选，推荐）:
    gh workflow disable telegram-chat.yml --repo <user>/claude-investment-skills

D7. 端到端烟雾测试（从手机）:
    "我的 alert" → 期望 1-3 秒内回复。
```

**停止条件**：
- D2 PAT 漏了 Contents 权限 → 见 G3。
- D4 subdomain 提示被拒 → 见 G2。
- D5 `setWebhook` 返回 `last_error_message: SSL error` → 见 G1。
- D7 静默 > 30 秒 → 见 G5。

---

## 阶段 4 —— GOTCHAS（编号，便于直接引用）

每个 gotcha：用户看到的提示、原因、修复方法。

### G1 —— 首次部署 webhook 后 Telegram 报 "SSL error"

**提示**：`curl ".../getWebhookInfo"` 显示 `"last_error_message":"SSL error..."`，发生在首次 `wrangler deploy` 后 1-2 min 内。

**原因**：Cloudflare 给 URL 配好了但 DNS 还没传播。Telegram 试着 POST 失败，正在退避。

**修复**：等 2 min，然后强制重试：
```bash
curl "https://api.telegram.org/bot$TOKEN/deleteWebhook"
curl -F "url=$URL" "https://api.telegram.org/bot$TOKEN/setWebhook"
```

### G2 —— wrangler 拒绝单字符 subdomain

**提示**：第一次 `wrangler deploy` 问 `What would you like your workers.dev subdomain to be?`，拒绝 `y`、`n`、`1` 等。

**原因**：Cloudflare 要求 3-63 字符，字母/数字/连字符，不能首尾带连字符，全球唯一。单字符已被占用/预留。

**修复**：用用户的 GitHub 用户名。常见词（`bot`、`john`、`worker`）都被占了 —— 取特别点的。Subdomain **在该账号下永久绑定** —— 提交前跟用户确认。

### G3 —— Worker 日志显示 "GitHub commit failed: 403 Resource not accessible by personal access token"

**提示**：Bot 回 `⚠️ Error: GitHub commit failed: 403...` 或 `wrangler tail` 日志里有这个错。

**原因**：**PAT 创建时 Contents 设成 Read-only** 而不是 Read+Write。Worker 能 `GET` alerts.json（public repo 不用 auth 都能 GET）但每次 `PUT`（commit）都失败。这是 **Flow D 最常见的 #1 故障**。

**修复**：
1. https://github.com/settings/personal-access-tokens
2. 点 `price-alert-webhook` → 点 "Access on \<user\>" 旁边的 "Edit"
3. Repository access → "Only select repositories" → 选 fork
4. Repository permissions → 加 `Contents` → 设成 **Read and write**
5. 点 **Update**
6. **Token 字符串不变** —— 不用重新跑 `wrangler secret put GITHUB_TOKEN`

**主动检测**：部署 Flow D 前先用这个 no-op PUT 测 PAT：
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
响应必须含 `"commit":` —— 任何含 `"403"` 或 `"Resource not accessible"` 的都说明要做 G3 修复。

### G4 —— Worker 回 `⚠️ Error: btoa() can only operate on characters in the Latin1 range`

**提示**：Bot 的错误回复含 "btoa()" 和 "Latin1"。

**原因**：`worker.ts` 过时了。当前 main 用 `TextEncoder`/`TextDecoder` 处理非 Latin1 字符（中文 note、em-dash、emoji）。

**修复**：
```bash
cd ~/.claude/skills && git pull
cd price-alert/webhook && wrangler deploy
```

### G5 —— Bot 完全不回（没错误，纯静默）

**提示**：用户发 Telegram 消息，30+ 秒没动静，也没错误信息。

**原因** —— 三种可能，按此顺序调试：
1. Webhook 没真正设置 → Telegram 排队但没投递
2. Worker URL 打错或 subdomain 错
3. Worker 代码在 async `waitUntil` 路径里静默崩了

**修复顺序**：
```bash
# 1. 确认 webhook 注册了
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
# url 字段必须精确匹配部署后的 worker URL

# 2. 实时看 worker logs
cd ~/.claude/skills/price-alert/webhook
wrangler tail
# 让用户从手机发消息。
# 如果没有任何 log → webhook URL 错了, 重做 D5。
# 如果有 incoming request + 异常 → 把错误对照 G3/G4/G6。
```

### G6 —— Anthropic API 返回 "credit balance too low"

**提示**：Bot 回 `⚠️ Error: Anthropic API error: 400 ... credit balance...`.

**原因**：API key 有效但账号没付费余额。**Trial 信用不覆盖 tool use** —— 这是常见 surprise。

**修复**：console.anthropic.com → Settings → Billing → 充 $5+。建议开 auto-reload（余额 < $5 自动充）省心。

### G7 —— 本地 `git push` 被拒（webhook 刚 commit 过 alert）

**提示**：`git push` 失败 `! [rejected] (fetch first)`，发生在 webhook 处理过一条 chat 消息之后。

**原因**：Webhook 刚通过 GitHub Contents API commit 了更新的 alerts.json。本地 main 落后于 remote main。

**修复**：
```bash
git pull --rebase origin main
git push
```

**绝对不要**用 `git push --force` 来"修"这个 —— 会把 webhook 的 commit 覆盖掉。

### G8 —— 手动重跑 telegram-chat workflow 后出现重复 alert

**提示**：用户通过 "Run workflow" 按钮触发了两次 polling，现在同一个 alert 有 2 份。

**原因**：Telegram update offset race —— 两次 run 处理了同一份 getUpdates 响应。

**修复**：让 bot 取消其中一个（"取消重复的"）。别手动重跑 workflow；让 cron 自己跑。用了 Flow D（webhook）之后这个 gotcha 完全消失。

### G9 —— `wrangler login` 打开浏览器但 auth 不完成

**提示**：浏览器开了，OAuth 屏幕出现，用户点 Authorize，但 wrangler CLI 一直等着。

**原因**：通常是公司 VPN 或浏览器挡了到 `localhost:8976` 的 callback。

**修复**：换个无 VPN 的环境跑 `wrangler login`。还卡的话用 API token：Cloudflare dashboard → My Profile → API Tokens → 用 "Edit Cloudflare Workers" 模板 → `export CLOUDFLARE_API_TOKEN=<token>`，跳过 `wrangler login`。

---

## 阶段 5 —— VERIFICATION 命令

每个里程碑后跑这些确认状态：

| 检查 | 命令 | 期望 |
|---|---|---|
| Repo 克隆 OK | `ls ~/.claude/skills/setup.sh` | 文件存在 |
| yfmcp 装了 | `claude mcp list \| grep yfmcp` | 一行输出 |
| Telegram bot 通 | `curl "https://api.telegram.org/bot$TOKEN/getMe"` | `{"ok":true,...}` |
| GH Actions 启用 | `gh workflow list --repo <user>/claude-investment-skills` | 两个 workflow 都列出来 |
| GitHub Secrets 设了 | `gh secret list --repo <user>/claude-investment-skills` | secret 名字（值不显示） |
| Cloudflare worker 部署了 | `curl https://price-alert-webhook.<sub>.workers.dev` | `price-alert webhook — POST only` |
| Worker secrets 设了 | `wrangler secret list`（在 `webhook/` 目录）| 5 个 entries |
| Webhook 注册 + 健康 | `curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"` | `url` 非空，无 `last_error_message` |
| PAT 能写 | G3 的 no-op PUT 诊断 | 响应含 `"commit":` |

---

## 阶段 6 —— HANDOFF（何时停下问用户）

**永远暂停且问**（**不要**自作主张）：
- Fork 之前确认是否已有 fork
- 覆盖 `~/.claude/skills/` 如果非空
- 选 workers.dev subdomain（账号永久绑定）
- 给 Anthropic API 充钱（真金白银）
- 删除 workflows 或 webhooks
- Force-push 到 main
- 改 Cloudflare 账户里 worker 范围之外的设置

**可以静默执行**：
- `git pull` / `npm install` / `pip install`
- 读文件、列目录、查版本
- 通过 API 设 GitHub Secrets（加密，可逆）
- 重跑 `wrangler deploy`（幂等）
- 编辑用户本地工作树（Edit tool 等）

---

## 阶段 7 —— POST-INSTALL（装完之后）

用户选的 flow 成功完成后：

1. **总结装了什么** —— 简洁概括 worker URL（如果 Flow D）、bot @handle、哪些 workflow 在跑。
2. **现在试一下** —— 用用户的语言从 `EXAMPLES.md` 给一个例句：
   - EN: "alert me when NVDA hits $1200"
   - CN: "NVDA 跌到 1200 通知我"
3. **成本预期** —— 重复 $0-$4/月 那个数字，附一行细分。
4. **更多在哪**：
   - `EXAMPLES.md` —— 50+ 条 alert NL 说法
   - `AGENT-TOOL-REFERENCE.md` —— 分析 skill 的工具调用契约
   - `INTRODUCTION.md` —— 想搞懂内部的话看架构深度版

然后**交接**。你的活完了。后续都是运行时调用，不是 setup —— 切到 AGENT-TOOL-REFERENCE.md 模式。

---

## 附录 A —— 必需凭证清单

开始 Flow D 之前给用户看这个，让他一次性凑齐：

```
□ GitHub fork URL                                                       （Flow B Step B3）
□ Telegram bot token，来自 @BotFather                                    （Flow B Step B1）
□ Telegram chat_id，来自 getUpdates                                      （Flow B Step B2）
□ Anthropic API key，来自 console.anthropic.com（+ $5 信用！）           （Flow C Step C1）
□ Cloudflare 账号（免费）                                                （Flow D 前提）
□ 本地装好 Node.js                                                      （Flow D 前提）
□ GitHub fine-grained PAT（Contents: Read AND Write），范围限制到 fork    （Flow D Step D2）
```

任何一项缺 → **停下来先凑齐**。中途在"凑齐模式"和"执行模式"之间切换会留下脆弱的半成品状态，调试起来很痛。

---

## 附录 B —— 每个阶段改动的文件

需要回滚或审计时参考：

| 阶段 | 写了/改了哪些 |
|---|---|
| Flow A | `~/.claude/skills/`（克隆）、`/tmp/.insider_venv/`（venv）、`~/.claude.json`（mcp 注册）|
| Flow B | GitHub fork 的 Secrets（`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`）、`price-alert/alerts.json`（commits）|
| Flow C | GitHub fork 的 Secrets（`ANTHROPIC_API_KEY`）、`price-alert/tg_state.json`（自动 commit）|
| Flow D | Cloudflare Worker（`price-alert-webhook` 部署）、Worker secrets（5 个）、Telegram webhook URL 设置、GitHub PAT（新的 fine-grained token）|

---

## 版本

本文件对应 repo 版本 **1.6**（post-webhook）。重大 flow 变化时（例如新 chat 路径、新 alert 类型），升版本号 + 加"从 N 迁移到 N+1"章节。

如果这里的步骤跟 `SETUP.md` 或 `SETUP-WEBHOOK.md` 不一致，**SETUP 文件是权威** —— 它们有逐屏截图和按钮文字。本文件是编排层；SETUP 文件是逐屏实录。

---

## 给"赶时间的 agent"的快速地图

用户粘了 repo URL 说"装一下"。做这些：

1. `cat AGENTS.md`（本文件）→ 确定 flow
2. 用户问"这是啥"先 `cat README.md`
3. PREP 问卷 → 只问未知项
4. 按选定 flow 的步骤一个一个走
5. 每步后跑对应 verification 命令
6. 任何错误 → 用错误字符串匹配 GOTCHAS 表
7. 最后一步完成 → POST-INSTALL 总结，交接给 `AGENT-TOOL-REFERENCE.md`
