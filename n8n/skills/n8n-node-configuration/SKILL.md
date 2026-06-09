---
name: n8n-node-configuration
description: 感知 operation 的节点配置指导。配置节点、理解属性依赖、确定必填字段、在 `get_node` 的 detail 级别间选择、或学习按节点类型分类的常见配置模式时使用。设置节点参数时应始终使用本 SKILL —— 它解释每个 operation 需要哪些字段,`displayOptions` 如何控制字段可见性,以及何时用 `patchNodeField` 做定点编辑而非整节点更新。
---

# n8n 节点配置

带属性依赖的 operation 感知配置专家指南。

---

## 配置哲学

**渐进披露(progressive disclosure)**: 从最小化开始,按需增加复杂度

配置最佳实践:

- `get_node` + `detail: "standard"` 是最常用的发现模式
- 配置编辑间隔平均 56 秒
- 95% 用例用 1-2K tokens 响应即可覆盖

**要点**: 大多数配置只需要 standard detail,而非完整 schema!

---

## 核心概念

### 1. Operation 感知配置

**并非所有字段总是必填** —— 取决于 operation!

**示例**: Slack 节点

```javascript
// operation='post' 时
{
  "resource": "message",
  "operation": "post",
  "channel": "#general",  // post 必填
  "text": "Hello!"        // post 必填
}

// operation='update' 时
{
  "resource": "message",
  "operation": "update",
  "messageId": "123",     // update 必填(不同!)
  "text": "Updated!"      // update 必填
  // channel 对 update 不是必填
}
```

**关键**: resource + operation 决定哪些字段必填!

### 2. 属性依赖

**字段会基于其他字段的值显示/隐藏**

**示例**: HTTP Request 节点

```javascript
// method='GET' 时
{
  "method": "GET",
  "url": "https://api.example.com"
  // sendBody 不显示(GET 没有 body)
}

// method='POST' 时
{
  "method": "POST",
  "url": "https://api.example.com",
  "sendBody": true,       // 现在出现!
  "body": {               // sendBody=true 时必填
    "contentType": "json",
    "content": {...}
  }
}
```

**机制**: `displayOptions` 控制字段可见性

### 3. 渐进式发现

**使用合适的 detail 级别**:

1. **get_node({detail: "standard"})** - 默认
   - 快速概览(~1-2K tokens)
   - 必填字段 + 常用选项
   - **优先使用** —— 覆盖 95% 需求

2. **get_node({mode: "search_properties", propertyQuery: "..."})**(用于查找特定字段)
   - 按名字查找属性
   - 查找 auth、body、headers 等时使用

3. **get_node({detail: "full"})**(完整 schema)
   - 全部属性(~3-8K tokens)
   - 仅在 standard detail 不够时使用

---

## 配置工作流

### 标准流程

```
1. 确定节点类型与 operation
   ↓
2. 用 get_node(默认 standard detail)
   ↓
3. 配置必填字段
   ↓
4. 校验配置
   ↓
5. 若字段不清 → get_node({mode: "search_properties"})
   ↓
6. 按需添加可选字段
   ↓
7. 再次校验
   ↓
8. 部署
```

### 示例:配置 HTTP Request

**Step 1**: 明确需求

```javascript
// 目标: POST JSON 到 API
```

**Step 2**: 获取节点信息

```javascript
const info = get_node({
  nodeType: "nodes-base.httpRequest"
});

// 返回: method、url、sendBody、body、authentication 必填/可选
```

**Step 3**: 最小配置

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "authentication": "none"
}
```

**Step 4**: 校验

```javascript
validate_node({
  nodeType: "nodes-base.httpRequest",
  config,
  profile: "runtime"
});
// → 错误: "sendBody required for POST"
```

**Step 5**: 补必填字段

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "authentication": "none",
  "sendBody": true
}
```

**Step 6**: 再次校验

```javascript
validate_node({...});
// → 错误: "body required when sendBody=true"
```

