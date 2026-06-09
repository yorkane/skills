---
name: n8n-validation-expert
description: 解读校验错误并指导修复。遇到校验错误、校验警告、误报、operator 结构问题,或需要理解校验结果时使用。需要了解校验 profile、错误类型、校验循环流程、自动修复能力时也可使用。当 `validate_node` 或 `validate_workflow` 返回错误或警告时,应查阅本 SKILL —— 它能区分哪些警告是误报、哪些错误需要实际修复。
---

# n8n 校验专家

解读并修复 n8n 校验错误的专家指南。

---

## 校验哲学

**尽早校验,频繁校验**

校验通常是迭代的:

- 预期会有校验反馈循环
- 通常 2-3 轮 校验 → 修复
- 平均: 思考错误 23s,修复 58s

**要点**: 校验是迭代过程,不是一次到位!

---

## 错误严重程度等级

### 1. 错误(必须修复)

**阻塞 workflow 执行** —— 激活前必须解决

**类型**:

- `missing_required` - 必填字段未填
- `invalid_value` - 值不在允许选项内
- `type_mismatch` - 数据类型错误(如字符串而非数字)
- `invalid_reference` - 引用的节点不存在
- `invalid_expression` - 表达式语法错误

**示例**:

```json
{
  "type": "missing_required",
  "property": "channel",
  "message": "Channel name is required",
  "fix": "Provide a channel name (lowercase, no spaces, 1-80 characters)"
}
```

### 2. 警告(建议修复)

**不阻塞执行** —— workflow 可激活但可能有问题

**类型**:

- `best_practice` - 推荐但非必需
- `deprecated` - 使用了旧 API/特性
- `performance` - 潜在性能问题

**示例**:

```json
{
  "type": "best_practice",
  "property": "errorHandling",
  "message": "Slack API can have rate limits",
  "suggestion": "Add onError: 'continueRegularOutput' with retryOnFail"
}
```

### 3. 建议(可选)

**锦上添花** —— 可提升 workflow 的改进项

**类型**:

- `optimization` - 可更高效
- `alternative` - 有更好的实现方式

---

## 校验循环

### 来自遥测的模式

**7,841 次**此模式出现:

```
1. 配置节点
   ↓
2. validate_node(思考错误 23 秒)
   ↓
3. 仔细阅读错误信息
   ↓
4. 修复错误
   ↓
5. 再次 validate_node(修复 58 秒)
   ↓
6. 重复直到通过(通常 2-3 轮)
```

### 示例

```javascript
// 第 1 轮
let config = {
  resource: "channel",
  operation: "create"
};

const result1 = validate_node({
  nodeType: "nodes-base.slack",
  config,
  profile: "runtime"
});
// → 错误: 缺少 "name"

// ⏱️  23 秒思考...

// 第 2 轮
config.name = "general";

const result2 = validate_node({
  nodeType: "nodes-base.slack",
  config,
  profile: "runtime"
});
// → 错误: 缺少 "text"

// ⏱️  58 秒修复...

// 第 3 轮
config.text = "Hello!";

const result3 = validate_node({
  nodeType: "nodes-base.slack",
  config,
  profile: "runtime"
});
// → 通过!✅
```

**这是正常的!** 多轮迭代不要气馁。

---

## 校验 Profile

为不同阶段选择合适的 profile:

### minimal

**适用**: 编辑中的快速检查

**校验内容**:

- 仅必填字段
- 基础结构

**优点**: 最快、最宽松
**缺点**: 可能漏掉问题

### runtime(推荐)

**适用**: 部署前校验

**校验内容**:

- 必填字段
- 值类型
- 允许的值
- 基础依赖

**优点**: 平衡,捕获真实错误
**缺点**: 一些边缘情况可能漏掉

**推荐在大多数场景下使用**

### ai-friendly

**适用**: AI 生成的配置

**校验内容**:

- 同 runtime
- 减少误报
- 对小问题更宽容

**优点**: AI workflow 噪声更少
**缺点**: 可能放过一些可疑配置

### strict

**适用**: 生产部署、关键 workflow

**校验内容**:

- 全部
- 最佳实践
- 性能顾虑
- 安全问题

**优点**: 最大安全性
**缺点**: 警告多,有些是误报

---

## 常见错误类型

### 1. missing_required

**含义**: 必填字段未提供

**修复方法**:

1. 用 `get_node` 查看必填字段
2. 将缺失字段添加到配置
3. 提供合适的值

**示例**:

