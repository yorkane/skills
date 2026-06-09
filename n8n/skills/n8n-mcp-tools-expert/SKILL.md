---
name: n8n-mcp-tools-expert
description: 高效使用 n8n-mcp MCP 工具的专家指南。当搜索节点、校验配置、访问模板、管理 workflow、管理凭据、审计实例安全,或使用任何 n8n-mcp 工具时使用。提供工具选择指导、参数格式与常见模式。重要 —— 在调用任何 n8n-mcp 工具前应先查阅本 SKILL,可避免 nodeType 格式错误、参数结构错误、工具使用低效等常见问题。当用户提到 n8n、workflow、节点或自动化,且你拥有 n8n MCP 工具时,应优先使用本 SKILL。
---

# n8n MCP 工具专家

掌握使用 n8n-mcp MCP 服务器工具构建 workflow 的指南。

---

## 工具分类

n8n-mcp 提供的工具按类别组织:

1. **节点发现** → [SEARCH_GUIDE.md](SEARCH_GUIDE.md)
2. **配置校验** → [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md)
3. **Workflow 管理** → [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)
4. **模板库** - 搜索与部署 2,700+ 真实 workflow
5. **Workflow 生成** - 自然语言 → workflow,带 proposal 审核(`n8n_generate_workflow`,仅 hosted)
6. **数据表** - 管理 n8n 数据表与行(`n8n_manage_datatable`)
7. **凭据管理** - 完整凭据 CRUD + schema 发现(`n8n_manage_credentials`)
8. **安全审计** - 实例安全审计,含自定义深度扫描(`n8n_audit_instance`)
9. **文档与指南** - 工具文档、AI agent 指南、Code 节点指南

---

## 速查表

### 最常用工具(按成功率排序)

| 工具 | 适用场景 | 速度 |
|------|----------|------|
| `search_nodes` | 按关键字查找节点 | <20ms |
| `get_node` | 了解节点操作(detail="standard") | <10ms |
| `validate_node` | 校验配置(mode="full") | <100ms |
| `n8n_create_workflow` | 创建 workflow | 100-500ms |
| `n8n_update_partial_workflow` | 编辑 workflow(使用频率最高!) | 50-200ms |
| `validate_workflow` | 校验完整 workflow | 100-500ms |
| `n8n_deploy_template` | 部署模板到 n8n 实例 | 200-500ms |
| `n8n_generate_workflow` | NL → workflow(proposal → 部署),仅 hosted | 2-15s |
| `n8n_manage_datatable` | 管理数据表与行 | 50-500ms |
| `n8n_manage_credentials` | 凭据 CRUD + schema 发现 | 50-500ms |
| `n8n_audit_instance` | 安全审计(内置 + 自定义扫描) | 500-5000ms |
| `n8n_autofix_workflow` | 自动修复校验错误 | 200-1500ms |

---

## 工具选择指南

### 找到正确的节点

**工作流**:

```
1. search_nodes({query: "keyword"})
2. get_node({nodeType: "nodes-base.name"})
3. [可选] get_node({nodeType: "nodes-base.name", mode: "docs"})
```

**示例**:

```javascript
// Step 1: 搜索
search_nodes({query: "slack"})
// 返回: nodes-base.slack

// Step 2: 获取详情
get_node({nodeType: "nodes-base.slack"})
// 返回: operations、properties、examples(standard detail)

// Step 3: 获取可读文档
get_node({nodeType: "nodes-base.slack", mode: "docs"})
// 返回: markdown 文档
```

**常见模式**: 搜索 → get_node(平均 18s)

### 校验配置

**工作流**:

```
1. validate_node({nodeType, config: {}, mode: "minimal"}) - 校验必填字段
2. validate_node({nodeType, config, profile: "runtime"}) - 完整校验
3. [重复] 修复错误,再次校验
```

**常见模式**: 校验 → 修复 → 校验(每轮 23s 思考 + 58s 修复)

