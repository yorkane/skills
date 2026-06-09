# Workflow 管理工具指南

创建、更新、管理 n8n workflow 的完整指南。

---

## 工具可用性

**需要 n8n API**: 本指南中的所有工具都需要配置 `N8N_API_URL` 和 `N8N_API_KEY`。

若不可用,可使用模板示例与仅校验 workflow。

---

## n8n_create_workflow

**速度**: 100-500ms

**适用**: 从零创建新 workflow

**语法**:

```javascript
n8n_create_workflow({
  name: "Webhook to Slack",  // 必填
  nodes: [...],              // 必填: 节点数组
  connections: {...},        // 必填: 连接对象
  settings: {...}            // 可选: workflow 设置
})
```

**返回**: 含 ID 的已创建 workflow

**示例**:

```javascript
n8n_create_workflow({
  name: "Webhook to Slack",
  nodes: [
    {
      id: "webhook-1",
      name: "Webhook",
      type: "n8n-nodes-base.webhook",  // 完整前缀!
      typeVersion: 2,
      position: [250, 300],
      parameters: {
        path: "slack-notify",
        httpMethod: "POST"
      }
    },
    {
      id: "slack-1",
      name: "Slack",
      type: "n8n-nodes-base.slack",
      typeVersion: 2,
      position: [450, 300],
      parameters: {
        resource: "message",
        operation: "post",
        channel: "#general",
        text: "={{$json.body.message}}"
      }
    }
  ],
  connections: {
    "Webhook": {
      "main": [[{node: "Slack", type: "main", index: 0}]]
    }
  }
})
```

**注意**:

- Workflow 创建时为**未激活**(用 `activateWorkflow` 操作激活)
- 创建时运行自动清洗
- 创建前校验以获得最佳结果

---

## n8n_update_partial_workflow(最常用!)

**速度**: 50-200ms | **使用次数**: 38,287(最常用工具!)

**适用**: 对 workflow 做增量修改

**常见模式**: 编辑间隔平均 56s(迭代构建!)

### 19 种操作类型

**节点操作**(7 种):

1. `addNode` - 添加新节点
2. `removeNode` - 按 ID 或名字移除节点
3. `updateNode` - 更新节点属性(用点号语法)
4. `patchNodeField` - 通过严格的 find/replace 做定点字符串编辑(见下)
5. `moveNode` - 改变位置
6. `enableNode` - 启用已禁用节点
7. `disableNode` - 禁用启用中的节点

**连接操作**(5 种):

8. `addConnection` - 连接节点(支持智能参数)
9. `removeConnection` - 移除连接(支持 ignoreErrors)
10. `rewireConnection` - 改变连接目标
11. `cleanStaleConnections` - 自动移除断开的连接
12. `replaceConnections` - 替换整个连接对象

**元数据操作**(4 种):

13. `updateSettings` - workflow 设置
14. `updateName` - 重命名 workflow
15. `addTag` - 添加标签
16. `removeTag` - 移除标签

**激活操作**(2 种):

17. `activateWorkflow` - 激活 workflow 以自动执行
18. `deactivateWorkflow` - 停用 workflow

**项目管理操作**(1 种):

19. `transferWorkflow` - 将 workflow 转移到其他项目(企业/云)

### Intent 参数(重要!)

始终携带 `intent` 以获得更好的响应:

```javascript
n8n_update_partial_workflow({
  id: "workflow-id",
  intent: "为 API 失败添加错误处理",  // 描述你在做什么
  operations: [...]
})
```

### 智能参数

**IF 节点** —— 用语义化分支名:

```javascript
{
  type: "addConnection",
  source: "IF",
  target: "True Handler",
  branch: "true"  // 代替 sourceIndex: 0
}

{
  type: "addConnection",
  source: "IF",
  target: "False Handler",
  branch: "false"  // 代替 sourceIndex: 1
}
```

**Switch 节点** —— 用语义化 case 编号:

```javascript
{
  type: "addConnection",
  source: "Switch",
  target: "Handler A",
  case: 0
}

{
  type: "addConnection",
  source: "Switch",
  target: "Handler B",
  case: 1
}
```

### AI 连接类型(8 种)

**全面支持** AI workflow:

