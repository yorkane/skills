# 数据访问模式 - JavaScript Code 节点

n8n Code 节点中数据访问模式的完整指南。

---

## 概览

Code 节点提供 4 种主要的数据访问方式:

| 模式 | 用途 | 何时使用 |
|------|------|---------|
| `$input.all()` | 所有输入 item | 批处理、聚合、过滤 |
| `$input.first()` | 仅第一个 item | API 响应、单个对象 |
| `$input.item` | 每个 item(Each Item 模式)| 逐项处理 |
| `$node` | 其他节点 | 跨节点引用 |

---

## 模式 1:`$input.all()` - 处理所有 Item

**适用**: 处理数组、批处理、聚合

### 基础用法

```javascript
const allItems = $input.all();

const processed = allItems.map(item => ({
  json: {
    ...item.json,
    processed: true,
    processedAt: new Date().toISOString()
  }
}));

return processed;
```

### 过滤 + 映射

```javascript
const allItems = $input.all();

// 过滤:仅活跃用户
const active = allItems.filter(item => item.json.active === true);

// 映射:仅保留特定字段
const simplified = active.map(item => ({
  json: {
    id: item.json.id,
    name: item.json.name,
    email: item.json.email
  }
}));

return simplified;
```

### 聚合(Reduce)

```javascript
const allItems = $input.all();

const total = allItems.reduce((sum, item) => {
  return sum + (item.json.amount || 0);
}, 0);

return [{
  json: {
    total,
    count: allItems.length,
    average: total / allItems.length
  }
}];
```

### 分组

```javascript
const allItems = $input.all();

const grouped = allItems.reduce((acc, item) => {
  const category = item.json.category || 'uncategorized';
  if (!acc[category]) {
    acc[category] = [];
  }
  acc[category].push(item.json);
  return acc;
}, {});

return [{
  json: { grouped }
}];
```

---

## 模式 2:`$input.first()` - 获取首 Item

**适用**: API 响应、单个对象、配置数据

### 基础用法

```javascript
const firstItem = $input.first();
const data = firstItem.json;

return [{
  json: {
    result: data.value,
    timestamp: new Date().toISOString()
  }
}];
```

### API 响应处理

```javascript
const response = $input.first().json;

// 提取嵌套数据
return [{
  json: {
    user: {
      id: response.data.user.id,
      name: response.data.user.name,
      email: response.data.user.email
    },
    metadata: {
      total: response.meta.total,
      page: response.meta.page
    }
  }
}];
```

### 解构访问

```javascript
const { id, name, email } = $input.first().json;

return [{
  json: {
    userId: id,
    fullName: name,
    emailAddress: email,
    processed: true
  }
}];
```

---

## 模式 3:`$input.item` - 当前 Item(Each Item 模式)

**适用**: "Run Once for Each Item" 模式中

### 基础用法

```javascript
// 在 "Run Once for Each Item" 模式
const currentItem = $input.item;

return [{
  json: {
    ...currentItem.json,
    processedAt: new Date().toISOString(),
    itemId: currentItem.json.id
  }
}];
```

### 条件处理

```javascript
const item = $input.item;

if (item.json.amount > 1000) {
  return [{
    json: {
      ...item.json,
      flagged: true,
      reason: 'High value transaction'
    }
  }];
}

return [{
  json: {
    ...item.json,
    flagged: false
  }
}];
```

---

## 模式 4:`$node` - 引用其他节点

**适用**: 需要 workflow 中其他节点的数据

### 引用节点输出

```javascript
// 获取特定节点的数据
const webhookData = $node["Webhook"].json;
const httpData = $node["HTTP Request"].json;

return [{
  json: {
    combined: {
      webhook: webhookData,
      http: httpData
    }
  }
}];
```

### 多个节点组合

```javascript
// 从多个节点聚合
const sources = {
  webhook: $node["Webhook"].json,
  api: $node["HTTP Request"].json,
  database: $node["Postgres"].json
};

return [{
  json: sources
}];
```

### 节点不存在时

```javascript
// 防御性访问
const webhookData = $node["Webhook"] ? $node["Webhook"].json : null;

if (!webhookData) {
  return [{
    json: { error: "Webhook node not found or has no data" }
  }];
}

return [{
  json: { data: webhookData }
}];
```

---

## 关键:Webhook 数据结构

**最常见错误**: Webhook 数据嵌套在 `.body` 下!

### Webhook 输出结构

```json
{
  "headers": {
    "content-type": "application/json",
    "user-agent": "..."
  },
  "params": {},
  "query": {},
  "body": {
    "name": "John",
    "email": "john@example.com",
    "message": "Hello"
  }
}
```

### 正确的 Webhook 访问

