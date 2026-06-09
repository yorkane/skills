---
name: n8n
description: A consolidated Chinese-localized n8n workflow building subagent. Use when working with n8n, n8n-mcp tools, or n8n workflows — building, validating, configuring nodes, writing expressions, writing Code (JavaScript), designing workflow patterns, interpreting validation errors, debugging, or any n8n-related task. Combines 6 specialized sub-skills: n8n Expression Syntax, n8n MCP Tools Expert, n8n Workflow Patterns, n8n Validation Expert, n8n Node Configuration, and n8n Code JavaScript. Always consult this skill first when the user mentions n8n, workflows, nodes, n8n-mcp, webhook, HTTP API, or workflow automation.
---

## 全局原则(必读)

创建或修改 workflow 时,**始终**遵循以下原则:

1. **从 manual trigger 开始**: 创建 workflow 时,始终以 **manual trigger** 节点开始,验证通过后再添加其他触发器。
2. **先验证再扩展**: 始终测试 workflow,保证 manual trigger 先验证通过,再测试其他 trigger,确保 workflow 可以正确执行。
3. **Code 节点用 JavaScript**: 始终使用 JavaScript 编写 Code 节点代码(95% 场景最佳,Python 限制更多)。
4. **执行时间控制**: 等待 workflow 执行时间通常**不要超过 15 秒**;超此阈值的 workflow 应考虑拆分或异步化。
5. **优先查本 subagent**: 使用本 subagent 时,**优先从入口 SKILL.md 开始**,再按需进入下方 6 大分项。
6. 手动执行workflow, 并确认最后的结果没有错误，并符合预期才标志着这个 workflow 已经完成。

---

## 环境准备

### 连接 N8N(从 .env 读取凭证)

```bash
source ./.env && curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" "${N8N_API_URL}/api/v1/workflows"
```

### 关键环境变量

| 变量 | 用途 |
|------|------|
| `N8N_API_URL` | n8n 实例 API 地址(如 `http://192.168.1.31:3009`) |
| `N8N_API_KEY` | n8n API 密钥(在 n8n 设置中生成) |

---

## 6 个分项 SKILL 索引

本 subagent 由以下 6 个专项 SKILL 组成,根据任务场景选择:

### 1. n8n Expression Syntax(表达式语法)

**触发场景**: 编写 n8n 表达式、使用 `{{}}` 语法、访问 `$json`/`$node` 变量、排查表达式错误、跨节点映射数据、引用 webhook 数据。

**关键资源**:

- [SKILL.md](skills/n8n-expression-syntax/SKILL.md) - 表达式完整指南
- [COMMON_MISTAKES.md](skills/n8n-expression-syntax/COMMON_MISTAKES.md) - 15 类常见错误
- [EXAMPLES.md](skills/n8n-expression-syntax/EXAMPLES.md) - 10 个真实示例

**最常见用法**:

```javascript
// 访问当前节点数据
{{$json.fieldName}}

// 引用其他节点
{{$node["HTTP Request"].json.data}}

// Webhook 数据(在 .body 下!)
{{$json.body.email}}

// 环境变量
{{$env.API_KEY}}
```

**绝对不能忘**:
- 表达式必须用 `{{ }}` 包裹
- **Webhook 数据在 `$json.body` 下**(不在根!)
- **Code 节点中不用 `{{ }}`**,直接 `$json.field`
- 含空格的节点名要用引号:`$node["HTTP Request"]`
- 节点名**区分大小写**

---

### 2. n8n MCP Tools Expert(MCP 工具专家)

**触发场景**: 搜索节点、校验配置、访问模板、管理 workflow、管理凭据、审计实例安全,或使用任何 n8n-mcp 工具。

**关键资源**:

- [SKILL.md](skills/n8n-mcp-tools-expert/SKILL.md) - MCP 工具总览
- [SEARCH_GUIDE.md](skills/n8n-mcp-tools-expert/SEARCH_GUIDE.md) - 节点发现
- [VALIDATION_GUIDE.md](skills/n8n-mcp-tools-expert/VALIDATION_GUIDE.md) - 校验工具
- [WORKFLOW_GUIDE.md](skills/n8n-mcp-tools-expert/WORKFLOW_GUIDE.md) - Workflow 管理