**Step 7**: 完成配置

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/create",
  "authentication": "none",
  "sendBody": true,
  "body": {
    "contentType": "json",
    "content": {
      "name": "={{$json.name}}",
      "email": "={{$json.email}}"
    }
  }
}
```

**Step 8**: 最终校验

```javascript
validate_node({...});
// → 通过!✅
```

---

## get_node Detail 级别

### Standard Detail(默认 - 使用它!)

**✅ 开始配置时使用**

```javascript
get_node({
  nodeType: "nodes-base.slack"
});
// detail="standard" 是默认值
```

**返回**(~1-2K tokens):

- 必填字段
- 常用选项
- operation 列表
- 元数据

**使用**: 95% 配置需求

### Full Detail(谨慎使用)

**✅ Standard 不够时**

```javascript
get_node({
  nodeType: "nodes-base.slack",
  detail: "full"
});
```

**返回**(~3-8K tokens):

- 完整 schema
- 全部属性
- 全部嵌套选项

**警告**: 响应大,仅在 standard 不足时使用

### Search Properties Mode

**✅ 查找特定字段时**

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "search_properties",
  propertyQuery: "auth"
});
```

**使用**: 查找 auth、headers、body 字段等

### 决策树

```
┌─────────────────────────────────┐
│ 开始新节点配置?                  │
├─────────────────────────────────┤
│ 是 → get_node (standard)        │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Standard 已含所需?               │
├─────────────────────────────────┤
│ 是 → 用它配置                    │
│ 否 → 继续                        │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 查找特定字段?                    │
├─────────────────────────────────┤
│ 是 → search_properties mode     │
│ 否 → 继续                        │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 仍需更多细节?                    │
├─────────────────────────────────┤
│ 是 → get_node({detail: "full"}) │
└─────────────────────────────────┘
```

---

## 属性依赖深入

### displayOptions 机制

**字段有可见性规则**:

```javascript
{
  "name": "body",
  "displayOptions": {
    "show": {
      "sendBody": [true],
      "method": ["POST", "PUT", "PATCH"]
    }
  }
}
```

**翻译**: "body" 字段在以下条件显示:

- `sendBody = true` 且
- `method = POST、PUT 或 PATCH`

### 常见依赖模式

#### 模式 1:布尔开关

**示例**: HTTP Request `sendBody`

```javascript
// sendBody 控制 body 可见性
{
  "sendBody": true   // → body 字段出现
}
```

#### 模式 2:Operation 切换

**示例**: Slack `resource/operation`

```javascript
// 不同 operation → 不同字段
{
  "resource": "message",
  "operation": "post"
  // → 显示: channel、text、attachments 等
}

{
  "resource": "message",
  "operation": "update"
  // → 显示: messageId、text(不同字段!)
}
```

#### 模式 3:类型选择

**示例**: IF 节点 conditions

```javascript
{
  "type": "string",
  "operation": "contains"
  // → 显示: value1, value2
}

{
  "type": "boolean",
  "operation": "equals"
  // → 显示: value1, value2, 不同 operators
}
```

### 查找属性依赖

**用 get_node + search_properties mode**:

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "search_properties",
  propertyQuery: "body"
});

// 返回属性路径匹配 "body" 含说明
```

**或用 full detail 获取完整 schema**:

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  detail: "full"
});

// 返回含 displayOptions 规则的完整 schema
```

**使用时机**: 校验失败且不理解为何字段缺失/必填时

---

## 常见节点模式

### 模式 1:Resource/Operation 节点

**示例**: Slack、Google Sheets、Airtable

**结构**:

```javascript
{
  "resource": "<entity>",      // 什么类型
  "operation": "<action>",     // 对它做什么
  // ... operation 特定字段
}
```

**配置方法**:

1. 选 resource
2. 选 operation
3. 用 get_node 看 operation 特定要求
4. 配置必填字段

### 模式 2:HTTP 节点

**示例**: HTTP Request、Webhook

**结构**:

```javascript
{
  "method": "<HTTP_METHOD>",
  "url": "<endpoint>",
  "authentication": "<type>",
  // ... method 特定字段
}
```

**依赖**:

- POST/PUT/PATCH → sendBody 可用
- `sendBody=true` → body 必填
- `authentication != "none"` → credentials 必填

### 模式 3:数据库节点

**示例**: Postgres、MySQL、MongoDB

**结构**:

```javascript
{
  "operation": "<query|insert|update|delete>",
  // ... operation 特定字段
}
```

**依赖**:

- `operation="executeQuery"` → query 必填
- `operation="insert"` → table + values 必填
- `operation="update"` → table + values + where 必填

### 模式 4:条件逻辑节点

**示例**: IF、Switch、Merge

**结构**:

```javascript
{
  "conditions": {
    "<type>": [
      {
        "operation": "<operator>",
        "value1": "...",
        "value2": "..."  // 仅二元运算符
      }
    ]
  }
}
```

**依赖**:

