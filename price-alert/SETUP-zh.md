# Price Alert — 设置指南

> 任何股票跌到/涨到你定的价格时，手机推送通知给你。

[English version](./SETUP.md)

---

## 配好之后是什么效果

跟 Claude 说一句：

```
"Alert me when GLW hits $140"
"GLW 跌到 140 通知我"
```

…然后 15 分钟内当价格真的触发，你的手机收到 Telegram 推送：

```
🔻 PRICE ALERT: GLW

Current: $139.85
Trigger: $139.85 ≤ $140.00
52W high: $198.25 (-29.5% off)
Note: AI 玻璃基板 tier 1 入场
```

整套系统跑在 **GitHub Actions**（免费、24/7、不需要电脑开机）+ **Telegram**（手机即时推送）。

---

## 前提条件

| 需要 | 怎么搞 |
|---|---|
| **Telegram 账号** | iOS/Android 免费 app，或者 telegram.org 网页版 |
| **GitHub 账号** | github.com 免费注册 |
| **Fork 或 clone 这个 repo** | `git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills` |
| **Claude Code 已安装** | https://docs.claude.com/claude-code/install |

如果上面有缺，先搞这个。剩下流程 ~7 分钟。

---

## Part 1 — 建 Telegram bot（5 分钟）

### 1.1 在 Telegram 里找到 @BotFather

打开 Telegram，点搜索图标，输入 `@BotFather`。官方那个有蓝色✓认证标。点进去，点 **Start**。

### 1.2 发 `/newbot`

发消息 `/newbot`，BotFather 会问你两个问题：

```
BotFather: Alright, a new bot. How are we going to call it?
你:        Zizhao Price Alerts          ← 显示名（任意，emoji 可以）

BotFather: Good. Now let's choose a username for your bot.
           It must end in 'bot'.
你:        zizhao_pricealert_bot        ← 唯一 username，必须 _bot 结尾
```

### 1.3 保存 bot token

BotFather 会回类似这样：

```
Done! Congratulations on your new bot. You will find it at t.me/zizhao_pricealert_bot.

Use this token to access the HTTP API:
7234567890:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxx
   ↑ 这一整串就是你的 BOT_TOKEN —— 保存好
```

**⚠️ Token 等于密码。**任何人有它都能从你的 bot 发消息。**不要发到群里**，**不要 commit 到代码里**。

### 1.4 拿你的 chat_id

Telegram 需要知道**发到哪个聊天**（可能是你、群、频道）。最简单的方法：

1. Telegram 里搜你的 bot（`zizhao_pricealert_bot`）。
2. 点 **Start**，发任意消息（比如 `hello`）。
3. 浏览器打开（把 `<YOUR_TOKEN>` 替换成你的 token）:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
4. 你会看到 JSON。找 `"chat":{"id":...}` 字段：
   ```json
   {
     "ok": true,
     "result": [{
       "update_id": 123456789,
       "message": {
         "from": {"id": 987654321, ...},
         "chat": {
           "id": 987654321,        ← 这个数字就是你的 CHAT_ID
           "first_name": "你的名字"
         },
         "text": "hello"
       }
     }]
   }
   ```

记下这个数字。**群组的 chat_id 是负数**（比如 `-1001234567890`）。

### 1.5 烟雾测试（可选但强烈推荐）

继续之前，把这个 URL 粘到浏览器（两个占位符都换）：

```
https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=Hello%20from%20setup
```

如果一切正确，你手机收到 "Hello from setup" 消息。如果报错，两个值都核对一遍。

---

## Part 1.6 — 把凭证存到本地 `.env`

在 push 任何东西到 GitHub 之前，把凭证存到本地 `.env` 文件 —— 这个文件**永远不会被 commit**。

```bash
cd ~/.claude/skills/price-alert
cp .env.example .env
# 用编辑器（nano、vim、VSCode 等）打开 .env，粘贴：
#   TELEGRAM_BOT_TOKEN=<你的真实 token>
#   TELEGRAM_CHAT_ID=<你的真实 chat_id>
```