```javascript
// Language Model
{
  type: "addConnection",
  source: "OpenAI Chat Model",
  target: "AI Agent",
  sourceOutput: "ai_languageModel"
}

// Tool
{
  type: "addConnection",
  source: "HTTP Request Tool",
  target: "AI Agent",
  sourceOutput: "ai_tool"
}

// Memory
{
  type: "addConnection",
  source: "Window Buffer Memory",
  target: "AI Agent",
  sourceOutput: "ai_memory"
}

// 全部 8 种:
// - ai_languageModel
// - ai_tool
// - ai_memory
// - ai_outputParser
// - ai_embedding
// - ai_vectorStore
// - ai_document
// - ai_textSplitter
```

### 用 null 删除属性

把属性设为 `null` 以删除:

```javascript
// 删除属性
{
  type: "updateNode",
  nodeName: "HTTP Request",
  updates: { onError: null }
}

// 从废弃属性迁移
{
  type: "updateNode",
  nodeName: "HTTP Request",
  updates: {
    continueOnFail: null,  // 移除旧的
    onError: "continueErrorOutput"  // 添加新的
  }
}
```

### patchNodeField(定点字符串编辑)

对字符串字段用 `patchNodeField` 做严格的 find/replace 编辑 —— 代码、HTML、邮件模板、JSON body。与 `updateNode` + `__patch_find_replace`(未命中会静默警告)不同,`patchNodeField` 是严格的:未找到 find 字符串会报错,匹配多次也会报错(防止歧义替换)。

**何时用哪个**:

- `patchNodeField` —— 多数字符串编辑的首选。严格的错误处理能尽早捕获错误。
- `updateNode` + `__patch_find_replace` —— 旧式做法。宽容(未命中警告但继续)。仅在需要宽容行为时使用。

**语法**:

```javascript
{
  type: "patchNodeField",
  nodeName: "Code",           // 或 nodeId
  fieldPath: "parameters.jsCode",  // 点号路径到字符串字段
  patches: [
    {
      find: "const limit = 10;",
      replace: "const limit = 50;",
      replaceAll: false,       // 默认: false。设为 true 替换所有出现
      regex: false             // 默认: false。设为 true 把 find 当作正则
    }
  ]
}
```

**示例**:

```javascript
// 代码中基础的严格 find/replace
n8n_update_partial_workflow({
  id: "wf-123",
  intent: "更新 API 限制",
  operations: [{
    type: "patchNodeField",
    nodeName: "Code",
    fieldPath: "parameters.jsCode",
    patches: [{find: "const limit = 10;", replace: "const limit = 50;"}]
  }]
})

// 替换 URL 的所有出现
n8n_update_partial_workflow({
  id: "wf-123",
  intent: "迁移 API 域名",
  operations: [{
    type: "patchNodeField",
    nodeName: "Code",
    fieldPath: "parameters.jsCode",
    patches: [{find: "api.old.com", replace: "api.new.com", replaceAll: true}]
  }]
})

// 基于正则的替换(忽略空白)
n8n_update_partial_workflow({
  id: "wf-123",
  intent: "用正则更新 limit",
  operations: [{
    type: "patchNodeField",
    nodeName: "Code",
    fieldPath: "parameters.jsCode",
    patches: [{find: "const\\s+limit\\s*=\\s*\\d+", replace: "const limit = 100", regex: true}]
  }]
})

// 邮件模板上的多个顺序 patch
n8n_update_partial_workflow({
  id: "wf-123",
  intent: "更新邮件页脚",
  operations: [{
    type: "patchNodeField",
    nodeName: "Set Email",
    fieldPath: "parameters.assignments.assignments.6.value",
    patches: [
      {find: "© 2025", replace: "© 2026"},
      {find: "<p>Unsubscribe</p>", replace: ""}
    ]
  }]
})
```

**错误行为**(这就是严格的来源):

- **未找到 find 字符串** → 操作失败并报错(不是静默警告)
- **多次匹配但未设 `replaceAll`** → 操作失败(检测到歧义)
- Patch 顺序应用 —— 顺序很重要

**安全限制**:

- 每操作最多 50 个 patch
- 正则模式上限 500 字符
- 正则仅作用于 512KB 以下的字段
- ReDoS 安全: 拒绝嵌套量词如 `(a+)+` 和重叠分支如 `(\w|\d)+`
- field path 的原型污染防护

