# 错误目录

含真实示例与修复方案的 n8n 校验错误综合目录。

---

## 错误类型概览

按优先级排列的常见校验错误:

| 错误类型 | 优先级 | 严重性 | 自动修复 |
|---|---|---|---|
| missing_required | 最高 | 错误 | ❌ |
| invalid_value | 高 | 错误 | ❌ |
| type_mismatch | 中 | 错误 | ❌ |
| invalid_expression | 中 | 错误 | ❌ |
| invalid_reference | 低 | 错误 | ❌ |
| operator_structure | 最低 | 警告 | ✅ |

---

## 错误(必须修复)

### 1. missing_required

**含义**: 节点配置中未提供必填字段

**发生场景**:

- 创建新节点时未填所有必填字段
- 在不同 operation 之间复制配置
- 切换 operation 导致必填项不同

**最常见的校验错误**

#### 示例 1:Slack 频道缺失

**错误**:

```json
{
  "type": "missing_required",
  "property": "channel",
  "message": "Channel name is required",
  "node": "Slack",
  "path": "parameters.channel"
}
```

**错误配置**:

```javascript
{
  "resource": "message",
  "operation": "post"
  // 缺少: channel
}
```

**修复**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#general"  // ✅ 已加必填字段
}
```

**如何识别必填字段**:

```javascript
// 用 get_node 查看必填项
const info = get_node({
  nodeType: "nodes-base.slack"
});
// 查看标记为 "required": true 的属性
```

#### 示例 2:HTTP Request 缺 URL

**错误**:

```json
{
  "type": "missing_required",
  "property": "url",
  "message": "URL is required for HTTP Request",
  "node": "HTTP Request",
  "path": "parameters.url"
}
```

**错误配置**:

```javascript
{
  "method": "GET",
  "authentication": "none"
  // 缺少: url
}
```

**修复**:

```javascript
{
  "method": "GET",
  "authentication": "none",
  "url": "https://api.example.com/data"  // ✅ 已加
}
```

#### 示例 3:数据库查询缺连接

**错误**:

```json
{
  "type": "missing_required",
  "property": "query",
  "message": "SQL query is required",
  "node": "Postgres",
  "path": "parameters.query"
}
```

**错误配置**:

```javascript
{
  "operation": "executeQuery"
  // 缺少: query
}
```

**修复**:

```javascript
{
  "operation": "executeQuery",
  "query": "SELECT * FROM users WHERE active = true"  // ✅ 已加
}
```

#### 示例 4:条件必填字段

**错误**:

```json
{
  "type": "missing_required",
  "property": "body",
  "message": "Request body is required when sendBody is true",
  "node": "HTTP Request",
  "path": "parameters.body"
}
```

**错误配置**:

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "sendBody": true
  // 缺少: body(sendBody=true 时必填)
}
```

**修复**:

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "sendBody": true,
  "body": {
    "contentType": "json",
    "content": {
      "name": "John",
      "email": "john@example.com"
    }
  }  // ✅ 已加条件必填字段
}
```

---

### 2. invalid_value

**含义**: 提供的值不在允许选项或格式内

**发生场景**:

- 用了错误的枚举值
- operation 名拼错
- 特殊字段格式无效(email、URL、channel)

**第二常见的错误**

#### 示例 1:Operation 无效

**错误**:

```json
{
  "type": "invalid_value",
  "property": "operation",
  "message": "Operation must be one of: post, update, delete, get",
  "current": "send",
  "allowed": ["post", "update", "delete", "get"]
}
```

**错误配置**:

```javascript
{
  "resource": "message",
  "operation": "send"  // ❌ 无效 - 应为 "post"
}
```

**修复**:

```javascript
{
  "resource": "message",
  "operation": "post"  // ✅ 用有效的 operation
}
```

#### 示例 2:HTTP Method 无效

**错误**:

```json
{
  "type": "invalid_value",
  "property": "method",
  "message": "Method must be one of: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS",
  "current": "FETCH",
  "allowed": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
}
```

**错误配置**:

```javascript
{
  "method": "FETCH",  // ❌ 无效
  "url": "https://api.example.com"
}
```

**修复**:

```javascript
{
  "method": "GET",  // ✅ 用有效的 HTTP method
  "url": "https://api.example.com"
}
```

#### 示例 3:Channel 格式无效

**错误**:

```json
{
  "type": "invalid_value",
  "property": "channel",
  "message": "Channel name must start with # and be lowercase (e.g., #general)",
  "current": "General"
}
```

**错误配置**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "General"  // ❌ 格式错误
}
```