**最常用工具**:

| 工具 | 用途 |
|------|------|
| `search_nodes` | 按关键字查找节点 |
| `get_node` | 了解节点配置(默认 standard detail) |
| `validate_node` | 校验配置(profile="runtime") |
| `n8n_create_workflow` | 创建 workflow |
| `n8n_update_partial_workflow` | 增量编辑(最常用!) |
| `n8n_validate_workflow` | 校验完整 workflow |
| `n8n_autofix_workflow` | 自动修复 |

**nodeType 格式(关键!)**:

- 搜索/校验工具: `nodes-base.slack`(短前缀)
- Workflow 工具: `n8n-nodes-base.slack`(完整前缀)

---

### 3. n8n Workflow Patterns(Workflow 模式)

**触发场景**: 构建新 workflow、设计 workflow 结构、选择 workflow 模式、规划 workflow 架构、连接服务、自动化流程。

**关键资源**:

- [SKILL.md](skills/n8n-workflow-patterns/SKILL.md) - 6 大模式总览
- [webhook_processing.md](skills/n8n-workflow-patterns/webhook_processing.md) - Webhook 处理
- [http_api_integration.md](skills/n8n-workflow-patterns/http_api_integration.md) - HTTP API 集成
- [database_operations.md](skills/n8n-workflow-patterns/database_operations.md) - 数据库操作
- [ai_agent_workflow.md](skills/n8n-workflow-patterns/ai_agent_workflow.md) - AI Agent
- [scheduled_tasks.md](skills/n8n-workflow-patterns/scheduled_tasks.md) - 定时任务

**6 大核心模式**:

1. **Webhook 处理**(最常用): `Webhook → 校验 → 转换 → 响应/通知`
2. **HTTP API 集成**: `触发器 → HTTP Request → 转换 → 动作 → 错误处理`
3. **数据库操作**: `定时 → 查询 → 转换 → 写入 → 验证`
4. **AI Agent**: `触发器 → AI Agent(模型 + 工具 + 记忆)→ 输出`
5. **定时任务**: `定时 → 拉取 → 处理 → 投递 → 日志`
6. **批处理**: `准备 → SplitInBatches → 逐批处理 → 累积 → 聚合`

**模式选择**: 根据触发方式(即时/周期)与数据源(外部 API/数据库/AI)选择对应模式。

---

### 4. n8n Validation Expert(校验专家)

**触发场景**: 遇到校验错误、校验警告、误报、operator 结构问题,或需要解读校验结果。

**关键资源**:

- [SKILL.md](skills/n8n-validation-expert/SKILL.md) - 校验总览
- [ERROR_CATALOG.md](skills/n8n-validation-expert/ERROR_CATALOG.md) - 9 类错误完整目录
- [FALSE_POSITIVES.md](skills/n8n-validation-expert/FALSE_POSITIVES.md) - 6 类常见误报

**校验 Profile**:

- `minimal` - 仅必填字段(快速)
- `runtime` - 值 + 类型(**推荐,部署前用**)
- `ai-friendly` - 减少误报(AI 配置用)
- `strict` - 最大校验强度(生产)

**校验循环**: 校验 → 读错误 → 修复 → 再次校验(通常 2-3 轮,平均 23s 思考 + 58s 修复)

**关键规则**:

- 错误**必须修复**,警告可选
- **自动清洗**自动修复 operator 结构
- 用 `runtime` profile 做平衡校验
- 误报存在 —— 学会识别

---

### 5. n8n Node Configuration(节点配置)

**触发场景**: 配置节点、理解属性依赖、确定必填字段、在 `get_node` 的 detail 级别间选择、学习常见配置模式。

**关键资源**:

- [SKILL.md](skills/n8n-node-configuration/SKILL.md) - 节点配置总览
- [DEPENDENCIES.md](skills/n8n-node-configuration/DEPENDENCIES.md) - 属性依赖与 displayOptions
- [OPERATION_PATTERNS.md](skills/n8n-node-configuration/OPERATION_PATTERNS.md) - 11 个常见节点配置

**核心概念**:

- **Operation 感知**: 不同 operation = 不同必填字段
- **属性依赖**: `displayOptions` 控制字段可见性(`sendBody=true` 时才显示 `body`)
- **渐进式披露**: 从 `get_node` 默认 standard detail 开始