### 激活操作

```javascript
// 激活 workflow
n8n_update_partial_workflow({
  id: "workflow-id",
  intent: "为生产激活 workflow",
  operations: [{type: "activateWorkflow"}]
})

// 停用 workflow
n8n_update_partial_workflow({
  id: "workflow-id",
  intent: "为维护停用 workflow",
  operations: [{type: "deactivateWorkflow"}]
})
```

### 使用示例

```javascript
n8n_update_partial_workflow({
  id: "workflow-id",
  intent: "在 IF 条件后添加 transform 节点",
  operations: [
    // 添加节点
    {
      type: "addNode",
      node: {
        name: "Transform",
        type: "n8n-nodes-base.set",
        position: [400, 300],
        parameters: {}
      }
    },
    // 连接它(智能参数)
    {
      type: "addConnection",
      source: "IF",
      target: "Transform",
      branch: "true"  // 清晰且语义化!
    }
  ]
})
```

### 清理与恢复

**cleanStaleConnections** —— 移除断开的连接:

```javascript
{type: "cleanStaleConnections"}
```

**rewireConnection** —— 原子化改变目标:

```javascript
{
  type: "rewireConnection",
  source: "Webhook",
  from: "Old Handler",
  to: "New Handler"
}
```

**尽力模式** —— 应用能成功的部分:

```javascript
n8n_update_partial_workflow({
  id: "workflow-id",
  operations: [...],
  continueOnError: true  // 部分失败不阻断
})
```

**应用前校验**:

```javascript
n8n_update_partial_workflow({
  id: "workflow-id",
  operations: [...],
  validateOnly: true  // 预览而不应用
})
```

---

## n8n_deploy_template(快速起步!)

**速度**: 200-500ms

**适用**: 直接部署模板到 n8n 实例

```javascript
n8n_deploy_template({
  templateId: 2947,  // 必填: 来自 n8n.io
  name: "My Weather to Slack",  // 可选: 自定义名称
  autoFix: true,  // 默认: 自动修复常见问题
  autoUpgradeVersions: true,  // 默认: 升级节点版本
  stripCredentials: true  // 默认: 移除凭据引用
})
```

**返回**:

- Workflow ID
- 所需凭据
- 已应用的修复

**示例**:

```javascript
// 部署 webhook 到 Slack 模板
const result = n8n_deploy_template({
  templateId: 2947,
  name: "Production Slack Notifier"
});

// 结果包含:
// - id: "new-workflow-id"
// - requiredCredentials: ["slack"]
// - fixesApplied: ["typeVersion upgraded", "expression format fixed"]
```

---

## n8n_generate_workflow(自然语言 → workflow)

**速度**: 提案约 2s,全新生成 5–15s,部署约 3s

**适用**: 用户用自然英语描述 workflow,希望系统起草(并可选部署)

> ⚠️ **仅 hosted 功能。** 自托管实例上,工具返回 `{hosted_only: true}` 与重定向消息,而不是 workflow。自托管请用 `n8n_deploy_template`(模板)或 `n8n_create_workflow`(手动)。

### 工作原理

**带审核检查点的多步流程** —— 提案/预览先返回,部署需要第二次调用。这避免部署低质量草稿。

### 路径 A:提案 → 部署(默认,推荐)

```javascript
// Step 1: 生成提案(不部署,返回最多 5 个候选)
n8n_generate_workflow({
  description: "Slack daily standup reminder at 9am every weekday"
})
// → {
//     status: "proposals",
//     proposals: [
//       {
//         id: "uuid-1",
//         name: "Daily Standup Reminder",
//         description: "...",
//         flow_summary: "Schedule trigger → Slack message",
//         credentials_needed: ["slackApi"]
//       },
//       ...
//     ]
//   }

// Step 2: 部署你选中的提案
n8n_generate_workflow({
  description: "Slack daily standup reminder at 9am every weekday",
  deploy_id: "uuid-1"
})
// → { status: "deployed", workflow_id, workflow_name, workflow_url,
//     node_count, node_summary }
```

### 路径 B:跳过缓存 → 预览 → 确认

当提案都不符合需求时使用。