**修复**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#general"  // ✅ 格式正确
}
```

#### 示例 4:区分大小写的枚举

**错误**:

```json
{
  "type": "invalid_value",
  "property": "resource",
  "message": "Resource must be one of: channel, message, user, file",
  "current": "Message",
  "allowed": ["channel", "message", "user", "file"]
}
```

**注意**: 枚举区分大小写!

**错误配置**:

```javascript
{
  "resource": "Message",  // ❌ 大写 M
  "operation": "post"
}
```

**修复**:

```javascript
{
  "resource": "message",  // ✅ 小写
  "operation": "post"
}
```

---

### 3. type_mismatch

**含义**: 值的数据类型错误(如字符串而非数字)

**发生场景**:

- 硬编码了本该是数字的值
- 在需要字面量的地方用了表达式
- JSON 序列化问题

**常见错误**

#### 示例 1:字符串而非数字

**错误**:

```json
{
  "type": "type_mismatch",
  "property": "limit",
  "message": "Expected number, got string",
  "expected": "number",
  "current": "100"
}
```

**错误配置**:

```javascript
{
  "operation": "executeQuery",
  "query": "SELECT * FROM users",
  "limit": "100"  // ❌ 字符串
}
```

**修复**:

```javascript
{
  "operation": "executeQuery",
  "query": "SELECT * FROM users",
  "limit": 100  // ✅ 数字
}
```

#### 示例 2:数字而非字符串

**错误**:

```json
{
  "type": "type_mismatch",
  "property": "channel",
  "message": "Expected string, got number",
  "expected": "string",
  "current": 12345
}
```

**错误配置**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": 12345  // ❌ 数字(即便是 channel ID)
}
```

**修复**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#general"  // ✅ 字符串(channel 名,不是 ID)
}
```

#### 示例 3:布尔被作为字符串

**错误**:

```json
{
  "type": "type_mismatch",
  "property": "sendHeaders",
  "message": "Expected boolean, got string",
  "expected": "boolean",
  "current": "true"
}
```

**错误配置**:

```javascript
{
  "method": "GET",
  "url": "https://api.example.com",
  "sendHeaders": "true"  // ❌ 字符串 "true"
}
```

**修复**:

```javascript
{
  "method": "GET",
  "url": "https://api.example.com",
  "sendHeaders": true  // ✅ 布尔 true
}
```

#### 示例 4:对象而非数组

**错误**:

```json
{
  "type": "type_mismatch",
  "property": "tags",
  "message": "Expected array, got object",
  "expected": "array",
  "current": {"tag": "important"}
}
```

**错误配置**:

```javascript
{
  "name": "New Channel",
  "tags": {"tag": "important"}  // ❌ 对象
}
```

**修复**:

```javascript
{
  "name": "New Channel",
  "tags": ["important", "alerts"]  // ✅ 数组
}
```

---

### 4. invalid_expression

**含义**: n8n 表达式存在语法错误或无效引用

**发生场景**:

- 表达式外漏 `{{}}`
- 变量名拼错
- 引用了不存在的节点或字段
- 表达式中 JavaScript 语法无效

**中等常见**

**相关**: 完整表达式指南见 **n8n Expression Syntax** SKILL

#### 示例 1:漏写花括号

**错误**:

```json
{
  "type": "invalid_expression",
  "property": "text",
  "message": "Expressions must be wrapped in {{}}",
  "current": "$json.name"
}
```

**错误配置**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#general",
  "text": "$json.name"  // ❌ 漏 {{}}
}
```