```javascript
// 错误
{
  "type": "missing_required",
  "property": "channel",
  "message": "Channel name is required"
}

// 修复
config.channel = "#general";
```

### 2. invalid_value

**含义**: 值不在允许选项内

**修复方法**:

1. 查看错误信息中的允许值
2. 用 `get_node` 看选项
3. 更新为有效值

**示例**:

```javascript
// 错误
{
  "type": "invalid_value",
  "property": "operation",
  "message": "Operation must be one of: post, update, delete",
  "current": "send"
}

// 修复
config.operation = "post";  // 用有效的 operation
```

### 3. type_mismatch

**含义**: 字段数据类型错误

**修复方法**:

1. 查看错误信息中的期望类型
2. 转换为正确类型

**示例**:

```javascript
// 错误
{
  "type": "type_mismatch",
  "property": "limit",
  "message": "Expected number, got string",
  "current": "100"
}

// 修复
config.limit = 100;  // 数字,不是字符串
```

### 4. invalid_expression

**含义**: 表达式语法错误

**修复方法**:

1. 用 n8n Expression Syntax SKILL
2. 检查是否漏写 `{{}}` 或拼写错误
3. 验证节点/字段引用

**示例**:

```javascript
// 错误
{
  "type": "invalid_expression",
  "property": "text",
  "message": "Invalid expression: $json.name",
  "current": "$json.name"
}

// 修复
config.text = "={{$json.name}}";  // 加上 {{}}
```

### 5. invalid_reference

**含义**: 引用的节点不存在

**修复方法**:

1. 检查节点名拼写
2. 验证节点在 workflow 中存在
3. 更新引用为正确名

**示例**:

```javascript
// 错误
{
  "type": "invalid_reference",
  "property": "expression",
  "message": "Node 'HTTP Requets' does not exist",
  "current": "={{$node['HTTP Requets'].json.data}}"
}

// 修复 - 修正拼写
config.expression = "={{$node['HTTP Request'].json.data}}";
```

### 6. patchNodeField 错误

**含义**: `n8n_update_partial_workflow` 中的 `patchNodeField` 操作失败

`patchNodeField` 操作设计为严格 —— 出现错误时直接报错而不是静默继续。这能尽早捕获错误,但需要处理这些特定的错误情形。

**错误: 未找到 Find 字符串**

patch 的 `find` 值在目标字段中不存在。通常意味着内容已被修改,或 find 字符串有拼写错误。

```
patchNodeField: find string not found in field "parameters.jsCode"
```

**修复**: 再次检查字符串。用 `n8n_get_workflow` 检查当前字段值。空格与换行符很重要 —— 若不确定,用 `regex: true` 加 `\s+` 做灵活空白匹配。

**错误: 匹配歧义(多次出现)**

find 字符串在字段中出现多次。若未设置 `replaceAll: true`,会被视为歧义而拒绝。

```
patchNodeField: find string matches 3 times in field "parameters.jsCode" — set replaceAll: true to replace all, or use a more specific find string
```

**修复**: 若要替换所有出现,设置 `replaceAll: true`;或让 find 字符串更具体以只匹配目标位置。

**错误: 无效正则模式**

`regex: true` 时,模式会被验证正确性与安全性。

```
patchNodeField: invalid or unsafe regex pattern
```

**修复**: 检查正则语法。嵌套量词如 `(a+)+`、重叠分支如 `(\w|\d)+` 会被作为 ReDoS 风险拒绝。简化模式。

---

## 自动清洗系统

### 功能

**自动修复常见的 operator 结构问题**,在任何 workflow 更新时运行

**触发时机**:

- `n8n_create_workflow`
- `n8n_update_partial_workflow`
- 任何 workflow 保存操作

### 修复内容

#### 1. 二元运算符(两个值)

**运算符**: equals、notEquals、contains、notContains、greaterThan、lessThan、startsWith、endsWith

**修复**: 移除 `singleValue` 属性(二元运算符比较两个值)

**修复前**:

```javascript
{
  "type": "boolean",
  "operation": "equals",
  "singleValue": true  // ❌ 错误!
}
```

**修复后**(自动):

```javascript
{
  "type": "boolean",
  "operation": "equals"
  // singleValue 已移除 ✅
}
```

#### 2. 一元运算符(一个值)

**运算符**: isEmpty、isNotEmpty、true、false

**修复**: 添加 `singleValue: true`(一元运算符只检查单个值)

**修复前**:

```javascript
{
  "type": "boolean",
  "operation": "isEmpty"
  // 缺少 singleValue ❌
}
```

**修复后**(自动):