```javascript
// ❌ 错误: 返回 undefined
const name = $json.name;
const email = $json.email;

// ✅ 正确: Webhook 数据在 .body 下
const name = $json.body.name;
const email = $json.body.email;

// 通过 $input 访问
const webhookData = $input.first().json.body;
const name = webhookData.name;
```

### 跨节点引用 Webhook

```javascript
// 引用 Webhook 节点
const webhookData = $node["Webhook"].json;
const name = webhookData.body.name;  // 仍然是 .body!
const email = webhookData.body.email;
```

### 深度嵌套

```javascript
// 访问嵌套数据
const user = $json.body.user;
const userName = user.name;
const userEmail = user.contact.email;

// 单行访问
const userEmail = $json.body.user.contact.email;
```

---

## 选择正确的模式

### 决策树

```
┌─────────────────────────────────┐
│ 需要所有 item 的数据?            │
├─────────────────────────────────┤
│ 是 → $input.all()                │
│ 否 → 继续                        │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 仅需第一个 item?                 │
├─────────────────────────────────┤
│ 是 → $input.first()              │
│ 否 → 继续                        │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 在 Each Item 模式?               │
├─────────────────────────────────┤
│ 是 → $input.item                 │
│ 否 → 继续                        │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 来自其他节点?                    │
├─────────────────────────────────┤
│ 是 → $node["Name"]              │
└─────────────────────────────────┘
```

### 何时用什么

**`$input.all()`**:
- ✅ 聚合(总和、平均、计数)
- ✅ 过滤和排序
- ✅ 跨 item 比较
- ✅ 批处理

**`$input.first()`**:
- ✅ API 响应
- ✅ 配置查找
- ✅ 单对象处理

**`$input.item`**:
- ✅ 逐项独立处理
- ✅ 每个 item 不同的逻辑

**`$node["Name"]`**:
- ✅ 跨节点数据组合
- ✅ 复杂 workflow 中
- ✅ 引用早期节点输出

---

## 常见错误

### 1. 用 `$json` 而不是 `$json.body`

```javascript
// ❌ Webhook 中错误
const email = $json.email;  // undefined

// ✅ 正确
const email = $json.body.email;
```

### 2. 不处理空输入

```javascript
// ❌ 可能崩溃
const first = $input.first();
const data = first.json;  // 崩如果无输入

// ✅ 防御性
const first = $input.first();
if (!first) {
  return [{ json: { error: "No input data" } }];
}
const data = first.json;
```

### 3. 忘记 $input 是数组

```javascript
// ❌ 错误: $input 不是数组
const items = $input;  // 不是数组!

// ✅ 正确
const items = $input.all();  // 是数组
const firstItem = $input.first();  // 是单个 item
```

### 4. 在 All Items 模式用 $input.item

```javascript
// ❌ 错误: $input.item 仅用于 Each Item 模式
const current = $input.item;  // undefined!

// ✅ 在 All Items 模式用 $input.all() 或 first()
const all = $input.all();
const first = $input.first();
```

### 5. 节点名拼写错误

```javascript
// ❌ 错误: 节点名错误
const data = $node["http requets"].json;  // 找不到

// ✅ 正确: 精确匹配节点名
const data = $node["HTTP Request"].json;
```

---

## 进阶模式

### 模式 1:跨节点数据合并

```javascript
const userId = $node["Webhook"].json.body.user_id;
const userDetails = $node["User Lookup"].json;
const orders = $node["Orders"].json;

return [{
  json: {
    user: {
      id: userId,
      ...userDetails
    },
    orders: orders
  }
}];
```

### 模式 2:有回退的节点引用

```javascript
function getNodeData(nodeName) {
  return $node[nodeName] ? $node[nodeName].json : null;
}

const webhookData = getNodeData("Webhook");
const httpData = getNodeData("HTTP Request");

return [{
  json: {
    webhook: webhookData,
    http: httpData
  }
}];
```

### 模式 3:有错误处理的 First Item

```javascript
const first = $input.first();

if (!first || !first.json) {
  return [{
    json: {
      error: "No data available",
      timestamp: new Date().toISOString()
    }
  }];
}

return [{
  json: {
    data: first.json,
    processed: true
  }
}];
```

---

## 小结

**核心模式**:

1. `$input.all()` - 处理所有 item(最常用)
2. `$input.first()` - 仅第一个 item
3. `$input.item` - Each Item 模式专用
4. `$node["Name"]` - 跨节点引用

**关键点**:

- Webhook 数据**始终在 `.body` 下**
- 节点名**区分大小写**
- 用括号语法处理含空格的节点名
- 防御性检查空输入

**记住**: 选对模式可以省 50% 代码!

**相关**:

- [COMMON_PATTERNS.md](COMMON_PATTERNS.md) - 实际示例
- [ERROR_PATTERNS.md](ERROR_PATTERNS.md) - 错误防范
- [BUILTIN_FUNCTIONS.md](BUILTIN_FUNCTIONS.md) - 辅助函数
