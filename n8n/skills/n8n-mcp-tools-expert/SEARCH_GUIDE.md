# 节点发现工具指南

查找与理解 n8n 节点的完整指南。

---

## search_nodes(从这里开始!)

**速度**: <20ms

**适用**: 你明确知道要找什么(关键字、服务、用途)

**语法**:

```javascript
search_nodes({
  query: "slack",      // 必填: 搜索关键字
  mode: "OR",          // 可选: OR(默认)、AND、FUZZY
  limit: 20,           // 可选: 最大结果数(默认 20)
  source: "all",       // 可选: all、core、community、verified
  includeExamples: false  // 可选: 含模板配置
})
```

**返回**:

```javascript
{
  "query": "slack",
  "results": [
    {
      "nodeType": "nodes-base.slack",                    // 用于 search/validate 工具
      "workflowNodeType": "n8n-nodes-base.slack",       // 用于 workflow 工具
      "displayName": "Slack",
      "description": "Consume Slack API",
      "category": "output",
      "relevance": "high"
    }
  ]
}
```

**提示**:

- 常见搜索: webhook、http、database、email、slack、google、ai
- `OR` 模式(默认): 任意词匹配
- `AND` 模式: 需要所有词
- `FUZZY` 模式: 容错拼写(可找 "slak" → Slack)
- 用 `source: "core"` 仅看内置节点
- 用 `includeExamples: true` 获取真实配置

---

## get_node(统一节点信息)

`get_node` 工具通过不同 detail 级别与 mode 提供全部节点信息。

### Detail 级别(mode="info")

| Detail | Tokens | 适用场景 |
|--------|--------|----------|
| `minimal` | ~200 | 快速元数据检查 |
| `standard` | ~1-2K | **多数场景(默认)** |
| `full` | ~3-8K | 仅复杂调试 |

### Standard Detail(推荐)

**速度**: <10ms | **大小**: ~1-2K tokens

**适用**: 找到节点后需要配置细节

```javascript
get_node({
  nodeType: "nodes-base.slack",      // 必填: 短前缀格式
  includeExamples: true              // 可选: 获取真实模板配置
})
// detail="standard" 是默认值
```

**返回**:

- 可用 operations 与 resources
- 必要属性(10-20 个最常用)
- 元数据(isAITool、isTrigger、hasCredentials)
- 模板中的真实示例(若 includeExamples: true)

### Minimal Detail

**速度**: <5ms | **大小**: ~200 tokens

**适用**: 仅需基础元数据

```javascript
get_node({
  nodeType: "nodes-base.slack",
  detail: "minimal"
})
```

**返回**: nodeType、displayName、description、category

### Full Detail(谨慎使用)

**速度**: <100ms | **大小**: ~3-8K tokens

**适用**: 调试复杂配置,需要完整 schema

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  detail: "full"
})
```

**警告**: 负载大!多数场景用 `standard`。

---

## get_node 的 mode

### mode="docs"(可读文档)

**适用**: 需要带示例的可读文档

```javascript
get_node({
  nodeType: "nodes-base.slack",
  mode: "docs"
})
```

**返回**: 格式化的 markdown,含:

- 使用示例
- 认证指南
- 常见模式
- 最佳实践

**比原始 schema 更适合学习!**

### mode="search_properties"(查找特定字段)

**适用**: 在节点中查找特定属性

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "search_properties",
  propertyQuery: "auth",           // 该 mode 必填
  maxPropertyResults: 20           // 可选: 默认 20
})
```

**返回**: 与查询匹配的属性路径与说明

**常见搜索**: auth、header、body、json、url、method、credential

### mode="versions"(版本历史)

**适用**: 检查节点版本历史

```javascript
get_node({
  nodeType: "nodes-base.executeWorkflow",
  mode: "versions"
})
```

**返回**: 含破坏性变更标记的版本历史

### mode="compare"(对比版本)

**适用**: 查看版本之间的差异

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "compare",
  fromVersion: "3.0",
  toVersion: "4.1"       // 可选: 默认为最新
})
```

**返回**: 版本之间的属性级变更

### mode="breaking"(仅破坏性变更)

**适用**: 升级前检查破坏性变更

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "breaking",
  fromVersion: "3.0"
})
```