Repo 根目录的 `.gitignore` 已经排除了 `.env` —— `git status` 不会显示它。**任何 commit 之前确认**：

```bash
git -C ~/.claude/skills status --short | grep -i "\.env"
# 期望输出: 没东西（或只有 .env.example，那个可以 commit）
```

如果不小心看到 `.env` 被 staged，**立刻停下**，从 staging 移除。

### 既然 GitHub Actions 不读 .env，为什么还要它？

| 场景 | 凭证从哪来 |
|---|---|
| **本地测试**（在你电脑上跑 `python check_alerts.py`） | 自动读 `.env` |
| **GitHub Actions cron**（实际生产路径） | 读 repo Secrets（Part 2 设置） |

`.env` 只是给**你电脑**用 —— push live cron 之前测试脚本用的。

### ⚠️ 万一 token 泄露了

如果你的 token 出现在 `.env` 之外的任何地方（截图、聊天、repo、剪贴板、任何地方），它就**已经不安全**：

1. 打开 @BotFather → `/mybots` → 选你的 bot → **API Token** → **Revoke current token**
2. BotFather 给你新 token
3. 同时更新 `.env` 和 GitHub Secrets 的新值
4. 旧 token 立刻失效 —— 不需要其他操作

---

## Part 2 — 把凭证加到 GitHub Secrets（2 分钟）

GitHub Actions 需要知道你的 token + chat_id。**绝对不能写到代码里** —— 用 repo secrets。

### 2.1 打开 repo 的 Secrets 页

把 `YOUR_USERNAME` 换成你的 GitHub 用户名：

```
https://github.com/YOUR_USERNAME/claude-investment-skills/settings/secrets/actions
```

（或者点：GitHub repo → Settings → Secrets and variables → Actions）

### 2.2 加两个 secrets

点 **New repository secret** 两次，分别加：

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 给你的 token（比如 `7234567890:AAH-xxx...`） |
| `TELEGRAM_CHAT_ID` | `/getUpdates` 拿到的 chat id（比如 `987654321`） |

存了之后 secrets 显示为 `***` —— 连你自己都读不出来（只能改或删）。GitHub Actions runner 跑的时候才会注入。

---

## Part 3 — 手动测试 workflow（1 分钟）

不要等 cron，立即验证能跑通。

### 3.1 手动触发 workflow

打开：
```
https://github.com/YOUR_USERNAME/claude-investment-skills/actions/workflows/price-alerts.yml
```

点 **Run workflow** → **Run workflow**（绿色按钮）。

任务 ~10 秒后开始。点进去看日志。

如果 `alerts.json` 是空的，你会看到：
```
Checking 0 active alerts at 2026-05-10T...
Summary: 0 fired, 0 skipped, 0 not triggered
```

绿勾 ✅ —— 配置正确，只是还没东西监控。

### 3.2 强制触发一次（端到端验证 Telegram）

设一个保证会触发的 alert：

```bash
cd ~/.claude/skills
/tmp/.insider_venv/bin/python price-alert/scripts/add_alert.py SPY below 99999 \
    --note "烟雾测试 — 应该立刻触发"

git add price-alert/alerts.json
git commit -m "test: smoke-test alert (delete after)"
git push
```

再点 **Run workflow**。~30 秒内你的 Telegram 应该收到：

```
🔻 PRICE ALERT: SPY
Current: $737.62
Trigger: $737.62 ≤ $99999.00
...
```

确认 Telegram 通了后，清理：

```bash
/tmp/.insider_venv/bin/python price-alert/scripts/cancel_alert.py --all
git add price-alert/alerts.json
git commit -m "test: clean up smoke-test alert"
git push
```

---

## Part 4 — 加真正的 alerts

直接跟 Claude 说：

```
你: 通知我 GLW 跌到 $140，写个 note "AI 玻璃 tier 1"
你: NVDA 跌 10% 提醒我
你: 盯一下 SMH，从现在跌 5% 通知
```

