# Claude 投资分析 Skills 系统

> Claude Code 的投资分析自动化系统。
> Top-Down 框架：宏观 → 年度主题 → 板块 → 个股 → 入场点位 → 仓位。
> 价值 + 期权 + 宏观感知三合一，支持中英文自然语言触发。

[English Version](./README.md)

## 🤖 给 AI agent / CLI 用户

如果你是 AI agent（Claude Code、自定义 agent、定时器）或在做 CLI 包装，**先读 [`AGENT-TOOL-REFERENCE.md`](./AGENT-TOOL-REFERENCE.md)**。它包含：
- 每个工具的中英文自然语言触发短语
- 精确的 CLI 模板和参数说明
- 用户话术 → 命令的映射例子
- 多工具组合调用的 pattern

`INVESTMENT-WORKFLOW.md` 告诉你**用哪个 skill**。`AGENT-TOOL-REFERENCE.md` 告诉你**精确怎么调用脚本**。

---

## ⚡ 一键开始（3 分钟）

```bash
# 1. Clone 这个 repo 到 ~/.claude/skills/
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git ~/.claude/skills

# 2. 跑 setup 脚本
bash ~/.claude/skills/setup.sh

# 3. 在 Claude Code 里试试
/analyze-stock NVDA
```

---

## 🎯 这是什么

10 个专业 skills 组成的投资分析系统，给你**基金经理级别**的分析：

| Skill | 用途 | 触发关键词 |
|-------|------|----------|
| `analyze-stock` | 10 步深度分析任何股票 | "analyze X"、"X 是不是 buy"、"深度分析" |
| `macro-risk-check` | 每日宏观风险扫描 | "宏观看一下"、"市场状态" |
| `find-untapped-thesis` | NOK 类未爆发筛选 | "找下一个 NOK"、"X 板块未爆发" |
| `earnings-prep` | 财报前决策框架 | "X 财报怎么处理"、"该持有还是减仓" |
| `leaps-screen` | LEAPS 长期期权选择 | "X 买什么 LEAPS"、"现货还是 LEAPS" |
| `option-wall-analysis` | 最大痛点 + 期权墙 | "X 的 max pain"、"option walls" |
| `tax-optimize` | LTCG vs STCG 决策 | "X 减仓税务"、"什么时候卖" |
| `portfolio-audit` | 完整组合风险审计 | "审一下我的组合"、"减什么仓" |
| `narrative-reversal-screen` | ORCL 风格反转筛选 | "找 ORCL 那种"、"暴跌反转" |
| `sector-rotation-analysis` | 板块热力图 + 轮动 | "板块轮动"、"该买哪个板块" |

加上已有的：
- `review-investment-screenshot` — 截图组合速读
- `find-alpha` — 时间分级 alpha
- `schedule` — 远程定时 agent

---

## 📦 安装步骤

### 前置依赖

| 依赖 | 版本 | 安装 |
|------|------|------|
| **Claude Code** | 最新版 | https://docs.claude.com/claude-code/install |
| **Python** | 3.9+ | `brew install python3` (macOS) |
| **Git** | 任何版本 | `brew install git` |

### 必需的 MCP Servers

#### 1. yfmcp（YFinance MCP）— 必装
提供股票实时数据、期权链、新闻。

```bash
# 通过 Claude Code 安装
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp

# 或者查最新安装命令：
# https://github.com/...yfmcp
```

#### 2. WebSearch — 内置
Claude Code 已包含。用于宏观事件、新闻、合同验证。

### 可选 MCP Servers（claude.ai connectors）

| Server | 用途 | 怎么装 |
|--------|------|------|
| Notion | 把分析存到笔记 | https://claude.ai/customize/connectors |
| Gmail | 读财报会议纪要 | 同上 |
| Google Calendar | 自动设置财报提醒 | 同上 |
| Google Drive | 引用投资文档 | 同上 |

### 完整安装步骤

```bash
# 1. 装 Claude Code（如果还没装）
# 看 https://docs.claude.com/claude-code/install

# 2. 装 yfmcp MCP server
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp

# 3. Clone 这个 repo
cd ~/.claude/skills
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git .

# 4. 跑 setup
bash setup.sh

# 5. 验证
ls ~/.claude/skills/
# 应该看到: analyze-stock, macro-risk-check 等等

# 6. 测试
# 打开 Claude Code，输入：
/analyze-stock NVDA
```