**`get_node` detail 选择**:

1. `standard`(默认,~1-2K tokens) - **95% 场景**
2. `mode: "search_properties"` - 查找特定字段
3. `detail: "full"`(~3-8K tokens) - 仅复杂调试

---

### 6. n8n Code JavaScript(JavaScript Code 节点)

**触发场景**: 写 JavaScript Code 节点、使用 `$input`/`$json`/`$node`、用 `$helpers` 发 HTTP 请求、用 DateTime 处理日期、排查 Code 节点错误、聚合/过滤/批处理。

**关键资源**:

- [SKILL.md](skills/n8n-code-javascript/SKILL.md) - Code 节点总览
- [DATA_ACCESS.md](skills/n8n-code-javascript/DATA_ACCESS.md) - 4 种数据访问模式
- [COMMON_PATTERNS.md](skills/n8n-code-javascript/COMMON_PATTERNS.md) - 10 个生产验证模式
- [ERROR_PATTERNS.md](skills/n8n-code-javascript/ERROR_PATTERNS.md) - 7 类错误防范
- [BUILTIN_FUNCTIONS.md](skills/n8n-code-javascript/BUILTIN_FUNCTIONS.md) - 内置函数参考

**核心规则**:

1. **Mode 选择**: 默认 "Run Once for All Items"(95% 场景)
2. **数据访问**: `$input.all()`(批处理)、`$input.first()`(单对象)、`$input.item`(Each Item 模式)
3. **返回格式**: **必须** `[{json: {...}}]` 数组形式
4. **Webhook 数据**: 在 `$json.body` 下(不是 `$json`!)
5. **内置函数**: `$helpers.httpRequest()`、DateTime(Luxon)、`$jmespath()`、`$getWorkflowStaticData()`

**最常见错误(占 90%)**:

1. 缺 return 语句
2. 在 Code 节点中用 `{{ }}`(应直接 `$json.field`)
3. 返回格式错(必须 `[{json: ...}]`)
4. Webhook 数据漏 `.body`
5. 缺空值检查(应用 `?.` 与 `||`)

---

## SKILL 协同工作流

典型场景:**"构建并验证 webhook → Slack workflow"**

1. **n8n Workflow Patterns**: 识别为 webhook 处理模式,打开 [webhook_processing.md](skills/n8n-workflow-patterns/webhook_processing.md)
2. **n8n MCP Tools Expert**: 用 `search_nodes({query: "slack"})` 找 Slack 节点;`search_nodes({query: "webhook"})` 找 Webhook 节点
3. **n8n Node Configuration**: 用 `get_node({nodeType: "nodes-base.slack"})` 查 slack 配置;用 `get_node({nodeType: "nodes-base.webhook"})` 查 webhook 配置
4. **n8n Expression Syntax**: 在 Slack 节点的 text 字段中,用 `{{$json.body.message}}`(注意 `.body`!)
5. **n8n Code JavaScript**: 若需在 Code 节点中处理 webhook 数据,用 `$json.body` 访问,返回 `[{json: {...}}]`
6. **n8n Validation Expert**: 用 `validate_node({profile: "runtime"})` 校验每个节点;用 `n8n_validate_workflow` 校验整体

---

## 通用工作流(从零构建)

### 1. 规划阶段

- [ ] 确定模式(webhook、API、数据库、AI、定时)
- [ ] 列出所需节点(用 `search_nodes`)
- [ ] 理解数据流(输入 → 转换 → 输出)
- [ ] 规划错误处理策略

### 2. 实现阶段(从 manual trigger 开始!)

- [ ] 创建 workflow,以 **manual trigger** 为第一个节点
- [ ] 测试 manual trigger 验证通过
- [ ] 添加数据源节点
- [ ] 配置凭据
- [ ] 添加转换节点(Set、Code、IF)
- [ ] 添加输出/动作节点
- [ ] 配置错误处理

### 3. 校验阶段

- [ ] `validate_node({profile: "runtime"})` 校验每个节点
- [ ] `n8n_validate_workflow` 校验整体
- [ ] 用样本数据测试
- [ ] 处理边界情况(空数据、错误)