```javascript
{
  "type": "boolean",
  "operation": "isEmpty",
  "singleValue": true  // ✅ 已添加
}
```

#### 3. IF/Switch 元数据

**修复**: 为 IF v2.2+ 与 Switch v3.2+ 添加完整的 `conditions.options` 元数据

### 无法修复的内容

#### 1. 断开的连接

引用了不存在的节点

**解决**: 在 `n8n_update_partial_workflow` 中用 `cleanStaleConnections` 操作

#### 2. 分支数量不匹配

3 个 Switch 规则但只有 2 个输出连接

**解决**: 补缺失连接或删除多余规则

#### 3. 矛盾的损坏状态

API 返回损坏数据但拒绝更新

**解决**: 可能需要手动干预数据库

---

## 误报

### 什么是误报

技术上看"错误"但在你的用例中可接受的校验警告

### 常见误报

#### 1. "缺少错误处理"

**警告**: 未配置错误处理

**可接受场景**:

- 失败明显的简单 workflow
- 测试/开发 workflow
- 非关键通知

**应修复**: 处理重要数据的生产 workflow

#### 2. "无重试逻辑"

**警告**: 节点失败时未重试

**可接受场景**:

- 自带重试逻辑的 API
- 幂等操作
- Manual 触发 workflow

**应修复**: 不稳定的外部服务、生产自动化

#### 3. "缺少限流"

**警告**: API 调用无限流

**可接受场景**:

- 内部无限制的 API
- 低量 workflow
- 服务端有限流的 API

**应修复**: 公共 API、高量 workflow

#### 4. "无界查询"

**警告**: SELECT 无 LIMIT

**可接受场景**:

- 已知的小数据集
- 聚合查询
- 开发/测试

**应修复**: 大表的生产查询

### 减少误报

**使用 `ai-friendly` profile**:

```javascript
validate_node({
  nodeType: "nodes-base.slack",
  config: {...},
  profile: "ai-friendly"  // 误报更少
})
```

---

## 校验结果结构

### 完整响应

```javascript
{
  "valid": false,
  "errors": [
    {
      "type": "missing_required",
      "property": "channel",
      "message": "Channel name is required",
      "fix": "Provide a channel name (lowercase, no spaces)"
    }
  ],
  "warnings": [
    {
      "type": "best_practice",
      "property": "errorHandling",
      "message": "Slack API can have rate limits",
      "suggestion": "Add onError: 'continueRegularOutput'"
    }
  ],
  "suggestions": [
    {
      "type": "optimization",
      "message": "Consider using batch operations for multiple messages"
    }
  ],
  "summary": {
    "hasErrors": true,
    "errorCount": 1,
    "warningCount": 1,
    "suggestionCount": 1
  }
}
```

### 解读方法

#### 1. 检查 `valid` 字段

```javascript
if (result.valid) {
  // ✅ 配置有效
} else {
  // ❌ 有错误 - 部署前必须修复
}
```

#### 2. 优先修复错误

```javascript
result.errors.forEach(error => {
  console.log(`错误 ${error.property}: ${error.message}`);
  console.log(`修复: ${error.fix}`);
});
```

#### 3. 评估警告

```javascript
result.warnings.forEach(warning => {
  console.log(`警告: ${warning.message}`);
  console.log(`建议: ${warning.suggestion}`);
  // 决定是否需要处理
});
```

#### 4. 考虑建议

```javascript
// 可选改进
// 非必需但可能提升 workflow
```

---

## Workflow 校验

### validate_workflow(结构)

**校验整个 workflow**,而非单个节点

**检查**:

1. **节点配置** - 每个节点有效
2. **连接** - 无断引用
3. **表达式** - 语法和引用有效
4. **流程** - 逻辑工作流结构

**示例**:

```javascript
validate_workflow({
  workflow: {
    nodes: [...],
    connections: {...}
  },
  options: {
    validateNodes: true,
    validateConnections: true,
    validateExpressions: true,
    profile: "runtime"
  }
})
```

### 常见 Workflow 错误

#### 1. 断开的连接

```json
{
  "error": "Connection from 'Transform' to 'NonExistent' - target node not found"
}
```

**修复**: 删除陈旧连接或创建缺失节点

#### 2. 循环依赖

```json
{
  "error": "Circular dependency detected: Node A → Node B → Node A"
}
```

**修复**: 重组 workflow 移除循环

#### 3. 多个起始节点

```json
{
  "warning": "Multiple trigger nodes found - only one will execute"
}
```

**修复**: 删除多余触发器或拆成多个 workflow