### 管理 Workflow

**工作流**:

```
1. n8n_create_workflow({name, nodes, connections})
2. n8n_validate_workflow({id})
3. n8n_update_partial_workflow({id, operations: [...]})
4. n8n_validate_workflow({id}) 再次
5. n8n_update_partial_workflow({id, operations: [{type: "activateWorkflow"}]})
```

**常见模式**: 迭代更新(编辑间隔平均 56s)

---

## 关键:nodeType 格式

**不同工具使用不同格式**!

### 格式 1:搜索/校验工具

```javascript
// 使用简短前缀
"nodes-base.slack"
"nodes-base.httpRequest"
"nodes-base.webhook"
"nodes-langchain.agent"
```

**使用此格式的工具**:
- search_nodes(返回此格式)
- get_node
- validate_node
- validate_workflow

### 格式 2:Workflow 工具

```javascript
// 使用完整前缀
"n8n-nodes-base.slack"
"n8n-nodes-base.httpRequest"
"n8n-nodes-base.webhook"
"@n8n/n8n-nodes-langchain.agent"
```

**使用此格式的工具**:
- n8n_create_workflow
- n8n_update_partial_workflow

### 转换

```javascript
// search_nodes 同时返回两种格式
{
  "nodeType": "nodes-base.slack",          // 用于 search/validate 工具
  "workflowNodeType": "n8n-nodes-base.slack"  // 用于 workflow 工具
}
```

---

## 常见错误

### 错误 1:nodeType 格式错误

**问题**: "Node not found" 错误

```javascript
// 错误
get_node({nodeType: "slack"})  // 缺前缀
get_node({nodeType: "n8n-nodes-base.slack"})  // 前缀错误

// 正确
get_node({nodeType: "nodes-base.slack"})
```

### 错误 2:默认使用 detail="full"

**问题**: 返回体过大,响应慢,浪费 token

```javascript
// 错误 - 返回 3-8K tokens,谨慎使用
get_node({nodeType: "nodes-base.slack", detail: "full"})

// 正确 - 返回 1-2K tokens,覆盖 95% 场景
get_node({nodeType: "nodes-base.slack"})  // detail="standard" 是默认值
get_node({nodeType: "nodes-base.slack", detail: "standard"})
```

**何时使用 detail="full"**:
- 调试复杂配置问题
- 需要完整属性 schema 与所有嵌套选项
- 探索高级功能

**更好的替代**:
1. `get_node({detail: "standard"})` - 获取 operations 列表(默认)
2. `get_node({mode: "docs"})` - 获取可读文档
3. `get_node({mode: "search_properties", propertyQuery: "auth"})` - 查找特定属性

### 错误 3:未使用校验 profile

**问题**: 误报过多或漏报真实错误

**Profile**:
- `minimal` - 仅必填字段(快速,宽松)
- `runtime` - 值 + 类型(推荐,部署前使用)
- `ai-friendly` - 减少误报(AI 配置使用)
- `strict` - 最大校验强度(生产)

```javascript
// 错误 - 使用默认 profile
validate_node({nodeType, config})

// 正确 - 显式指定 profile
validate_node({nodeType, config, profile: "runtime"})
```

### 错误 4:忽视自动清洗

**现象**: 任何 workflow 更新都会触发所有节点的自动清洗

**自动修复**:
- 二元运算符(equals、contains)→ 移除 singleValue
- 一元运算符(isEmpty、isNotEmpty)→ 添加 `singleValue: true`
- IF/Switch 节点 → 添加缺失的元数据

**无法修复**:
- 断开的连接
- 分支数量不匹配
- 矛盾的损坏状态

```javascript
// 任何更新后,自动清洗会对所有节点运行
n8n_update_partial_workflow({id, operations: [...]})
// → 自动修复 operator 结构
```

### 错误 5:未使用智能参数