---

## 🛠 目录结构

```
~/.claude/skills/
├── setup.sh                            # 一键安装脚本
├── INVESTMENT-WORKFLOW.md              # 主决策树
├── README.md                           # 英文文档
├── README-zh.md                        # 这个文件（中文）
│
├── analyze-stock/SKILL.md              # 10 步主框架
├── macro-risk-check/SKILL.md           # 每日宏观雷达
├── find-untapped-thesis/SKILL.md       # NOK 风格筛选
├── earnings-prep/SKILL.md              # 财报前分析
├── leaps-screen/SKILL.md               # LEAPS 选择
├── option-wall-analysis/SKILL.md       # Max pain + 期权墙
├── tax-optimize/SKILL.md               # LTCG/STCG 计算
├── portfolio-audit/SKILL.md            # 组合风险审计
├── narrative-reversal-screen/SKILL.md  # ORCL 风格反转
├── sector-rotation-analysis/SKILL.md   # 板块热力图
│
└── review-investment-screenshot/       # （已有）
    └── scripts/
        ├── insider_ratio.py            # v3：openinsider 主源，Form 4 code 感知，按时间分桶
        ├── cluster_buy_scan.py         # 新：扫描 openinsider /latest-cluster-buys 找 cluster 信号
        ├── quote_pull.py               # 批量实时报价
        ├── option_walls.py             # OI 集中 strikes
        └── max_pain.py                 # Max pain 计算
```

---

## 🎓 核心理念

Top-Down 宏观感知投资框架，5 大核心原则：

1. **AI = 工厂模式**，不是软件收税。Hyperscalers 像工厂买机器一样买算力。
2. **K 型分化**：板块内部赢家碾压输家。挑赢家。
3. **瓶颈环节升值**：被约束的供给环节（电力、燃料、材料）会重估。
4. **需求毁灭风险窗口**：定期监控油价、通胀、地缘政治信号。
5. **Carry trade 结构**：BOJ 政策能触发全球风险偏好级联反应。

加上纪律性原则：
- 永远查 insider trading（用 `insider_ratio.py`，不要相信 yfinance summary）
- 加仓前先看宏观（regime > 个股）
- 三档入场计划（不要"市价买入"）
- 仓位上限（单股 max 10%，高 beta max 5%）
- 现金就是 alpha（危险区 40-50%）

---

## 🚀 常用工作流

### 工作流 1：「该不该买 NVDA？」
```
1. /macro-risk-check          # 当前 regime 安全吗？
2. /analyze-stock NVDA        # 10 步深度分析
3. /option-wall-analysis NVDA # 短期价位
4. /leaps-screen NVDA         # 看看 LEAPS（如果入场点合适）
```

### 工作流 2：「该不该减仓？」
```
1. /macro-risk-check          # 看 regime
2. /portfolio-audit           # 完整审计（提供持仓）
3. /tax-optimize NOK 1000     # 每个减仓项查税
```

### 工作流 3：「AMD 明天财报怎么办？」
```
1. /earnings-prep AMD         # Implied move + 4 种情景
2. /option-wall-analysis AMD  # 锚定到哪儿
3. /tax-optimize AMD 350      # 如果减仓查税
```

### 工作流 4：「找好想法」
```
1. /macro-risk-check          # 避免坏时机
2. /find-untapped-thesis "AI Power"  # 筛选
3. /narrative-reversal-screen        # 反转标的
4. /analyze-stock [TOP_PICK]         # 深度分析头部赢家
```

---

## 📅 推荐定时任务

通过 `/schedule` skill 设置：

| 频率 | Skill | 何时 |
|------|-------|------|
| 每周一早 8 点 ET | `macro-risk-check` | 盘前 regime 读取 |
| 每周五下午 4 点 ET | `find-untapped-thesis` | 找下周想法 |
| 每月 1 日 | `portfolio-audit` | 完整组合审计 |
| 重大事件前 24h | `macro-risk-check` | Fed/BOJ/重大财报前 |
| 季度 | `tax-optimize` | 年末规划 |

---

## 🔧 后台脚本