```javascript
// Step 1: 绕过提案;获取全新预览(不部署)
n8n_generate_workflow({
  description: "Webhook receives JSON, transforms it, POSTs to a REST API",
  skip_cache: true
})
// → { status: "preview", ... }

// Step 2: 部署预览
n8n_generate_workflow({
  description: "Webhook receives JSON, transforms it, POSTs to a REST API",
  confirm_deploy: true
})
// → { status: "deployed", ... }
```

### 写好描述

生成 workflow 的质量取决于描述的清晰度。始终包含:

- **触发器类型**: `webhook`、`schedule`(带周期 —— "每 15 分钟"、"工作日 9 点")、`manual`、`form`、`chat`
- **涉及的服务**: 显式命名(Slack、Gmail、HubSpot、Postgres 等)—— 通用术语("某个聊天工具")会产生通用结果
- **逻辑/流程**: 分支、转换、聚合、去重、重试行为

**差**: `"当某事发生时发送通知"`

**好**: `"当 'leads' Postgres 表新增一行时,用 Clearbit 富化,然后向 #sales Slack 频道发送摘要。跳过 'company' 为空的行。"`

### 参数

| 参数 | 类型 | 用途 |
|-----------|------|-----|
| `description` | string(必填) | 自然语言描述 |
| `deploy_id` | string | 上次调用返回的提案 ID —— 部署它 |
| `skip_cache` | boolean | 跳过提案;从零生成并返回预览 |
| `confirm_deploy` | boolean | 部署本会话中最近的预览 |

### 常见陷阱

- **仅 hosted** —— 自托管上不会生成 workflow;回退到 `n8n_deploy_template` 或 `n8n_create_workflow`
- **提案不部署** —— 除非再次用 `deploy_id` 或 `confirm_deploy` 调用,否则 n8n 中不存在
- **部署时未激活** —— 生成的 workflow 创建时为**未激活**状态;激活前需在 n8n UI 中配置凭据
- **per-session 状态** —— 待处理提案/预览存于 MCP session 状态;重连会丢失,需要重新发描述

### 推荐的后续操作

部署后始终校验:

```javascript
n8n_generate_workflow({description: "...", deploy_id: "uuid-1"})
// → workflow_id: "abc"

n8n_validate_workflow({id: "abc"})
// → 捕获生成器遗漏的节点版本或连接问题

// 若发现问题,n8n_autofix_workflow 可以解决常见问题
n8n_autofix_workflow({id: "abc", applyFixes: true})
```

---

## n8n_workflow_versions(版本控制)

**适用**: 管理 workflow 历史、回滚、清理

### 列出版本

```javascript
n8n_workflow_versions({
  mode: "list",
  workflowId: "workflow-id",
  limit: 10
})
```

### 获取特定版本

```javascript
n8n_workflow_versions({
  mode: "get",
  versionId: 123
})
```

### 回滚到之前的版本

```javascript
n8n_workflow_versions({
  mode: "rollback",
  workflowId: "workflow-id",
  versionId: 123,  // 可选: 特定版本
  validateBefore: true  // 默认: 回滚前校验
})
```

### 删除版本

```javascript
// 删除特定版本
n8n_workflow_versions({
  mode: "delete",
  workflowId: "workflow-id",
  versionId: 123
})

// 删除 workflow 的所有版本
n8n_workflow_versions({
  mode: "delete",
  workflowId: "workflow-id",
  deleteAll: true
})
```

### 清理旧版本

```javascript
n8n_workflow_versions({
  mode: "prune",
  workflowId: "workflow-id",
  maxVersions: 10  // 保留最近 10 个
})
```

---

## n8n_test_workflow(触发执行)

**适用**: 测试 workflow 执行

**自动检测** 触发器类型(webhook、form、chat)

```javascript
// 测试 webhook workflow
n8n_test_workflow({
  workflowId: "workflow-id",
  triggerType: "webhook",  // 可选: 自动检测
  httpMethod: "POST",
  data: {message: "Hello!"},
  waitForResponse: true,
  timeout: 120000
})

// 测试 chat workflow
n8n_test_workflow({
  workflowId: "workflow-id",
  triggerType: "chat",
  message: "Hello, AI agent!",
  sessionId: "session-123"  // 用于对话连续性
})
```

---

## n8n_manage_credentials(凭据管理)

**速度**: 50-500ms