**问题**: 多输出节点的 sourceIndex 计算复杂

**旧方式**(手动):

```javascript
// IF 节点连接
{
  type: "addConnection",
  source: "IF",
  target: "Handler",
  sourceIndex: 0  // 哪个输出?难记!
}
```

**新方式**(智能参数):

```javascript
// IF 节点 - 语义化分支名
{
  type: "addConnection",
  source: "IF",
  target: "True Handler",
  branch: "true"  // 清晰可读!
}

{
  type: "addConnection",
  source: "IF",
  target: "False Handler",
  branch: "false"
}

// Switch 节点 - 语义化 case 编号
{
  type: "addConnection",
  source: "Switch",
  target: "Handler A",
  case: 0
}
```

### 错误 7:updateNode 参数名错误

**问题**: 使用 `parameters` 而不是 `updates`

```javascript
// 错误
n8n_update_partial_workflow({
  id: "wf-123",
  operations: [{
    type: "updateNode",
    nodeName: "HTTP Request",
    parameters: {url: "..."}  // ❌ 错误的键
  }]
})

// 正确
n8n_update_partial_workflow({
  id: "wf-123",
  operations: [{
    type: "updateNode",
    nodeName: "HTTP Request",
    updates: {url: "..."}  // ✅ 正确的键
  }]
})
```

### 错误 8:凭据挂载格式错误

**问题**: 凭据未挂载到节点

```javascript
// 错误 - 凭据是平铺对象
updates: {credentials: "myApiKey"}

// 正确 - 凭据按类型嵌套,含 id 和 name
updates: {
  credentials: {
    httpHeaderAuth: {
      id: "abc123",
      name: "My API Key"
    }
  }
}
```

### 错误 6:未使用 intent 参数

**问题**: 工具响应帮助性降低

```javascript
// 错误 - 响应缺少上下文
n8n_update_partial_workflow({
  id: "abc",
  operations: [{type: "addNode", node: {...}}]
})

// 正确 - 响应更利于 AI 理解
n8n_update_partial_workflow({
  id: "abc",
  intent: "为 API 失败添加错误处理",
  operations: [{type: "addNode", node: {...}}]
})
```

---

## 工具使用模式

### 模式 1:节点发现(最常用)

**常见工作流**: 步骤间平均 18s

```javascript
// Step 1: 搜索(快速!)
const results = await search_nodes({
  query: "slack",
  mode: "OR",  // 默认:任意词匹配
  limit: 20
});
// → 返回: nodes-base.slack, nodes-base.slackTrigger

// Step 2: 获取详情(约 18s 后,用户在审阅搜索结果)
const details = await get_node({
  nodeType: "nodes-base.slack",
  includeExamples: true  // 获取真实模板配置
});
// → 返回: operations、properties、metadata
```

### 模式 2:校验循环

**典型周期**: 23s 思考,58s 修复

```javascript
// Step 1: 校验
const result = await validate_node({
  nodeType: "nodes-base.slack",
  config: {
    resource: "channel",
    operation: "create"
  },
  profile: "runtime"
});

// Step 2: 检查错误(约 23s 思考)
if (!result.valid) {
  console.log(result.errors);  // "Missing required field: name"
}

// Step 3: 修复配置(约 58s 修复)
config.name = "general";

// Step 4: 再次校验
await validate_node({...});  // 重复直到通过
```

### 模式 3:Workflow 编辑

**使用频率最高的更新工具**: 99.0% 成功率,编辑间隔平均 56s

```javascript
// 迭代构建 workflow(不要一次到位!)
// Edit 1
await n8n_update_partial_workflow({
  id: "workflow-id",
  intent: "添加 webhook 触发器",
  operations: [{type: "addNode", node: {...}}]
});

// ~56s 后...

// Edit 2
await n8n_update_partial_workflow({
  id: "workflow-id",
  intent: "将 webhook 连接到处理器",
  operations: [{type: "addConnection", source: "...", target: "..."}]
});

// ~56s 后...

// Edit 3(校验)
await n8n_validate_workflow({id: "workflow-id"});

// 就绪?激活!
await n8n_update_partial_workflow({
  id: "workflow-id",
  intent: "为生产环境激活 workflow",
  operations: [{type: "activateWorkflow"}]
});
```