| 脚本 | 用途 | 用法 |
|------|------|------|
| `insider_ratio.py` (v3) | 严格开放市场 insider $ 比，openinsider 主源，按 Form 4 code 过滤（只算 P）| `python insider_ratio.py NVDA --window 90` |
| `cluster_buy_scan.py` | 扫描 openinsider 找市场全局 cluster buy | `python cluster_buy_scan.py --days 30 --min-value 500000 --min-insiders 3 --detail --enrich --senior-only` |
| `max_pain.py` | 按到期日的 max pain | `python max_pain.py NVDA 4` |
| `option_walls.py` | OI 集中 strikes | `python option_walls.py NVDA 4` |
| `quote_pull.py` | 批量实时报价 | `python quote_pull.py "A,B,C"` |

所有脚本使用 `/tmp/.insider_venv`（由 `setup.sh` 创建）。

### Insider 数据源（按可信度排序）
1. **openinsider.com/screener?s=TICKER** — 主源。Form 4 with codes（P=买入, S=卖出, A=授予, M=行权, F=税务, G=赠予）。免费，无需登录。
2. **secform4.com** — 备份。看 10b5-1 计划脚注。
3. **stocktitan.net SEC filings** — 可读 Form 4 描述。
4. **yfinance** — fallback。已知盲区（漏掉 NKE/UNH/PLTR 真实 cluster buy）。

---

## ⚠️ 硬性规则（不能违反）

1. **永远跑 `insider_ratio.py --window 90`**（openinsider 主源）— 不要信 yfinance 的「净买入」（把 RSU 算成买入）
2. **Form 4 code 只有 "P" 算买入** — A/M/F/G 是 RSU/行权/税务/赠予，**不是**买入信号。已验证假阳性：UNH "10 directors 4/1/2026"（全是 DSU 季度补偿）、PLTR "Karp 1.47M 股"（RSU 归属）
3. **任何 "cluster buy" 标题都要在 openinsider.com/[TICKER] 验证** — 媒体经常把补偿当成 conviction
4. **卖出要查 10b5-1**（在 secform4.com 看脚注）— 计划性 trust 卖出告诉你的不是当前观点
5. **加仓前先看宏观** — 再好的股在 red regime 里也跌
6. **仓位上限**：单股 max 10%，高 beta max 5%
7. **三档入场**：永远不要「市价买入」，必须有 50DMA / 200DMA 备份
8. **Concrete 证据 > 故事**：「AI 好」≠ 投资逻辑
9. **引用源**：每个宏观说法要带 WebSearch 链接
10. **税务感知出场**：特别是高收入者

---

## 🐛 故障排查

### 「yfmcp not found」
```bash
claude mcp list  # 看看装了哪些
claude mcp add yfmcp -- npx -y @modelcontextprotocol/yfmcp
```

### 「Python venv 不工作」
```bash
rm -rf /tmp/.insider_venv
bash ~/.claude/skills/setup.sh
```

### 「yfinance: ModuleNotFoundError」
```bash
/tmp/.insider_venv/bin/pip install --upgrade yfinance pandas numpy
```

### 「Skills 在 Claude Code 里不显示」
- 重启 Claude Code
- 确认 SKILL.md 的 frontmatter 有 `name:` 和 `description:`
- 检查权限：`chmod -R 755 ~/.claude/skills/`

---

## 📚 进一步学习

- **主决策树**：[INVESTMENT-WORKFLOW.md](./INVESTMENT-WORKFLOW.md)
- **每个 skill 细节**：`[skill-name]/SKILL.md`
- **宏观年度框架**：见 `analyze-stock/SKILL.md` 年度主题部分
- **Insider 方法论**：见 `review-investment-screenshot/SKILL.md`（已有）

---

## 🤝 给朋友分享

```bash
# 朋友只需要跑：
git clone https://github.com/YOUR_USERNAME/claude-investment-skills.git ~/.claude/skills
bash ~/.claude/skills/setup.sh

# 完事。他们就有了你完整的投资思维系统。
```

---

## ⚖️ 免责声明

这些 skills 是**个人投资研究的工具**。**不是金融建议**。历史业绩不代表未来。实际投资决策请咨询持牌金融顾问。

这个框架有特定风格（top-down、价值导向、宏观感知、期权友好）。**不适合**：
- 日内交易
- 纯量化策略
- 纯加密组合
- 外汇交易

---

## 📜 致谢

- **框架灵感**：Buffett（安全边际）+ Druckenmiller（宏观转折）+ Stan Weinstein（趋势阶段）
- **构建工具**：Anthropic 的 Claude Code

---

**版本**：1.0
**最后更新**：2026-05-04