**适用**: 创建、更新、列出、删除凭据;发现凭据 schema

### 6 种 Actions

1. `list` - 列出所有凭据(id、name、type、时间戳)
2. `get` - 按 ID 获取凭据(data 字段被剥离)
3. `create` - 创建凭据(需要 name、type、data)
4. `update` - 按 ID 更新凭据(name、data、和/或 type)
5. `delete` - 永久删除凭据
6. `getSchema` - 发现凭据类型的必填字段

`list` 和 `get` 也接受可选的 `includeUsage: true` 标志,会给每个凭据附加 workflow 使用信息(见下"查找哪些 workflow 使用了某凭据")。

### 列出凭据

```javascript
n8n_manage_credentials({action: "list"})
// → [{id, name, type, createdAt, updatedAt}, ...]
```

### 获取凭据

```javascript
n8n_manage_credentials({action: "get", id: "123"})
// → {id, name, type, ...}(data 字段因安全被剥离)
// 若 GET 返回 403/405 则回退到 list+filter
```

### 查找哪些 Workflow 使用了某凭据

n8n 公开 API 没有原生的"哪些 workflow 用了凭据 X"端点,所以 n8n-mcp 通过客户端扫描 workflow 为你构建反向索引。给 `list` 或 `get` 传 `includeUsage: true` 即可。

```javascript
// 每个凭据,带引用它的 workflow
n8n_manage_credentials({action: "list", includeUsage: true})
// → {
//     credentials: [
//       {
//         id: "123",
//         name: "Production Slack",
//         type: "slackApi",
//         createdAt: "...", updatedAt: "...",
//         usedIn: [
//           {id: "wf_abc", name: "Daily digest",  active: true},
//           {id: "wf_xyz", name: "Alert fan-out", active: false}
//         ],
//         usageCount: 2
//       },
//       ...
//     ],
//     count: N,
//     // usageScanError: "..."  // 仅在 workflow 扫描失败时出现
//   }

// 单个凭据,带其 workflow 引用
n8n_manage_credentials({action: "get", id: "123", includeUsage: true})
// → 与 `get` 同样的结构,加 usedIn 和 usageCount。
//   扫描失败时:响应设置 usageScanError 并省略 usedIn/usageCount。
```

**何时使用**:

- `delete` 之前:确认没有任何引用
- 用 `update` 轮换 secret 之前:查看会影响的 workflow
- `n8n_audit_instance` 标记凭据后:定位需要修复的 workflow

**行为与限制**:

- 反向索引客户端构建,按 workflow 去重,上限 5000 个 workflow(同 `n8n_audit_instance`)
- 归档的 workflow 被 n8n API 排除 —— "无 usage" 结果**不**证明凭据未被使用;销毁性操作前请验证
- 每次调用触发一次全量 workflow 扫描。大实例上响应比基础 ~50–500ms 慢,反复调用时需要预算时间
- 扫描失败时,响应降级为基础凭据并附 `usageScanError` 字段,而不是整个调用失败
- 默认行为不变:省略该标志不会触发额外 API 调用

### 发现 Schema

```javascript
n8n_manage_credentials({
  action: "getSchema",
  type: "httpHeaderAuth"
})
// → 该凭据类型的必填字段、类型、说明
```

### 创建凭据

```javascript
n8n_manage_credentials({
  action: "create",
  name: "My Slack Token",
  type: "slackApi",
  data: {accessToken: "xoxb-your-token"}
})
// → 创建的凭据(data 字段从响应中剥离)
```

### 更新凭据

```javascript
n8n_manage_credentials({
  action: "update",
  id: "123",
  name: "Updated Slack Token",
  data: {accessToken: "xoxb-new-token"},
  type: "slackApi"  // 可选,部分 n8n 版本需要
})
// → 更新的凭据(data 字段从响应中剥离)
```

### 删除凭据

```javascript
n8n_manage_credentials({action: "delete", id: "123"})
```

### 典型工作流:为新集成设置凭据

```javascript
// 1. 发现需要哪些字段
n8n_manage_credentials({
  action: "getSchema",
  type: "slackApi"
})

// 2. 创建凭据
n8n_manage_credentials({
  action: "create",
  name: "Production Slack",
  type: "slackApi",
  data: {accessToken: "xoxb-..."}
})

// 3. 验证已创建
n8n_manage_credentials({action: "list"})
```