---

## 详细指南

### 节点发现工具
详见 [SEARCH_GUIDE.md](SEARCH_GUIDE.md),包含:
- search_nodes
- get_node 的 detail 级别(minimal、standard、full)
- get_node 的 mode(info、docs、search_properties、versions)

### 校验工具
详见 [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md),包含:
- 校验 profile 详解
- validate_node 的 mode(minimal、full)
- validate_workflow 完整结构
- 自动清洗系统
- 校验错误处理

### Workflow 管理
详见 [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md),包含:
- n8n_create_workflow
- n8n_update_partial_workflow(含 19 种 operation 类型,包括 patchNodeField!)
- 智能参数(branch、case)
- AI 连接类型(8 种)
- Workflow 激活(activateWorkflow/deactivateWorkflow)
- n8n_deploy_template
- n8n_workflow_versions
- n8n_manage_credentials(凭据 CRUD + schema 发现)
- n8n_audit_instance(安全审计)

---

## 模板使用

### 搜索模板

```javascript
// 按关键字搜索(默认 mode)
search_templates({
  query: "webhook slack",
  limit: 20
});

// 按节点类型搜索
search_templates({
  searchMode: "by_nodes",
  nodeTypes: ["n8n-nodes-base.httpRequest", "n8n-nodes-base.slack"]
});

// 按任务类型搜索
search_templates({
  searchMode: "by_task",
  task: "webhook_processing"
});

// 按元数据搜索(复杂度、配置时间)
search_templates({
  searchMode: "by_metadata",
  complexity: "simple",
  maxSetupMinutes: 15
});
```

### 获取模板详情

```javascript
get_template({
  templateId: 2947,
  mode: "structure"  // 仅 nodes+connections
});

get_template({
  templateId: 2947,
  mode: "full"  // 完整 workflow JSON
});
```

### 直接部署模板

```javascript
// 部署模板到 n8n 实例
n8n_deploy_template({
  templateId: 2947,
  name: "My Weather to Slack",  // 自定义名称(可选)
  autoFix: true,  // 自动修复常见问题(默认)
  autoUpgradeVersions: true  // 升级节点版本(默认)
});
// 返回: workflow ID、所需凭据、已应用的修复
```

---

## Workflow 生成

### n8n_generate_workflow

通过多步骤流程(带审核检查点)从自然语言描述生成 n8n workflow。**仅 hosted** —— 自托管实例会收到重定向消息而非 workflow。

**两种路径**:

**路径 A —— 选择 proposal**(默认,最便宜,推荐):

```javascript
// Step 1: 最多获取 5 个 proposal(不部署)
n8n_generate_workflow({
  description: "Send a Slack message every morning at 9am with a daily standup reminder"
})
// → { status: "proposals", proposals: [{id, name, description, flow_summary, credentials_needed}, ...] }

// Step 2: 部署所选 proposal
n8n_generate_workflow({
  description: "Send a Slack message every morning at 9am with a daily standup reminder",
  deploy_id: "uuid-from-proposals"
})
// → { status: "deployed", workflow_id, workflow_name, workflow_url, node_count, node_summary }
```

**路径 B —— 全新生成**(当没有合适的 proposal 时):

```javascript
// Step 1: 跳过 proposal 缓存,获取预览(不部署)
n8n_generate_workflow({
  description: "Webhook → transform JSON → POST to REST API",
  skip_cache: true
})
// → { status: "preview", ... }

// Step 2: 部署预览
n8n_generate_workflow({
  description: "Webhook → transform JSON → POST to REST API",
  confirm_deploy: true
})
// → { status: "deployed", ... }
```