### 4. 部署阶段

- [ ] 用 `activateWorkflow` 操作激活
- [ ] 监控首次执行
- [ ] 记录 workflow 用途与数据流

---

## 快速参考:关键陷阱

### 🚨 Webhook 数据结构

```javascript
// 永远记住!
{{$json.name}}         // ❌ 错(返回 undefined)
{{$json.body.name}}    // ✅ 正确
```

### 🚨 节点引用格式

```javascript
// 永远记住!
{{$node.HTTP Request.json}}    // ❌ 错(语法错误)
{{$node["HTTP Request"].json}} // ✅ 正确(用引号 + 中括号)
```

### 🚨 Code 节点返回格式

```javascript
// 永远记住!
return {json: {result: 'ok'}}  // ❌ 错(无数组)
return [{json: {result: 'ok'}}] // ✅ 正确(数组包裹)
```

### 🚨 nodeType 格式

```javascript
// 搜索/校验工具用短前缀
"nodes-base.slack"

// Workflow 工具用完整前缀
"n8n-nodes-base.slack"
```

### 🚨 节点名区分大小写

```javascript
{{$node["http request"].json}}  // ❌ 错
{{$node["HTTP Request"].json}}  // ✅ 正确
```

---

## 文档导航

### 按主题

| 主题 | 关键资源 |
|------|---------|
| 表达式与语法 | [n8n-expression-syntax/SKILL.md](skills/n8n-expression-syntax/SKILL.md) |
| MCP 工具 | [n8n-mcp-tools-expert/SKILL.md](skills/n8n-mcp-tools-expert/SKILL.md) |
| Code 节点 | [n8n-code-javascript/SKILL.md](skills/n8n-code-javascript/SKILL.md) |
| 节点配置 | [n8n-node-configuration/SKILL.md](skills/n8n-node-configuration/SKILL.md) |
| 校验 | [n8n-validation-expert/SKILL.md](skills/n8n-validation-expert/SKILL.md) |
| Workflow 模式 | [n8n-workflow-patterns/SKILL.md](skills/n8n-workflow-patterns/SKILL.md) |

### 按场景

| 我想... | 查... |
|--------|------|
| 写 n8n 表达式 | [n8n-expression-syntax/SKILL.md](skills/n8n-expression-syntax/SKILL.md) |
| 找合适的节点 | [n8n-mcp-tools-expert/SEARCH_GUIDE.md](skills/n8n-mcp-tools-expert/SEARCH_GUIDE.md) |
| 配置节点 | [n8n-node-configuration/SKILL.md](skills/n8n-node-configuration/SKILL.md) |
| 写 Code 节点 | [n8n-code-javascript/SKILL.md](skills/n8n-code-javascript/SKILL.md) |
| 校验 workflow | [n8n-validation-expert/SKILL.md](skills/n8n-validation-expert/SKILL.md) |
| 设计 workflow 模式 | [n8n-workflow-patterns/SKILL.md](skills/n8n-workflow-patterns/SKILL.md) |
| 修校验错误 | [n8n-validation-expert/ERROR_CATALOG.md](skills/n8n-validation-expert/ERROR_CATALOG.md) |
| 用 HTTP API | [n8n-workflow-patterns/http_api_integration.md](skills/n8n-workflow-patterns/http_api_integration.md) |
| 处理 webhook | [n8n-workflow-patterns/webhook_processing.md](skills/n8n-workflow-patterns/webhook_processing.md) |
| 用数据库 | [n8n-workflow-patterns/database_operations.md](skills/n8n-workflow-patterns/database_operations.md) |
| 构 AI agent | [n8n-workflow-patterns/ai_agent_workflow.md](skills/n8n-workflow-patterns/ai_agent_workflow.md) |
| 定时任务 | [n8n-workflow-patterns/scheduled_tasks.md](skills/n8n-workflow-patterns/scheduled_tasks.md) |

---

## 附录

### 英文原版对照

完整的英文原版保留在 [`_en_appendix/`](_en_appendix/) 目录,便于对照查阅。

```
_en_appendix/
├── n8n-code-javascript/    # 英文原版
├── n8n-expression-syntax/  # 英文原版
├── n8n-mcp-tools-expert/   # 英文原版
├── n8n-node-configuration/ # 英文原版
├── n8n-validation-expert/  # 英文原版
└── n8n-workflow-patterns/  # 英文原版
```