### 典型工作流:安全地删除或轮换凭据

```javascript
// 1. 查看会影响什么
n8n_manage_credentials({action: "get", id: "123", includeUsage: true})
// → 检查 usedIn —— 引用它的每个 workflow 的 {id, name, active}

// 2a. 若无依赖,删除
n8n_manage_credentials({action: "delete", id: "123"})

// 2b. 若有依赖,改为轮换 secret 并通知负责人
n8n_manage_credentials({
  action: "update",
  id: "123",
  data: {accessToken: "xoxb-new-..."}
})
```

### 安全说明

- **响应剥离**: `get`、`create`、`update` 都从响应中剥离 `data` 字段(纵深防御 —— 永不返回 secret)
- **日志脱敏**: 凭据请求体在调试日志中脱敏
- **回退韧性**: 当 `GET /credentials/:id` 返回 403/405 时,`get` 回退到 list+filter(并非所有 n8n 版本都有该端点)
- **使用扫描韧性**: 当 `includeUsage: true` 触发的 workflow 扫描失败时,响应包含 `usageScanError`,仍返回基础凭据,而不是整个报错

---

## n8n_audit_instance(安全审计)

**速度**: 500-5000ms(扫描所有 workflow)

**适用**: 审计实例安全、查找硬编码 secret、检查无认证 webhook、验证错误处理

### 两种扫描方式

**1. 内置审计**(通过 n8n 的 `POST /audit` API):

- 5 个风险类别: `credentials`、`database`、`nodes`、`instance`、`filesystem`
- 包装 n8n 原生审计端点;不可用时优雅降级

**2. 自定义深度扫描**(workflow 分析):

- `hardcoded_secrets` —— 50+ 正则模式覆盖 API key/token/密码,以及 PII 检测
- `unauthenticated_webhooks` —— 无认证的 webhook/form 触发器
- `error_handling` —— 3+ 节点但无错误处理的 workflow
- `data_retention` —— 保存所有执行数据的 workflow

### 示例

```javascript
// 完整审计(默认)
n8n_audit_instance()

// 仅内置审计
n8n_audit_instance({
  categories: ["credentials", "nodes", "instance"],
  includeCustomScan: false
})

// 仅自定义扫描 —— 特定检查
n8n_audit_instance({
  customChecks: ["hardcoded_secrets", "unauthenticated_webhooks"]
})

// 自定义废弃 workflow 阈值
n8n_audit_instance({
  daysAbandonedWorkflow: 90
})
```

### 输出

返回可操作的 markdown 报告,含:

- **汇总表**: critical/high/medium/low 发现数
- **按 workflow 列出发现**: 每个 workflow 的问题表
- **内置审计结果**: n8n 原生审计发现
- **修复手册**:
  - 可自动修复(带工具链应用)
  - 需审核(需要人判断)
  - 需用户操作(如 key 轮换)

### Secret 掩码

检测到的 secret 在输出中掩码 —— 仅显示前 6 + 后 4 字符。原始值永不存储或返回。

### 修复类型

- `auto_fixable` —— 可用 MCP 工具修复(如给 webhook 加认证)
- `review_recommended` —— 需要人判断(如 PII 检测)
- `user_input_needed` —— 需要用户决定(如选择认证方式)
- `user_action_needed` —— 需手动操作(如轮换已暴露的 API key)

---

## n8n_validate_workflow(按 ID)

**适用**: 校验存储在 n8n 中的 workflow

```javascript
n8n_validate_workflow({
  id: "workflow-id",
  options: {
    validateNodes: true,
    validateConnections: true,
    validateExpressions: true,
    profile: "runtime"
  }
})
```

---

## n8n_get_workflow

**适用**: 检索 workflow 详情

**Modes**:

- `full`(默认) - 完整 workflow JSON
- `details` - 完整 + 执行统计
- `structure` - 仅节点 + 连接
- `minimal` - ID、name、active、tags

```javascript
// 完整 workflow
n8n_get_workflow({id: "workflow-id"})

// 仅结构
n8n_get_workflow({id: "workflow-id", mode: "structure"})

// 最小元数据
n8n_get_workflow({id: "workflow-id", mode: "minimal"})
```

---