**描述建议**(越具体效果越好):
- 触发器类型: webhook、schedule(含周期)、manual、form、chat
- 集成的服务: 明确名称(Slack、Gmail、Postgres 等)
- 逻辑/流程: 需要的转换、分支、聚合

**注意事项**:
- **仅 hosted** —— 自托管时响应为 `{hosted_only: true, ...}` 含重定向消息
- 生成的 workflow 部署后为**未激活**状态 —— 激活前需在 n8n UI 中配置凭据
- Proposal/preview 存于 per-MCP-session 状态;切换 session 会丢失待处理状态
- 部署后务必运行 `n8n_validate_workflow({id})` 检查问题
- 自托管实例可回退到 `n8n_deploy_template`(策划模板)或 `n8n_create_workflow`(完全控制)

**何时使用哪个**:

| 目标 | 工具 |
|------|------|
| 从 2,700+ 策划模板中选择 | `n8n_deploy_template` |
| 用自然语言描述需求(仅 hosted) | `n8n_generate_workflow` |
| 节点级精细构建 | `n8n_create_workflow` |

---

## 数据表管理

### n8n_manage_datatable

管理 n8n 数据表与行的统一工具。支持表与行的 CRUD 操作、过滤、分页与 dry-run。

**Table Actions**: `createTable`、`listTables`、`getTable`、`updateTable`、`deleteTable`
**Row Actions**: `getRows`、`insertRows`、`updateRows`、`upsertRows`、`deleteRows`

```javascript
// 创建数据表
n8n_manage_datatable({
  action: "createTable",
  name: "Contacts",
  columns: [
    {name: "email", type: "string"},
    {name: "score", type: "number"}
  ]
})

// 按条件获取行
n8n_manage_datatable({
  action: "getRows",
  tableId: "dt-123",
  filter: {
    filters: [{columnName: "status", condition: "eq", value: "active"}]
  },
  limit: 50
})

// 插入行
n8n_manage_datatable({
  action: "insertRows",
  tableId: "dt-123",
  data: [{email: "a@b.com", score: 10}],
  returnType: "all"
})

// 带 dry run 更新(预览变更)
n8n_manage_datatable({
  action: "updateRows",
  tableId: "dt-123",
  filter: {filters: [{columnName: "score", condition: "lt", value: 5}]},
  data: {status: "inactive"},
  dryRun: true
})

// Upsert(更新或插入)
n8n_manage_datatable({
  action: "upsertRows",
  tableId: "dt-123",
  filter: {filters: [{columnName: "email", condition: "eq", value: "a@b.com"}]},
  data: {score: 15},
  returnData: true
})
```

**过滤条件**: `eq`、`neq`、`like`、`ilike`、`gt`、`gte`、`lt`、`lte`

**最佳实践**:
- 批量更新/删除前用 `dryRun: true` 验证过滤正确性
- 预先定义列类型(`string`、`number`、`boolean`、`date`)
- 对 `insertRows` 使用 `returnType: "count"`(默认)以最小化响应体
- `deleteRows` 必须有 filter —— 不能无 filter 删除所有行

---

## 凭据管理

### n8n_manage_credentials

管理 n8n 凭据的统一工具。支持完整 CRUD、schema 发现,以及反向查询哪些 workflow 使用了某个凭据。

**Actions**: `list`、`get`、`create`、`update`、`delete`、`getSchema`

**可选 flag**: `includeUsage`(boolean,默认 `false`) —— 在 `list` 和 `get` 上,通过反向扫描 workflow 给每个凭据附加 `usedIn: [{id, name, active}]` 数组与 `usageCount`。省略时行为不变。