Claude 自动调脚本、commit、push。下个 cron tick 就开始监控。

查列表：
```
你: 列出我的 active alerts
```

取消：
```
你: 取消 GLW 的 alert
你: 取消所有 alerts
```

---

## Cron 怎么定的

`.github/workflows/price-alerts.yml`:

```yaml
on:
  schedule:
    - cron: '*/15 13-21 * * 1-5'   # 每 15 分钟，13-21 UTC，工作日
  workflow_dispatch:               # 手动触发按钮
```

翻译:
- **每 15 分钟一次**，仅美股交易时段（早 9am–下午 5pm ET，周一到周五）
- **手动触发**任何时候都可以（Actions 标签页）

**为什么这个时间窗？** 盘前 ~4am ET 开始但成交量稀薄、价格抖动；盘后会有新闻反应但大部分 alert 关心的是常规交易时段水位。9am–5pm ET 这个窗口覆盖核心 + 噪声最小。

改 cron：
- `*/5 13-21 * * 1-5`  → 每 5 分钟（更频繁，但更耗 GitHub Actions 配额）
- `0 14,18,21 * * 1-5` → 一天 3 次（开盘、午盘、收盘）
- `*/30 * * * *`       → 每 30 分钟，24/7（适合加密货币）

---

## 费用

**免费。**

| 资源 | 配额 | 我们用量 |
|---|---|---|
| GitHub Actions（免费 public repo）| 2,000 分钟/月 | 每 15 分钟 cron ≈ 50 分钟/月 |
| Telegram API | 消息无限 | 一周几条 |
| yfinance | 限速但不计费 | 远低于任何上限 |

如果 repo 设成 private，GitHub Actions 免费配额是 2,000 分钟/月。public 无上限。

---

## 故障排查 —— 真实 setup 中遇到的坑

这些都是第一次走完整流程时遇到的真问题。任何一步崩了就来这里查。

### 🐛 #1 `getUpdates` 返回 `{"ok": true, "result": []}` —— 最常见

**原因**: 你的 bot 还没收到过任何消息。Telegram 的 `getUpdates` 只返回**发给 bot 的最近消息**，所以 bot 一条消息都没收到时 result 数组就是空的。

**现象**:
```json
{"ok": true, "result": []}
```

**修复**（30 秒）:
1. 打开 Telegram → 搜索**你的 bot username**（比如 `@DuckyduckyTradeBot`）
2. 点进 bot，**点蓝色 START 按钮**（或者发 `/start`）
3. **再发任意一条消息**（比如 `hello`）
4. **刷新** `getUpdates` URL —— 现在 result 应该有内容了

**为什么这一步坑人**: Telegram 文档默认你已经在跟 bot 聊天。第一次 setup 时根本没东西可拿。

---

### 🐛 #2 `chat.id` vs `from.id` 容易搞混

JSON 返回里有**两个** `id` 字段：

```json
"message": {
  "from": {"id": 1435438296, ...},   ← 发送者的 user_id
  "chat": {"id": 1435438296, ...}    ← chat_id ← 用这个
}
```

**私聊**它俩相等。**群聊/频道**它俩不同 —— `from.id` 是发送者，`chat.id` 是 bot 所在聊天。

**规则**: 永远用 `chat.id`。任何聊天类型都是正确答案。

**群聊**: `chat.id` 是**负数**（比如 `-1001234567890`）。负号是值的一部分，**别漏掉**。

---

### 🐛 #3 不小心泄露了 token？

Token 可能通过截图、聊天、终端 scrollback、git commit、剪贴板等泄露。如果它出现在 `.env` + GitHub Secrets 之外的任何地方：

1. Telegram → @BotFather → `/mybots` → 选你的 bot → **API Token** → **Revoke current token**
2. BotFather 立刻给你新 token，旧的瞬间失效
3. 同时更新本地 `.env` **和** GitHub repo Secrets