## n8n_executions(执行管理)

**适用**: 管理 workflow 执行

### 获取执行详情

```javascript
n8n_executions({
  action: "get",
  id: "execution-id",
  mode: "summary"  // preview、summary、filtered、full、error
})

// 调试用 error mode
n8n_executions({
  action: "get",
  id: "execution-id",
  mode: "error",
  includeStackTrace: true
})
```

### 列出执行

```javascript
n8n_executions({
  action: "list",
  workflowId: "workflow-id",
  status: "error",  // success、error、waiting
  limit: 100
})
```

### 删除执行

```javascript
n8n_executions({
  action: "delete",
  id: "execution-id"
})
```

---

## Workflow 生命周期

**标准模式**:

```
1. CREATE
   n8n_create_workflow({...})
   → 返回 workflow ID

2. VALIDATE
   n8n_validate_workflow({id})
   → 检查错误

3. EDIT(迭代!编辑间隔平均 56s)
   n8n_update_partial_workflow({id, intent: "...", operations: [...]})
   → 做修改

4. 再次 VALIDATE
   n8n_validate_workflow({id})
   → 验证变更

5. ACTIVATE
   n8n_update_partial_workflow({
     id,
     intent: "激活 workflow",
     operations: [{type: "activateWorkflow"}]
   })
   → Workflow 现在响应触发器!

6. MONITOR
   n8n_executions({action: "list", workflowId: id})
   n8n_executions({action: "get", id: execution_id})
```

---

## 来自遥测的常见模式

### 模式 1:编辑 → 校验(7,841 次)

```javascript
n8n_update_partial_workflow({...})
// ↓ 23s(思考校验什么)
n8n_validate_workflow({id})
```

### 模式 2:校验 → 修复(7,266 次)

```javascript
n8n_validate_workflow({id})
// ↓ 58s(修复错误)
n8n_update_partial_workflow({...})
```

### 模式 3:迭代构建(31,464 次)

```javascript
update → update → update → ...(编辑间隔平均 56s)
```

**启示**: Workflow 是**迭代**构建的,不是一次到位!

---

## 最佳实践

### 应该

- **迭代**构建 workflow(编辑间隔平均 56s)
- 携带 **intent** 参数以获得更好的响应
- 用**智能参数**(branch、case)提升清晰度
- 重大变更**后**校验
- 关键更新用**原子模式**(默认)
- 为 AI 连接指定 **sourceOutput**
- 节点重命名/删除后清理陈旧连接
- 用 `n8n_deploy_template` 快速起步
- 就绪后通过 API 激活 workflow

### 不应

- 试图一次构建 workflow
- 跳过 intent 参数
- 在 branch/case 可用时用 sourceIndex
- 激活前跳过校验
- 创建后忘记测试 workflow
- 忽视自动清洗行为

---

## 小结

**要点**:

1. **n8n_update_partial_workflow** 是最常用工具(38,287 次使用,19 种操作类型)
2. 携带 **intent** 参数以获得更好的响应
3. Workflow **迭代**构建(编辑间隔平均 56s)
4. 用**智能参数**(`branch="true"`、`case=0`)提升清晰度
5. **patchNodeField** 用于定点字符串编辑(严格的 find/replace,支持正则)
6. 支持 **AI 连接**(8 种类型,配 sourceOutput)
7. 通过 API 支持 **workflow 激活**(`activateWorkflow` 操作)
8. 所有操作都运行**自动清洗**
9. 用 **n8n_deploy_template** 快速起步

**其他工具**:

- `n8n_deploy_template` - 直接部署模板
- `n8n_workflow_versions` - 版本控制与回滚
- `n8n_test_workflow` - 触发执行
- `n8n_executions` - 管理执行
- `n8n_manage_datatable` - 数据表与行管理
- `n8n_manage_credentials` - 凭据 CRUD + schema 发现
- `n8n_audit_instance` - 安全审计(内置 + 自定义扫描)
- `n8n_delete_workflow` - 永久删除 workflow
- `n8n_list_workflows` - 按过滤条件列出 workflow
- `n8n_update_full_workflow` - 完整 workflow 替换

**相关**:
- [SEARCH_GUIDE.md](SEARCH_GUIDE.md) - 查找要添加的节点
- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - 校验 workflow
