# WorkBuddy 开发记录

本文件说明麦门点单诸葛亮的开发环境与过程摘要。

**完整对话记录见同目录 `workbuddy-conversation.md`**，该文件由 WorkBuddy 会话存储直接导出，包含 72 条对话消息与 92 次工具调用记录，可核验项目确实使用腾讯 WorkBuddy 智能体开发。

## 开发环境

| 项目 | 内容 |
|---|---|
| 开发工具 | 腾讯 WorkBuddy |
| 专家 | 技能匠人（Skill Smith） |
| 使用技能 | `skill-crafting`（Skill 制作顾问） |
| MCP Server | `mcd-mcp`，地址 `https://mcp.mcd.cn` |
| 开发日期 | 2026-10-10 |

## 开发过程

### 阶段一：需求梳理与选题

初仅有模糊想法。经分析活动规则，明确以下关键判断：

- 比赛排名**仅看 GitHub Star 数**，无评委打分，技术质量不直接决定成绩
- 同一 GitHub 账号仅Star 最高的项目能进入排行榜，因此只做一个项目
- 推广渠道为微信群与朋友圈，缺少开发者流量池，需选题兼顾传播性

基于此选定"多人聚餐点单优化"场景，理由是痛点强度高、工具链完整、结果可验证为具体金额。

### 阶段二：MCP 能力实测

开发过程中逐一核实工具实际行为，纠正了初稿中的多处错误：

| 核实项 | 结果 |
|---|---|
| `now-time-info` | 连通正常，返回服务器时间 |
| `list-nutrition-foods` | 返回 160 条餐品营养数据 |
| `query-nearby-stores` | 郑州航空港区返回 5 家门店，含 `storeCode` 与 `distance` |
| `query-meals` | 门店 `3560129` 返回 100+ 在售品项，含现价与原价双字段 |
| `query-store-coupons` | 未绑定账号时返回空数组，属正常情况 |
| `query-nutrition-detail` | **该工具不存在**，实际只有 `list-nutrition-foods` |
| `query-meal-assistance` | 团餐场景算价前必须调用，取`gmServiceCode` |
| `query-promotions` | 门店满减规则，**仅 `beType=6` 可用** |
| `calculate-price` | `items` 参数结构存在歧义，见下方已知问题 |

四条链路的参数组合经实测确认：

| 场景 | beType | orderType | beCode |
|---|---|---|---|
| 到店自取 | 1 | 1 | 不传 |
| 麦乐送到家 | 2 | 2 | 必传 |
| 得来速 | 5 | 1 | 必传 |
| 企业团餐 | 6 | 2 | 必传 |

实测确认 `beType=1` 传入 `beCode` 会报错。

### 阶段三：Skill 生成与自检

使用 WorkBuddy 内置脚本完成确定性操作：

- `render` 生成完整 Skill 包（未使用占位模板）
- `validate` 结构校验通过，无问题项
- `preflight` 静态预检通过，2 项medium 风险均为环境检查器的 `urllib` 网络模块导入，属该脚本预期功能，无 high 风险

### 阶段四：环境检查器实测

在隔离临时目录执行，无网络、无真实凭据：

| 场景 | 返回 | 退出码 |
|---|---|---|
| 配置齐全加探测证据 | `ready`，跳过配置引导 | 0 |
| Token 失效 | `unavailable`，联动六项功能降级规则 | 1 |
| 请求未声明功能 | 拦截并报错 | 2 |
| capability 路由隔离 | 按请求返回对应能力 | 0 |

## 已知问题

### `calculate-price` 参数结构歧义

实测中该工具的 `items` 参数在单层数组与嵌套数组两种形态下均返回：

```
Parameter validation failed for tool "mcp__mcd-mcp__calculate-price": /items: must be array
```

MCP Server 声明的 schema 中 `items` 为数组但未定义内层元素类型。

**处理方式**：优先调用该工具；若持续校验失败，改用 `query-meals` 的 `currentPrice` 字段自行累加，并在输出中标注"价格未经工具验算"。不因工具故障编造优惠金额。

## 未覆盖范围

- 未完成真实外送/团餐链路的端到端验证（需用户提供配送地址与门店授权）
- 微信支付与外卖平台比价不在范围内
- 团餐助餐服务（`query-meal-assistance`）的实际返回结构未实测

## 产出

```text
mcd-party-planner/
├── SKILL.md
├── skill-dependencies.json
├── scripts/check_environment.py
└── references/
    ├── mcp-call-flow.md
    ├── optimization-rules.md
    └── setup-guide.md
```

参赛文件：

```text
├── README.md
├── MCP_INTEGRATION.md
├── mcp-config.example.json
├── workbuddy.md                    本文件，开发过程摘要
└── workbuddy-conversation.md       WorkBuddy 会话原始导出
```

`CONTEST_DECLARATION.md` 由官方仓库直接获取，内容未作任何改动。

## 会话记录导出方式

`workbuddy-conversation.md` 由以下方式生成：

1. WorkBuddy 会话按项目存储在 `~/.workbuddy/projects/<项目路径>/<会话ID>.jsonl`
2. 逐行解析 JSONL，按 `type` 字段区分 `message`、`function_call`、`function_call_result`
3. `message` 记录取 `role` 与 `content`，其中 `content` 为内容块数组（`input_text` / `output_text` / `tool_use` / `tool_result`）
4. `function_call` 记录取 `name` 与 `arguments`，保留工具名与调用参数
5. `function_call_result` 记录取 `output`，保留工具返回结果
6. 过滤内部注入的系统提示词标签，仅保留用户真实输入与助手输出
7. 时间戳为毫秒级整数，转换为本地时间字符串

也可在 WorkBuddy 界面直接导出：对话区右上角提供整轮对话导出为 Markdown / JSON，输入 `/export` 可下载当前会话归档。