```javascript
// 列出所有凭据
n8n_manage_credentials({action: "list"})
// → 返回: id、name、type、createdAt、updatedAt(不暴露 secret)

// 按 ID 获取凭据
n8n_manage_credentials({action: "get", id: "123"})
// → 返回: 凭据元数据(data 字段被剥离以确保安全)

// 发现凭据类型的必填字段
n8n_manage_credentials({action: "getSchema", type: "httpHeaderAuth"})
// → 返回: 必填字段、类型、说明

// 创建凭据
n8n_manage_credentials({
  action: "create",
  name: "My Slack Token",
  type: "slackApi",
  data: {accessToken: "xoxb-..."}
})

// 更新凭据
n8n_manage_credentials({
  action: "update",
  id: "123",
  name: "Updated Name",
  data: {accessToken: "xoxb-new-..."},
  type: "slackApi"  // 可选,部分 n8n 版本需要
})

// 删除凭据
n8n_manage_credentials({action: "delete", id: "123"})

// 列出凭据及引用它的 workflow
n8n_manage_credentials({action: "list", includeUsage: true})
// → 每个凭据新增: usedIn: [{id, name, active}], usageCount: N
//   响应可能含 usageScanError(若 workflow 扫描失败)
//   (此时仍会返回基础凭据列表)

// 获取单个凭据及引用它的 workflow
n8n_manage_credentials({action: "get", id: "123", includeUsage: true})
// → 添加 usedIn 与 usageCount;若扫描失败,响应会设置 usageScanError 并省略 usedIn/usageCount
```

**何时使用 `includeUsage`**:
- 删除前的安全检查:删除前确认凭据未被引用
- 凭据轮换影响分析:更新 secret 前列出受影响的 workflow
- 修复 `n8n_audit_instance` 的发现(例如共享/过度授权的凭据)

**`includeUsage` 注意事项**:
- 触发客户端全量 workflow 扫描(n8n API 无原生查询) —— 在大实例上较慢,尤其扫描数百个 workflow 时
- 上限 5000 个 workflow(同 `n8n_audit_instance`);归档 workflow 被 n8n 排除
- "无 usage" 结果**不**保证凭据未被使用 —— 销毁性操作前请验证
- 扫描失败时响应优雅降级:返回基础凭据并附 `usageScanError` 字段,而不是整个调用失败

**安全**:
- `get`、`create`、`update` 响应会剥离 `data` 字段(纵深防御)
- 若直接 GET 返回 403/405,`get` action 回退到 list+filter(并非所有 n8n 版本都暴露此端点)
- 凭据请求体在调试日志中被脱敏

**最佳实践**:
- `create` 之前用 `getSchema` 发现凭据类型的必填字段
- `data` 字段包含真实 secret 值 —— 仅在 create/update 时提供
- 创建后务必用 list 验证
- `delete` 之前用 `get` + `includeUsage: true` 查看影响

---

## 安全审计

### n8n_audit_instance

结合 n8n 内置审计与自定义深度扫描的安全审计工具。

```javascript
// 完整审计(默认,同时运行内置 + 自定义扫描)
n8n_audit_instance()

// 仅内置审计(指定类别)
n8n_audit_instance({
  categories: ["credentials", "nodes"],
  includeCustomScan: false
})

// 仅自定义扫描(指定检查)
n8n_audit_instance({
  customChecks: ["hardcoded_secrets", "unauthenticated_webhooks"]
})
```

**内置审计类别**: `credentials`、`database`、`nodes`、`instance`、`filesystem`

**自定义深度扫描检查项**:
- `hardcoded_secrets` —— 检测 50+ 模式,覆盖 API key、token、password(OpenAI、AWS、Stripe、GitHub、Slack 等)以及 PII(email、电话、信用卡)。Secret 在输出中被掩码(前 6 + 后 4 字符)
- `unauthenticated_webhooks` —— 标记无认证的 webhook/form 触发器
- `error_handling` —— 标记 3+ 节点但无错误处理的 workflow
- `data_retention` —— 标记保存所有执行数据的 workflow(success + failure)