---

## 小结

**使用步骤**:

1. 收到 n8n 相关任务 → 查阅本 SKILL.md
2. 按"6 个分项 SKILL 索引"找到最相关的子能力
3. 按"文档导航"查具体资源
4. 按"SKILL 协同工作流"组合使用
5. 遵循"全局原则"与"通用工作流"
6. 涉及 **E-Hentai / ExHentai** 集成 → 直接看 [`_ehentai_api/`](_ehentai_api/)
7. 遇到 Loop / SplitInBatches 异常 → 看"关键陷阱"清单

**记住**:

- Webhook 数据在 `.body` 下
- Code 节点不用 `{{ }}`,直接 `$json.field`
- Code 节点返回必须是 `[{json: {...}}]`
- 节点名区分大小写,含空格用引号
- Loop 内只有 1 个下游节点反馈
- Code 批处理用 `runOnceForAllItems`
- HTTP 用原生节点,不用 `$helpers.httpRequest`


---

## 关键陷阱（实战总结 2026-06）

### 🚨 SplitInBatches 输出方向

```jsonc
// ✅ 正确: main[0] = done, main[1] = each batch
"Split In Batches": {
  "main": [
    [],                                           // done
    [{"node": "...", "type": "main", "index": 0}] // each batch
  ]
}
```

### 🚨 Loop 反馈次数

**多个下游节点同时反馈回 SplitInBatches 会导致循环次数翻倍 + 批次错位**。

```
// ❌ 错: 2 个 Postgres 都反馈回 SplitInBatches
Parse → ┬─→ [Insert A] ─┐
        └─→ [Insert B] ─┴─→ SplitInBatches   // 反馈 2 次

// ✅ 对: 用 CTE 合并为 1 个节点
Parse → [Insert A & B (CTE)] → SplitInBatches  // 反馈 1 次
```

### 🚨 Code 节点 mode

批处理场景必须显式 `mode: "runOnceForAllItems"`，否则 25 个 item 跑 25 次。

### 🚨 $helpers.httpRequest 不可靠

**优先用原生 `n8n-nodes-base.httpRequest` 节点**，不要在 Code 节点中 `await $helpers.httpRequest()`。

### 🚨 split_part URL token 提取

```sql
-- ❌ 末尾 / 导致段位偏移
split_part(url, '/', 5)  -- 返回 gid 不是 token

-- ✅ 先 rtrim 末尾的 /，再取第 6 段
split_part(rtrim(url, '/'), '/', 6)
```

### 🚨 n8n settings 白名单

```json
// ❌ 报错: additional properties not allowed
{"executionOrder": "v1", "binaryMode": "separate", "saveDataErrorExecution": "all"}

// ✅ 允许的子集
{"executionOrder": "v1", "callerPolicy": "workflowsFromSameOwner"}
```

### 🚨 仅 manualTrigger 无法激活

n8n 不允许仅含 `manualTrigger` 的工作流 `active: true`。需要 `active: false` + UI 手动执行，或添加 Webhook/Schedule 节点。

---

## 领域 API 集成

### E-Hentai / ExHentai

当任务涉及 **E-Hentai 数据采集**（gallery 元数据、torrent、tags）时,优先查阅：

- [**`_ehentai_api/SKILL.md`**](_ehentai_api/SKILL.md) - 完整 API 参考（gdata / gtoken / 字段 / 限流 / 错误处理）
- [**`_ehentai_api/LESSONS.md`**](_ehentai_api/LESSONS.md) - n8n 集成踩坑经验（SplitInBatches / Loop / CTE / token 提取）

**适用场景**:
- 从 `eh_preview` 表中拉取 URL 并解析元数据
- 把 E-Hentai gallery 元数据落库到 `eh_page` + `eh_torrent`
- 任何 `POST https://e-hentai.org/api.php` 的 gdata 调用

**生产案例**: workflow `AoGawzvkWxvIh0pl`（`eh_preview 最新50条 API`），4 批次 × 25 条 = 100 URL/轮，~6-8s 跑完，147 torrents/100 pages 写入，0 errors。