- 二元运算符(equals、contains 等)→ value1 + value2
- 一元运算符(isEmpty、isNotEmpty)→ 仅 value1 + `singleValue: true`

---

## Operation 特定配置

### Slack 节点示例

#### 发消息

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#general",      // 必填
  "text": "Hello!",           // 必填
  "attachments": [],          // 可选
  "blocks": []                // 可选
}
```

#### 更新消息

```javascript
{
  "resource": "message",
  "operation": "update",
  "messageId": "1234567890",  // 必填(与 post 不同!)
  "text": "Updated!",         // 必填
  "channel": "#general"       // 可选(可推断)
}
```

#### 创建频道

```javascript
{
  "resource": "channel",
  "operation": "create",
  "name": "new-channel",      // 必填
  "isPrivate": false          // 可选
  // 注意: text 对此 operation 非必填
}
```

### HTTP Request 节点示例

#### GET 请求

```javascript
{
  "method": "GET",
  "url": "https://api.example.com/users",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "httpHeaderAuth",
  "sendQuery": true,                    // 可选
  "queryParameters": {                  // sendQuery=true 时显示
    "parameters": [
      {
        "name": "limit",
        "value": "100"
      }
    ]
  }
}
```

#### POST JSON

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/users",
  "authentication": "none",
  "sendBody": true,                     // POST 必填
  "body": {                             // sendBody=true 时必填
    "contentType": "json",
    "content": {
      "name": "John Doe",
      "email": "john@example.com"
    }
  }
}
```

### IF 节点示例

#### 字符串比较(二元)

```javascript
{
  "conditions": {
    "string": [
      {
        "value1": "={{$json.status}}",
        "operation": "equals",
        "value2": "active"              // 二元: 需要 value2
      }
    ]
  }
}
```

#### 空检查(一元)

```javascript
{
  "conditions": {
    "string": [
      {
        "value1": "={{$json.email}}",
        "operation": "isEmpty",
        // 无 value2 - 一元运算符
        "singleValue": true             // 由自动清洗添加
      }
    ]
  }
}
```

---

## 处理条件必填

### 示例:HTTP Request Body

**场景**: body 字段必填,但仅在特定情况

**规则**:

```
body 在以下情况必填:
  - sendBody = true 且
  - method IN (POST、PUT、PATCH、DELETE)
```

**如何发现**:

```javascript
// 选项 1: 读校验错误
validate_node({...});
// 错误: "body required when sendBody=true"

// 选项 2: 搜索该属性
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "search_properties",
  propertyQuery: "body"
});
// 显示: body 属性含 displayOptions 规则

// 选项 3: 试最小配置再迭代
// 先不带 body,校验会告诉你是否需要
```

### 示例:IF 节点 singleValue

**场景**: singleValue 属性在一元运算符时出现

**规则**:

```
singleValue 应为 true 当:
  - operation IN (isEmpty、isNotEmpty、true、false)
```

**好消息**: 自动清洗会自动修复!

**手动检查**:

```javascript
get_node({
  nodeType: "nodes-base.if",
  detail: "full"
});
// 显示含 operator 特定规则的完整 schema
```

---

## 节点特定配置说明

### SplitInBatches v3

```javascript
{
  "batchSize": 100,  // 每批 item 数
  "options": {}
}
```

**输出连接**:

- `main[0]`(done) → 连接下游处理(先加 Limit 1)
- `main[1]`(each batch) → 连接循环体,然后回连到 SplitInBatches 输入

详见 n8n Workflow Patterns SKILL 中的循环与嵌套循环模式。

### Google Sheets 节点

**逐项执行**: 每个 input item 触发一次独立 API 调用。若有 100 个 item 并用 Google Sheets "Append Row" 节点,会产生 100 次 API 调用。要批量写入,先在 Code 节点中聚合 item,再用单次 HTTP Request 调用 Sheets API。

**公式列**: 绝不要在含公式列的 sheet 上用 `append` —— 会覆盖公式。改用 HTTP Request 调用 Google Sheets API `values.update`(PUT)方法,配 `googleApi` 凭据。

---

## 配置反模式

### ❌ 不要:过度预配置

**错误**:

```javascript
// 添加所有可能字段
{
  "method": "GET",
  "url": "...",
  "sendQuery": false,
  "sendHeaders": false,
  "sendBody": false,
  "timeout": 10000,
  "ignoreResponseCode": false,
  // ... 还有 20 个可选字段
}
```

**正确**:

```javascript
// 从最小化开始
{
  "method": "GET",
  "url": "...",
  "authentication": "none"
}
// 只在需要时加字段
```

### ❌ 不要:跳过校验

**错误**:

```javascript
// 配置后不校验就部署
const config = {...};
n8n_update_partial_workflow({...});  // YOLO
```

**正确**:

```javascript
// 部署前校验
const config = {...};
const result = validate_node({...});
if (result.valid) {
  n8n_update_partial_workflow({...});
}
```

### ❌ 不要:忽视 operation 上下文

**错误**:

```javascript
// 同样配置用于所有 Slack operation
{
  "resource": "message",
  "operation": "post",
  "channel": "#general",
  "text": "..."
}

// 然后切到 update 但不改配置
{
  "resource": "message",
  "operation": "update",  // 改了
  "channel": "#general",  // update 用错了字段!
  "text": "..."
}
```

**正确**:

```javascript
// 改 operation 时检查要求
get_node({
  nodeType: "nodes-base.slack"
});
// 看 update operation 需要什么(messageId,不是 channel)
```

---

## 用 patchNodeField 做定点编辑

需要编辑节点内的特定字符串(而非替换整个字段)时,用 `n8n_update_partial_workflow` 中的 `patchNodeField`。尤其适合:

- 编辑 Code 节点中的代码,无需重传整个代码块
- 更新大段 HTML 邮件模板中的 URL 或文本
- 修复 JSON body 或长文本字段中的拼写错误

```javascript
// 替换整个 jsCode 字段
n8n_update_partial_workflow({
  id: "wf-123",
  operations: [{
    type: "patchNodeField",
    nodeName: "Code",
    fieldPath: "parameters.jsCode",
    patches: [{find: "const limit = 10;", replace: "const limit = 50;"}]
  }]
})
```

`patchNodeField` 是严格的 —— 若 find 字符串未找到或匹配多次(除非 `replaceAll: true`),会直接报错。这能防止配置更新中的意外静默失败。完整语法与示例见 n8n MCP Tools Expert SKILL。

---

## 最佳实践

### 应该

1. **从 get_node(standard detail)开始**
   - 约 1-2K tokens 响应
   - 覆盖 95% 配置需求
   - 默认 detail 级别

2. **迭代校验**
   - 配置 → 校验 → 修复 → 重复
   - 平均 2-3 轮是正常的
   - 仔细阅读校验错误

3. **卡住时用 search_properties mode**
   - 字段似乎缺失时搜索
   - 理解字段可见性控制
   - `get_node({mode: "search_properties", propertyQuery: "..."})`

4. **尊重 operation 上下文**
   - 不同 operation = 不同要求
   - 改 operation 时始终看 get_node
   - 不要假设配置可移植

5. **信任自动清洗**
   - Operator 结构会自动修复
   - 不要手动增删 singleValue
   - IF/Switch 元数据在保存时添加

### ❌ 不要

1. **直接跳到 detail="full"**
   - 先试 standard detail
   - 仅在需要时升级
   - 完整 schema 是 3-8K tokens

2. **盲目配置**
   - 部署前始终校验
   - 理解为何字段必填
   - 对条件字段用 search_properties

3. **不理解就复制配置**
   - 不同 operation 需要不同字段
   - 复制后校验
   - 适配新上下文

4. **手动修复自动清洗问题**
   - 让自动清洗处理 operator 结构
   - 聚焦业务逻辑
   - 保存让系统修复结构

---

## 详细参考

针对特定主题的完整指南:

- **[DEPENDENCIES.md](DEPENDENCIES.md)** - 属性依赖与 displayOptions 深入
- **[OPERATION_PATTERNS.md](OPERATION_PATTERNS.md)** - 按节点类型分类的常见配置模式

---

## 小结

**配置策略**:

1. 从 `get_node` 开始(默认 standard detail)
2. 为 operation 配置必填字段
3. 校验配置
4. 卡住时搜索属性
5. 迭代到通过(平均 2-3 轮)
6. 自信部署

**关键原则**:

- **Operation 感知**: 不同 operation = 不同要求
- **渐进披露**: 从最小化开始,按需扩展
- **依赖感知**: 理解字段可见性规则
- **校验驱动**: 让校验引导配置

**相关 SKILL**:

- **n8n MCP Tools Expert** - 正确使用发现工具
- **n8n Validation Expert** - 解读校验错误
- **n8n Expression Syntax** - 配置表达式字段
- **n8n Workflow Patterns** - 用正确配置应用模式