**修复**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#general",
  "text": "={{$json.name}}"  // ✅ 已包 {{}}
}
```

#### 示例 2:节点引用无效

**错误**:

```json
{
  "type": "invalid_expression",
  "property": "value",
  "message": "Referenced node 'HTTP Requets' does not exist",
  "current": "={{$node['HTTP Requets'].json.data}}"
}
```

**错误配置**:

```javascript
{
  "field": "data",
  "value": "={{$node['HTTP Requets'].json.data}}"  // ❌ 节点名拼错
}
```

**修复**:

```javascript
{
  "field": "data",
  "value": "={{$node['HTTP Request'].json.data}}"  // ✅ 正确的节点名
}
```

#### 示例 3:属性访问无效

**错误**:

```json
{
  "type": "invalid_expression",
  "property": "text",
  "message": "Cannot access property 'user' of undefined",
  "current": "={{$json.data.user.name}}"
}
```

**错误配置**:

```javascript
{
  "text": "={{$json.data.user.name}}"  // ❌ 结构不存在
}
```

**修复**(用安全访问):

```javascript
{
  "text": "={{$json.data?.user?.name || 'Unknown'}}"  // ✅ 安全导航 + 回退
}
```

#### 示例 4:Webhook 数据访问错误

**错误**:

```json
{
  "type": "invalid_expression",
  "property": "value",
  "message": "Property 'email' not found in $json",
  "current": "={{$json.email}}"
}
```

**常见坑**: Webhook 数据在 `.body` 下!

**错误配置**:

```javascript
{
  "field": "email",
  "value": "={{$json.email}}"  // ❌ 漏 .body
}
```

**修复**:

```javascript
{
  "field": "email",
  "value": "={{$json.body.email}}"  // ✅ Webhook 数据在 .body 下
}
```

---

### 5. invalid_reference

**含义**: 配置引用了 workflow 中不存在的节点

**发生场景**:

- 节点被重命名或删除
- 节点名拼写错误
- 从其他 workflow 复制粘贴

**较少见**

#### 示例 1:引用已删除节点

**错误**:

```json
{
  "type": "invalid_reference",
  "property": "expression",
  "message": "Node 'Transform Data' does not exist in workflow",
  "referenced_node": "Transform Data"
}
```

**错误配置**:

```javascript
{
  "value": "={{$node['Transform Data'].json.result}}"  // ❌ 节点已删除
}
```

**修复**:

```javascript
// 选项 1: 更新为已存在的节点
{
  "value": "={{$node['Set'].json.result}}"
}

// 选项 2: 不需要则移除表达式
{
  "value": "default_value"
}
```

#### 示例 2:连接指向不存在的节点

**错误**:

```json
{
  "type": "invalid_reference",
  "message": "Connection references node 'Slack1' which does not exist",
  "source": "HTTP Request",
  "target": "Slack1"
}
```

**修复**: 用 `cleanStaleConnections` 操作:

```javascript
n8n_update_partial_workflow({
  id: "workflow-id",
  operations: [{
    type: "cleanStaleConnections"
  }]
})
```

#### 示例 3:重命名节点后未更新

**错误**:

```json
{
  "type": "invalid_reference",
  "property": "expression",
  "message": "Node 'Get Weather' does not exist (did you mean 'Weather API'?)",
  "referenced_node": "Get Weather",
  "suggestions": ["Weather API"]
}
```

**错误配置**:

```javascript
{
  "value": "={{$node['Get Weather'].json.temperature}}"  // ❌ 旧名字
}
```

**修复**:

```javascript
{
  "value": "={{$node['Weather API'].json.temperature}}"  // ✅ 当前名字
}
```

---

## 警告(建议修复)

### 6. best_practice

**含义**: 配置能工作但不遵循最佳实践

**严重性**: 警告(不阻塞执行)

**可接受场景**: 开发、测试、简单 workflow

**应修复场景**: 生产 workflow、关键操作

#### 示例 1:缺错误处理

**警告**:

```json
{
  "type": "best_practice",
  "property": "onError",
  "message": "Slack API can have rate limits and connection issues",
  "suggestion": "Add error handling: onError: 'continueRegularOutput'"
}
```

**当前配置**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#alerts"
  // 无错误处理 ⚠️
}
```