**参数**(均为可选):
- `categories` —— 内置审计类别数组
- `includeCustomScan` —— 布尔(默认 `true`)
- `customChecks` —— 4 个自定义检查的子集
- `daysAbandonedWorkflow` —— 废弃 workflow 的天数阈值

**输出**: 可操作的 markdown 报告,含:
- 汇总表(critical/high/medium/low 发现数)
- 按 workflow 分组的发现
- 三段式修复手册:
  - **可自动修复** —— 可用工具链修复的项目(如给 webhook 加认证)
  - **需人工审核** —— 需要人判断的项目(如 PII 检测)
  - **需用户操作** —— 需手动干预的项目(如轮换已泄露的 key)

---

## 自助工具

### 获取工具文档

```javascript
// 所有工具概览
tools_documentation()

// 特定工具详情
tools_documentation({
  topic: "search_nodes",
  depth: "full"
})

// Code 节点指南
tools_documentation({topic: "javascript_code_node_guide", depth: "full"})
tools_documentation({topic: "python_code_node_guide", depth: "full"})
```

### AI Agent 指南

```javascript
// 完整 AI workflow 指南
ai_agents_guide()
// 返回: 架构、连接、工具、校验、最佳实践

// 或通过 tools_documentation
tools_documentation({topic: "ai_agents_guide", depth: "full"})
```

### 健康检查

```javascript
// 快速健康检查
n8n_health_check()

// 详细诊断
n8n_health_check({mode: "diagnostic"})
// → 返回: status、env vars、tool status、API connectivity
```

---

## 工具可用性

**始终可用**(无需 n8n API):
- search_nodes、get_node
- validate_node、validate_workflow
- search_templates、get_template
- tools_documentation、ai_agents_guide

**需要 n8n API**(N8N_API_URL + N8N_API_KEY):
- n8n_create_workflow
- n8n_update_partial_workflow、n8n_update_full_workflow
- n8n_validate_workflow(按 ID)
- n8n_list_workflows、n8n_get_workflow、n8n_delete_workflow
- n8n_test_workflow
- n8n_executions
- n8n_deploy_template
- n8n_workflow_versions
- n8n_autofix_workflow
- n8n_manage_datatable
- n8n_manage_credentials
- n8n_audit_instance

若 API 工具不可用,可使用模板与只校验 workflow。

---

## 统一工具参考

### get_node(统一节点信息)

**Detail 级别**(mode="info",默认):
- `minimal`(~200 tokens) - 仅基础元数据
- `standard`(~1-2K tokens) - 必要属性 + operations(推荐)
- `full`(~3-8K tokens) - 完整 schema(谨慎使用)

**Operation Modes**:
- `info`(默认) - 含 detail 级别的节点 schema
- `docs` - 可读 markdown 文档
- `search_properties` - 查找特定属性(配合 propertyQuery 使用)
- `versions` - 列出所有版本及破坏性变更
- `compare` - 对比两个版本
- `breaking` - 仅显示破坏性变更
- `migrations` - 显示可自动迁移的变更

```javascript
// 标准(推荐)
get_node({nodeType: "nodes-base.httpRequest"})

// 获取文档
get_node({nodeType: "nodes-base.webhook", mode: "docs"})

// 搜索属性
get_node({nodeType: "nodes-base.httpRequest", mode: "search_properties", propertyQuery: "auth"})

// 检查版本
get_node({nodeType: "nodes-base.executeWorkflow", mode: "versions"})
```

### validate_node(统一校验)

**Modes**:
- `full`(默认) - 综合校验,含 errors/warnings/suggestions
- `minimal` - 仅快速必填字段检查

**Profiles**(对 mode="full"):

- `minimal` - 非常宽松
- `runtime` - 标准(默认,推荐)
- `ai-friendly` - 平衡,适合 AI workflow
- `strict` - 最严格(生产)

