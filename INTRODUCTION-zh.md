# 介绍 — 这是个什么 Repo？

> 5 分钟读完，看看这个东西是不是给你用的。

[English Version](./INTRODUCTION.md)

---

## 这是什么

一套给 [Claude Code](https://docs.claude.com/claude-code)（Anthropic 官方 AI 编程助手）用的**投资分析 skills**。装上之后，你用大白话（中文或英文）跟 Claude 说话，它就能拉实时市场数据、深度分析个股、筛选投资标的、做财报前准备、审计你的组合 —— 全部用基金经理级的纪律。

它**不是交易机器人**。它是个**思考伙伴**：拉实时数据、跑系统化框架、给你有观点的判断 —— 帮你**更快做出更好的决策**。

---

## 你能问它什么

不用记命令，直接说话就行。几个真实例子：

```
你: "分析一下 NVDA"
→ Claude 拉 NVDA 的宏观环境、估值、内部交易、催化剂，给你 3 档入场计划
  + LEAPS 期权建议。

你: "宏观警报"
→ Claude 扫 8 层指标（NDX P/E、VIX、F&G、信用利差、宽度、日元套息、
  板块轮动、CTA 流），给出 regime 标签 + 具体仓位建议。

你: "审一下我的组合"（贴张截图）
→ Claude 算单股集中度、风格因子暴露、对冲有效性，给你减仓清单
  （含 $ 数额 + 理由）。

你: "AMD 财报前怎么看"
→ Claude 拉 implied move、过去 8 季度反应、4 个情景，给你
  hold/trim/hedge 建议（针对你的仓位定制）。

你: "find untapped AI Power names"（英文：找未爆发的 AI 电力股）
→ Claude 筛 forward P/E 低 + 1 年涨幅落后 + 具体催化剂 + 机构持仓低，
  返回 top 3 候选。
```

系统**中英文都懂**，对话中可以随时切换。

---

## 为什么有这个东西

市面上的投资 AI 工具大致两个极端：

1. **全自主机器人** — 黑箱、过度自信、经常出错、难以审计
2. **通用聊天机器人** — 答案肤浅、数字幻觉、没有实时数据

这个 repo 走中间路径：

- **实时数据**，不是训练数据 —— 每个回答都从 yfinance / FRED / openinsider 实时拉取
- **关键路径上确定性 Python**（内部交易分析、宏观评分）—— 可审计、可测试、可复现
- **有观点的框架**，把昂贵的教训编进了规则（内部交易规则来自真实的踩坑，宏观阈值来自真实的周期）
- **Top-Down 纪律** —— 宏观先于个股、regime 先于加仓、估值先于动量
- **天生双语** —— 每个触发短语都有中英文双版本

---

## 13 个 Skills（一句话简介）

| Skill | 干什么 |
|---|---|
| `analyze-stock` | 10 步深度分析任何美股 |
| `macro-risk-check` | 新闻驱动的每日宏观扫描（VIX、收益率、USDJPY） |
| `macro-warning` | 8 层批量模式顶部预警（CAPE、F&G、宽度、板块） |
| `find-alpha` | 每周 3 时间维度筛选（swing / position / LEAPS） |
| `find-untapped-thesis` | "下一个 NOK" 筛选 —— 主题内未爆发的低估标的 |
| `narrative-reversal-screen` | 跌透但故事还在的标的，找底部 |
| `sector-rotation-analysis` | 11 板块热力图 + 轮动配对 |
| `earnings-prep` | 财报前：implied move、情景、hold/trim/hedge 决策 |
| `leaps-screen` | 长期期权选行权价 + 收益率数学 |
| `option-wall-analysis` | Max pain + gamma 墙（短期支撑阻力） |
| `portfolio-audit` | 集中度/因子/期权 Greeks/压力测试 |
| `tax-optimize` | LTCG vs STCG 决策（含州税逻辑） |
| `review-investment-screenshot` | 截图组合速读 |
| `price-alert` | 参数化价格 alert，GitHub Actions + Telegram 推送（任何标的、任何阈值/百分比）。一次性 bot 设置见 [SETUP-zh.md](./price-alert/SETUP-zh.md) |

加上底层共享脚本：
- `insider_ratio.py` — Form 4 代码感知的内部交易分析
- `cluster_buy_scan.py` — 全市场 cluster buy 扫描
- `macro_pull.py` — 直接 API 宏观指标拉取
- `max_pain.py`、`option_walls.py`、`quote_pull.py` — 期权工具

---

## 安装（3 分钟）

需要：macOS 或 Linux、Python 3.9+、已装 [Claude Code](https://docs.claude.com/claude-code/install)。

```bash
# 1. Clone 到 Claude Code 的 skills 目录
git clone https://github.com/ssurmic/claude-investment-skills.git ~/.claude/skills

# 2. 跑 setup（建 Python venv，装 yfinance，验证一切）
bash ~/.claude/skills/setup.sh

# 3. 跟 Claude 聊
# 打开 Claude Code，直接说：
分析一下 NVDA
```

完事。setup 脚本会验证所有 13 个 skills + 工具脚本都在位。

---

## 自然语言 → Skill 的"魔法"

你**不需要**打 slash 命令。直接说话就行。原理：

1. **每个 skill 的 `description:` 字段**列了触发短语（中英文都有）。
2. **Claude Code 会拿你的输入**去匹配所有 skill descriptions，挑最匹配的。
3. **匹配上的 skill 加载完整 instructions** 并执行（拉数据、跑分析、返回答案）。

比如 `macro-warning` skill 的描述里写了：
```
Triggers in English ("macro warning", "regime check", "is the market at peak",
"should I take profits", "is it time to buy") or Chinese ("宏观警报",
"市场是不是顶了", "该不该减仓", "regime 怎么样", "该入场吗")
```

所以**这些任意一种说法**都会触发同一个 skill。你不必记精确措辞。**接近就行**，太模糊 Claude 会反问。

**组合短语**也行：
- "我想在财报前买 AMD，宏观安全吗？" → 依次触发 `macro-risk-check` + `earnings-prep`。

完整映射在 [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md)。

---

## 这个 repo **不是**什么

- ❌ 交易机器人 —— 永远不下单
- ❌ 投资建议 —— 是研究工具
- ❌ 回测引擎 —— 主打实时研究，不是历史模拟
- ❌ 加密货币导向 —— 为美股 + ETF + 期权设计
- ❌ 日内交易 —— 设计给 swing / position / LEAPS 时间维度
- ❌ 黑箱 —— 每个数字都有 source URL

---

## 接下来去哪

按角色挑文档：

- **散户 / 普通用户** → 继续读 [`README-zh.md`](./README-zh.md) 看 example prompts 和 workflow
- **AI agent / CLI 集成者** → 读 [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md) 看精确 CLI contract
- **Skill 开发者** → 读 [`ARCHITECTURE.md`](./ARCHITECTURE.md) 看架构决策和数据源选择理由
- **想知道"该用哪个 skill"** → 读 [`INVESTMENT-WORKFLOW.md`](./INVESTMENT-WORKFLOW.md) 的决策树
- **每个 skill 的具体逻辑** → 读那个 skill 自己的 `SKILL.md`

---

## 免责声明

这些工具是给**个人投资研究**用的。**不构成投资建议**。过往业绩不代表未来表现。实际投资决策请咨询持牌财务顾问。

框架是有观点的 —— 反映一种特定风格（top-down、估值感知、宏观敏感、期权友好）。**不适合**：日内交易、纯量化策略、纯加密货币组合、外汇交易。