**推荐修复**:

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#alerts",
  "continueOnFail": true,
  "retryOnFail": true,
  "maxTries": 3
}
```

#### 示例 2:无重试逻辑

**警告**:

```json
{
  "type": "best_practice",
  "property": "retryOnFail",
  "message": "External API calls should retry on failure",
  "suggestion": "Add retryOnFail: true, maxTries: 3, waitBetweenTries: 1000"
}
```

**可忽略场景**: 幂等操作、自带重试逻辑的 API

**应修复场景**: 不稳定的外部服务、生产自动化

---

### 7. deprecated

**含义**: 用了旧 API 版本或废弃特性

**严重性**: 警告(仍能用但未来可能失效)

**何时修复**: 始终(迟早要修)

#### 示例 1:旧 typeVersion

**警告**:

```json
{
  "type": "deprecated",
  "property": "typeVersion",
  "message": "typeVersion 1 is deprecated for Slack node, use version 2",
  "current": 1,
  "recommended": 2
}
```

**修复**:

```javascript
{
  "type": "n8n-nodes-base.slack",
  "typeVersion": 2,  // ✅ 已更新
  // 可能需要适配新版本的配置
}
```

---

### 8. performance

**含义**: 配置可能导致性能问题

**严重性**: 警告

**何时修复**: 高量 workflow、大数据集

#### 示例 1:无界查询

**警告**:

```json
{
  "type": "performance",
  "property": "query",
  "message": "SELECT without LIMIT can return massive datasets",
  "suggestion": "Add LIMIT clause or use pagination"
}
```

**当前**:

```sql
SELECT * FROM users WHERE active = true
```

**修复**:

```sql
SELECT * FROM users WHERE active = true LIMIT 1000
```

---

## 自动清洗修复

### 9. operator_structure

**含义**: IF/Switch operator 结构问题

**严重性**: 警告

**自动修复**: ✅ 是 —— 在 workflow 保存时自动修复

**少见**(基本自动修复)

#### 自动修复:二元运算符

**之前**(你这样创建):

```javascript
{
  "type": "boolean",
  "operation": "equals",
  "singleValue": true  // ❌ 二元运算符不该有
}
```

**之后**(自动清洗修复):

```javascript
{
  "type": "boolean",
  "operation": "equals"
  // singleValue 已移除 ✅
}
```

**你无需任何操作** —— 保存时自动修复!

#### 自动修复:一元运算符

**之前**:

```javascript
{
  "type": "boolean",
  "operation": "isEmpty"
  // 缺 singleValue ❌
}
```

**之后**:

```javascript
{
  "type": "boolean",
  "operation": "isEmpty",
  "singleValue": true  // ✅ 已自动添加
}
```

**你应该做的**: 信任自动清洗,不要手动修复!

---

## 恢复模式

### 模式 1:渐进式校验

**问题**: 一次出现太多错误

**解决**:

```javascript
// Step 1: 最小有效配置
let config = {
  resource: "message",
  operation: "post",
  channel: "#general",
  text: "Hello"
};

validate_node({nodeType: "nodes-base.slack", config, profile: "runtime"});
// ✅ 通过

// Step 2: 逐个添加特性
config.attachments = [...];
validate_node({nodeType: "nodes-base.slack", config, profile: "runtime"});

config.blocks = [...];
validate_node({nodeType: "nodes-base.slack", config, profile: "runtime"});
```

### 模式 2:错误分诊

**问题**: 多个错误

**解决**:

```javascript
const result = validate_node({...});

// 1. 修复错误(必须修)
result.errors.forEach(error => {
  console.log(`必须修复: ${error.property} - ${error.message}`);
});

// 2. 评估警告(建议修)
result.warnings.forEach(warning => {
  console.log(`建议修复: ${warning.property} - ${warning.message}`);
});

// 3. 考虑建议(可选)
result.suggestions.forEach(sug => {
  console.log(`可选: ${sug.message}`);
});
```

### 模式 3:用 get_node

**问题**: 不知道必填什么

**解决**:

```javascript
// 配置前,先查要求
const info = get_node({
  nodeType: "nodes-base.slack"
});

// 找必填字段
info.properties.forEach(prop => {
  if (prop.required) {
    console.log(`必填: ${prop.name} (${prop.type})`);
  }
});
```

---

## 小结

**最常见错误**:

1. `missing_required`(45%) - 始终查 get_node
2. `invalid_value`(28%) - 检查允许值
3. `type_mismatch`(12%) - 用正确数据类型
4. `invalid_expression`(8%) - 用 Expression Syntax SKILL
5. `invalid_reference`(5%) - 清理陈旧连接

**自动修复**:

- `operator_structure` - 信任自动清洗!

**相关 SKILL**:

- **[SKILL.md](SKILL.md)** - 主校验指南
- **[FALSE_POSITIVES.md](FALSE_POSITIVES.md)** - 何时忽略警告
- **n8n Expression Syntax** - 修复表达式错误
- **n8n MCP Tools Expert** - 正确使用校验工具