**返回**: 仅破坏性变更(不是所有变更)

### mode="migrations"(可自动迁移)

**适用**: 检查哪些内容可自动迁移

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "migrations",
  fromVersion: "3.0"
})
```

**返回**: 可自动迁移的变更

---

## 其他参数

### includeTypeInfo

添加类型结构元数据(校验规则、JS 类型)

```javascript
get_node({
  nodeType: "nodes-base.if",
  includeTypeInfo: true   // 每属性增加 ~80-120 tokens
})
```

用于复杂节点如 filter、resourceMapper

### includeExamples

含来自模板的真实配置示例

```javascript
get_node({
  nodeType: "nodes-base.slack",
  includeExamples: true   // 每示例增加 ~200-400 tokens
})
```

仅与 `mode: "info"` 和 `detail: "standard"` 配合生效

---

## 通用工作流:查找与配置

```
Step 1: 搜索
search_nodes({query: "slack"})
→ 返回: nodes-base.slack

Step 2: 获取 operations(平均思考 18s)
get_node({
  nodeType: "nodes-base.slack",
  includeExamples: true
})
→ 返回: operations 列表 + 示例配置

Step 3: 校验配置
validate_node({
  nodeType: "nodes-base.slack",
  config: {resource: "channel", operation: "create"},
  profile: "runtime"
})
→ 返回: 校验结果

Step 4: 在 Workflow 中使用
(配置就绪!)
```

**最常用模式**: search → get_node(平均 18s)

---

## 快速对比

| 工具/Mode | 适用场景 | 速度 | 大小 |
|-----------|-------------|-------|------|
| `search_nodes` | 按关键字查找 | <20ms | 小 |
| `get_node (standard)` | **获取配置(默认)** | <10ms | 1-2K |
| `get_node (minimal)` | 快速元数据 | <5ms | 200 |
| `get_node (full)` | 复杂调试 | <100ms | 3-8K |
| `get_node (docs)` | 学习用法 | 快 | 中 |
| `get_node (search_properties)` | 找特定字段 | 快 | 小 |
| `get_node (versions)` | 检查版本 | 快 | 小 |

**最佳实践**: search → get_node(standard) → validate

---

## nodeType 格式(关键!)

**Search/Validate 工具**(短前缀):

```javascript
"nodes-base.slack"
"nodes-base.httpRequest"
"nodes-langchain.agent"
```

**Workflow 工具**(完整前缀):

```javascript
"n8n-nodes-base.slack"
"n8n-nodes-base.httpRequest"
"@n8n/n8n-nodes-langchain.agent"
```

**转换**: search_nodes 同时返回两种格式:

```javascript
{
  "nodeType": "nodes-base.slack",          // 用于 get_node、validate_node
  "workflowNodeType": "n8n-nodes-base.slack"  // 用于 n8n_create_workflow
}
```

---

## 示例

### 查找并配置 HTTP Request

```javascript
// Step 1: 搜索
search_nodes({query: "http request"})

// Step 2: 获取 standard 信息
get_node({nodeType: "nodes-base.httpRequest"})

// Step 3: 查找 auth 选项
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "search_properties",
  propertyQuery: "authentication"
})

// Step 4: 校验配置
validate_node({
  nodeType: "nodes-base.httpRequest",
  config: {method: "POST", url: "https://api.example.com"},
  profile: "runtime"
})
```

### 探索 AI 节点

```javascript
// 查找所有 AI 相关节点
search_nodes({query: "ai agent", source: "all"})

// 获取 AI Agent 文档
get_node({nodeType: "nodes-langchain.agent", mode: "docs"})

// 获取配置详情与示例
get_node({
  nodeType: "nodes-langchain.agent",
  includeExamples: true
})
```

### 检查版本兼容性

```javascript
// 查看所有版本
get_node({nodeType: "nodes-base.executeWorkflow", mode: "versions"})

// 检查从 v1 到 v2 的破坏性变更
get_node({
  nodeType: "nodes-base.executeWorkflow",
  mode: "breaking",
  fromVersion: "1.0"
})
```

---

## 相关

- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - 校验节点配置
- [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) - 在 workflow 中使用节点