#### 4. 孤立节点

```json
{
  "warning": "Node 'Transform' is not connected to workflow flow"
}
```

**修复**: 连接节点或删除(若不再用)

---

## 恢复策略

### 策略 1:重新开始

**适用**: 配置严重损坏

**步骤**:

1. 从 `get_node` 记下必填字段
2. 创建最小有效配置
3. 逐步添加特性
4. 每次添加后校验

### 策略 2:二分查找

**适用**: Workflow 校验通过但执行不正确

**步骤**:

1. 删掉一半节点
2. 校验并测试
3. 若工作:问题在被删节点中
4. 若失败:问题在剩余节点中
5. 重复直到隔离问题

### 策略 3:清理陈旧连接

**适用**: "Node not found" 错误

**步骤**:

```javascript
n8n_update_partial_workflow({
  id: "workflow-id",
  operations: [{
    type: "cleanStaleConnections"
  }]
})
```

### 策略 4:用自动修复

**适用**: 可自动解决的校验错误

**步骤**:

```javascript
// 预览修复(默认 - 不应用)
n8n_autofix_workflow({
  id: "workflow-id",
  applyFixes: false,
  confidenceThreshold: "medium"  // high、medium、low
})

// 审核修复,然后应用
n8n_autofix_workflow({
  id: "workflow-id",
  applyFixes: true
})
```

---

## 自动修复能力

`n8n_autofix_workflow` 工具可修复以下问题类型:

1. **expression-format** - 补全表达式遗漏的 `=` 前缀(如 `{{ $json.field }}` → `={{ $json.field }}`)
2. **typeversion-correction** - 降级不支持的 typeVersions 节点
3. **error-output-config** - 移除冲突的 onError 设置
4. **node-type-correction** - 用相似度匹配修复未知节点类型(90%+ 置信度)
5. **webhook-missing-path** - 为缺 path 配置的 webhook 节点生成 UUID
6. **typeversion-upgrade** - 智能升级到最新版节点,自动迁移
7. **version-migration** - 复杂破坏性变更的迁移指导(需手动)

**置信度等级**: `high`(90%+,可安全自动应用)、`medium`(70-89%,建议审核)、`low`(<70%,需人工审核)

```javascript
// 预览所有修复
n8n_autofix_workflow({id: "workflow-id"})

// 仅应用高置信度修复
n8n_autofix_workflow({
  id: "workflow-id",
  applyFixes: true,
  confidenceThreshold: "high"
})

// 锁定特定修复类型
n8n_autofix_workflow({
  id: "workflow-id",
  fixTypes: ["expression-format", "typeversion-upgrade"],
  applyFixes: true
})
```

**更新后指引**: 对版本升级,查看响应中的 `postUpdateGuidance` 字段获取分步迁移说明。

---

## 最佳实践

### ✅ 应该

- 每次重大修改后校验
- 完整阅读错误信息
- 迭代修复(一次一个)
- 部署前用 `runtime` profile
- 检查 `valid` 字段确认成功
- 信任自动清洗处理 operator 问题
- 不清楚要求时用 `get_node`
- 记录接受的误报

### ❌ 不应

- 激活前跳过校验
- 试图一次性修复所有错误
- 忽视错误信息
- 开发期间用 `strict` profile(太吵)
- 假设校验通过(始终检查结果)
- 手动修复自动清洗问题
- 带着未解决的错误部署
- 忽视所有警告(部分很重要!)

---

## 详细指南

完整错误目录与误报示例:

- **[ERROR_CATALOG.md](ERROR_CATALOG.md)** - 错误类型完整列表与示例
- **[FALSE_POSITIVES.md](FALSE_POSITIVES.md)** - 警告可接受的场景

---

## 小结

**要点**:

1. **校验是迭代的**(平均 2-3 轮,23s + 58s)
2. **错误必须修复**,警告可选
3. **自动清洗**自动修复 operator 结构
4. **使用 runtime profile**进行平衡校验
5. **存在误报** —— 学会识别
6. **阅读错误信息** —— 包含修复指导

**校验流程**:

1. 校验 → 读错误 → 修复 → 再次校验
2. 重复直到通过(通常 2-3 轮)
3. 评估警告并决定是否接受
4. 自信部署

**相关 SKILL 与工具**:
- n8n MCP Tools Expert - 正确使用校验工具
- n8n Expression Syntax - 修复表达式错误
- n8n Node Configuration - 理解必填字段
- `n8n_audit_instance` - 主动安全校验(硬编码 secret、无认证 webhook、缺少错误处理、数据保留)