```javascript
// 完整校验,runtime profile
validate_node({nodeType: "nodes-base.slack", config: {...}, profile: "runtime"})

// 快速必填字段检查
validate_node({nodeType: "nodes-base.webhook", config: {}, mode: "minimal"})
```

---

## 性能特征

| 工具 | 响应时间 | 负载大小 |
|------|----------|----------|
| search_nodes | <20ms | 小 |
| get_node (standard) | <10ms | ~1-2KB |
| get_node (full) | <100ms | 3-8KB |
| validate_node (minimal) | <50ms | 小 |
| validate_node (full) | <100ms | 中 |
| validate_workflow | 100-500ms | 中 |
| n8n_manage_credentials | 50-500ms | 小-中 |
| n8n_audit_instance | 500-5000ms | 大 |
| n8n_create_workflow | 100-500ms | 中 |
| n8n_update_partial_workflow | 50-200ms | 小 |
| n8n_deploy_template | 200-500ms | 中 |

---

## 最佳实践

### 应该
- 简单 workflow(<=5 节点)直接使用 MCP 工具,不要过度设计调研
- 用 `patchNodeField` 对 Code 节点内容做定点编辑,而不是替换整个节点
- 多数场景使用 `get_node({detail: "standard"})`
- 显式指定校验 profile(`profile: "runtime"`)
- 使用智能参数(`branch`、`case`)以提升可读性
- 在 workflow 更新时携带 `intent` 参数
- 遵循 search → get_node → validate 流程
- 迭代构建 workflow(编辑间隔平均 56s)
- 每次重大修改后校验
- 用 `includeExamples: true` 获取真实配置
- 用 `n8n_deploy_template` 快速起步

### 不应
- 不必要时使用 `detail: "full"`(浪费 token)
- 忘记 nodeType 前缀(`nodes-base.*`)
- 跳过校验 profile
- 试图一次性构建 workflow(要迭代!)
- 忽视自动清洗行为
- 在 search/validate 工具上使用完整前缀(`n8n-nodes-base.*`)
- 构建完成后忘记激活 workflow

---

## 小结

**要点**:

1. 使用 **get_node** + `detail: "standard"`(默认) —— 覆盖 95% 场景
2. nodeType 格式不同: `nodes-base.*`(search/validate) vs `n8n-nodes-base.*`(workflows)
3. 显式指定**校验 profile**(`runtime` 推荐)
4. 使用**智能参数**(`branch="true"`、`case=0`)
5. 在 workflow 更新中携带 **intent 参数**
6. **自动清洗**在所有节点的更新时运行
7. Workflow 可通过 API 激活(`activateWorkflow` operation)
8. Workflow 是**迭代**构建的(编辑间隔平均 56s)
9. **数据表**用 `n8n_manage_datatable` 管理(CRUD + 过滤)
10. **凭据**用 `n8n_manage_credentials` 管理(CRUD + schema 发现)
11. **安全审计**用 `n8n_audit_instance`(内置 + 自定义深度扫描)
12. **AI agent 指南**通过 `ai_agents_guide()` 工具获取

**通用工作流**:

1. search_nodes → 找节点
2. get_node → 理解配置
3. validate_node → 校验配置
4. n8n_create_workflow → 构建
5. n8n_validate_workflow → 验证
6. n8n_update_partial_workflow → 迭代
7. activateWorkflow → 上线!

详情参见:
- [SEARCH_GUIDE.md](SEARCH_GUIDE.md) - 节点发现
- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - 配置校验
- [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) - workflow 管理

---

**相关 SKILL**:
- n8n Expression Syntax - 在 workflow 字段中写表达式
- n8n Workflow Patterns - 来自模板的架构模式
- n8n Validation Expert - 解读校验错误
- n8n Node Configuration - 特定 operation 的配置
- n8n Code JavaScript - 在 Code 节点写 JavaScript
- n8n Code Python - 在 Code 节点写 Python