**预防规则**:
- 永远不要把 token 粘到任何聊天里（包括 AI 聊天 —— 对话可能被 export）
- 永远不要截图 BotFather 的 token 区域；万一截图了，立刻 revoke
- 每次 commit 前 `git status`，确认 `.env` 不在列表里
- `git -C ~/.claude/skills check-ignore -v price-alert/.env` 应该返回 `.gitignore` 行 —— 这确认 gitignore 工作中

---

### 🐛 #4 `.env` vs `.env.example` —— 哪个 commit？

| 文件 | 状态 | 内容 |
|---|---|---|
| `.env.example` | ✅ **committed** 到 git | 模板，含 `PASTE_YOUR_TOKEN_HERE` 占位符 |
| `.env` | ❌ **gitignored**, 永不 commit | 你的真实 token + chat_id |

工作流:
```bash
cp .env.example .env       # 一次性: 复制模板
# 编辑 .env 填真实值
# .env 现在被忽略 —— git status 不会显示
```

验证已被忽略:
```bash
git -C ~/.claude/skills check-ignore -v price-alert/.env
# 期望: ".gitignore:35:.env\tprice-alert/.env"
```

如果 `check-ignore` 没输出，或 `git status` 把它显示为 untracked，**就是有问题** —— commit 前先修 gitignore。

---

### 🐛 #5 Workflow 报错 "TELEGRAM_BOT_TOKEN not set"

脚本跑了但找不到 Telegram 凭证。两条路径：

- **本地跑**: `.env` 文件缺失或位置错。应该在 `price-alert/.env`（跟 `SKILL.md` 同级）
- **GitHub Actions 跑**: Repo Secrets 没加或名字错。名字必须**精确**为 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`（大小写敏感、没前后空格）

本地快速验证:
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

### 🐛 #6 Telegram 报 "chat not found"

两种可能：

1. **chat_id 错** —— 重做上面的 `getUpdates` 流程；精确复制 `chat.id` 值（群聊保留负号）
2. **你没点过 bot 的 Start** —— 即使 chat_id 对，bot 也不能主动发起对话。必须用户先开启聊天

浏览器 URL 烟雾测试:
```
https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=test
```
返回 `{"ok":true,...}` → 正常。返回 `{"ok":false,"description":"chat not found"}` → 按上面修。

---

### 🐛 #7 其他 workflow 误动作

| 现象 | 解决 |
|---|---|
| Workflow 跑了但没 Telegram 消息 | 先用上面 URL 烟雾测试 —— 隔离是 bot 凭证问题还是 check_alerts.py 问题 |
| Cron 没按时跑 | GitHub 高峰时段可能延迟 ~15 分钟，看 Actions log 时间戳 |
| Alert 触发了但状态卡死 | 设计如此 —— `python cancel_alert.py <id> --rearm` 重置 |
| `add_alert.py` 成功但 Actions 没识别 | 你忘了跑完 add_alert.py 后 commit + push `alerts.json` |

---

## 架构图

```
你 ──"GLW 140 通知我"──→ Claude
                          │
                          ▼
               add_alert.py → alerts.json
                          │
                          ▼
                   git commit + push
                          │
                          ▼
            ┌─────GitHub Actions cron─────┐
            │  美股交易时段每 15 分钟       │
            │                             │
            │  python check_alerts.py     │
            │   1. 读 alerts.json         │
            │   2. yfinance 拉价格         │
            │   3. 评估条件                │
            │   4. POST Telegram bot API  │
            │   5. 标 fired=true          │
            │   6. commit alerts.json     │
            └──────────────┬──────────────┘
                           │
                           ▼
                📱 Telegram 推送通知
```

**没有服务器。没有付费服务。不需要电脑开机。**

---

## 分享给朋友

朋友想用：
1. Fork 或 clone 你的 repo
2. 在他自己的 GitHub + Telegram 上跑一遍 Part 1-3
3. 他的 alerts 跟你的隔离 —— 每个 fork 独立的 `alerts.json`

Bot token + chat_id 都在他自己的 GitHub Secrets 里，永远不进代码。
