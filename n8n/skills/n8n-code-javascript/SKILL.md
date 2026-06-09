---
name: n8n-code-javascript
description: 在 n8n Code 节点写 JavaScript。写 n8n 中的 JavaScript、使用 $input/$json/$node 语法、用 $helpers 发 HTTP 请求、用 DateTime 处理日期、排查 Code 节点错误、在 Code 节点 mode 间选择、或在 n8n 中做任何自定义数据转换时使用。workflow 需 Code 节点时(数据聚合、过滤、API 调用、格式转换、批处理逻辑或任何自定义 JavaScript)应始终用本 SKILL。覆盖 SplitInBatches 循环模式、跨迭代数据、pairedItem、真实生产模式。
---

# JavaScript Code 节点

n8n Code 节点中写 JavaScript 代码的专家指南。

---

## 快速开始

```javascript
// Code 节点基础模板
const items = $input.all();

// 处理数据
const processed = items.map(item => ({
  json: {
    ...item.json,
    processed: true,
    timestamp: new Date().toISOString()
  }
}));

return processed;
```

### 核心规则

1. **选择 "Run Once for All Items" 模式**(多数场景推荐)
2. **数据访问**: `$input.all()`、`$input.first()`、或 `$input.item`
3. **关键**: 必须返回 `[{json: {...}}]` 格式
4. **关键**: Webhook 数据在 `$json.body` 下(不是 `$json` 直接)
5. **可用内置函数**: `$helpers.httpRequest()`(无 auth)、`DateTime`(Luxon)、`$jmespath()`。**不可用**: `$helpers.httpRequestWithAuthentication`、`$env`(当 `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`)、`require()`(除非白名单)

---

## Mode 选择指南

Code 节点提供两种执行模式,按用例选择:

### Run Once for All Items(推荐 - 默认)

**适用**: 95% 用例

- **工作方式**: 代码**只执行一次**,与输入数量无关
- **数据访问**: `$input.all()` 或 `items` 数组
- **适用**: 聚合、过滤、批处理、转换、带所有数据的 API 调用
- **性能**: 多 item 时更快(单次执行)

```javascript
// 示例: 计算所有 item 的总和
const allItems = $input.all();
const total = allItems.reduce((sum, item) => sum + (item.json.amount || 0), 0);

return [{
  json: {
    total,
    count: allItems.length,
    average: total / allItems.length
  }
}];
```

**适用场景**:

- ✅ 跨数据集比较 item
- ✅ 计算总数、平均值、统计
- ✅ 排序或排名 item
- ✅ 去重
- ✅ 构建聚合报告
- ✅ 合并多 item 的数据

### Run Once for Each Item

**适用**: 仅特定场景

- **工作方式**: 代码对每个输入 item **独立**执行
- **数据访问**: `$input.item` 或 `$item`
- **适用**: 项特定逻辑、独立操作、逐项校验
- **性能**: 大数据集时较慢(多次执行)

```javascript
// 示例: 给每个 item 加处理时间戳
const item = $input.item;

return [{
  json: {
    ...item.json,
    processed: true,
    processedAt: new Date().toISOString()
  }
}];
```

**适用场景**:

- ✅ 每项需独立 API 调用
- ✅ 不同错误处理的逐项校验
- ✅ 基于 item 属性的项特定转换
- ✅ 业务逻辑要求 item 单独处理

**决策捷径**:

- **需要看多个 item?** → 用 "All Items" 模式
- **每项完全独立?** → 用 "Each Item" 模式
- **不确定?** → 用 "All Items" 模式(可在内部循环)

---

## 数据访问模式

### 模式 1:`$input.all()` - 最常用

**适用**: 处理数组、批操作、聚合

```javascript
// 获取前序节点所有 item
const allItems = $input.all();

// 按需 filter、map、reduce
const valid = allItems.filter(item => item.json.status === 'active');
const mapped = valid.map(item => ({
  json: {
    id: item.json.id,
    name: item.json.name
  }
}));

return mapped;
```

### 模式 2:`$input.first()` - 非常常用

**适用**: 处理单个对象、API 响应、先进先出

```javascript
// 仅取首项
const firstItem = $input.first();
const data = firstItem.json;

return [{
  json: {
    result: processData(data),
    processedAt: new Date().toISOString()
  }
}];
```

### 模式 3:`$input.item` - 仅 Each Item 模式

**适用**: 在 "Run Once for Each Item" 模式中

```javascript
// 循环中当前 item(仅 Each Item 模式)
const currentItem = $input.item;

return [{
  json: {
    ...currentItem.json,
    itemProcessed: true
  }
}];
```

### 模式 4:`$node` - 引用其他节点

**适用**: 需要 workflow 中特定节点的数据

```javascript
// 获取特定节点的输出
const webhookData = $node["Webhook"].json;
const httpData = $node["HTTP Request"].json;

return [{
  json: {
    combined: {
      webhook: webhookData,
      api: httpData
    }
  }
}];
```

**详见**: [DATA_ACCESS.md](DATA_ACCESS.md) 完整指南

---

## 关键:Webhook 数据结构

**最常见错误**: Webhook 数据嵌套在 `.body` 下

```javascript
// ❌ 错误 - 会返回 undefined
const name = $json.name;
const email = $json.email;

// ✅ 正确 - Webhook 数据在 .body 下
const name = $json.body.name;
const email = $json.body.email;

// 或用 $input
const webhookData = $input.first().json.body;
const name = webhookData.name;
```

**原因**: Webhook 节点把所有请求数据放在 `body` 属性下,包括 POST 数据、query 参数、JSON 负载。

**详见**: [DATA_ACCESS.md](DATA_ACCESS.md) 完整 webhook 结构

---

## 返回格式要求

**关键规则**: 始终返回含 `json` 属性的对象数组

### 正确的返回格式

```javascript
// ✅ 单结果
return [{
  json: {
    field1: value1,
    field2: value2
  }
}];

// ✅ 多结果
return [
  {json: {id: 1, data: 'first'}},
  {json: {id: 2, data: 'second'}}
];

// ✅ 转换后的数组
const transformed = $input.all()
  .filter(item => item.json.valid)
  .map(item => ({
    json: {
      id: item.json.id,
      processed: true
    }
  }));
return transformed;

// ✅ 空结果(无数据返回时)
return [];

// ✅ 条件返回
if (shouldProcess) {
  return [{json: processedData}];
} else {
  return [];
}
```

### 错误的返回格式

```javascript
// ❌ 错误: 无数组包裹的对象
return {
  json: {field: value}
};

// ❌ 错误: 无 json 包裹的数组
return [{field: value}];

// ❌ 错误: 纯字符串
return "processed";

// ❌ 错误: 无映射的原始数据
return $input.all();  // 缺 .map()

// ❌ 错误: 结构不完整
return [{data: value}];  // 应为 {json: value}
```

**为何重要**: 下游节点期望数组格式。错误格式会导致 workflow 执行失败。

**详见**: [ERROR_PATTERNS.md](ERROR_PATTERNS.md) #3 详细错误解决方案

---

## 常见模式概览

基于生产 workflow,以下是最有用的模式:

### 1. 多源数据聚合

合并来自多个 API、webhook 或节点的数据

```javascript
const allItems = $input.all();
const results = [];

for (const item of allItems) {
  const sourceName = item.json.name || 'Unknown';
  // 解析源特定结构
  if (sourceName === 'API1' && item.json.data) {
    results.push({
      json: {
        title: item.json.data.title,
        source: 'API1'
      }
    });
  }
}

return results;
```

### 2. 用正则过滤

从文本中提取模式、提及、关键字

```javascript
const pattern = /\b([A-Z]{2,5})\b/g;
const matches = {};

for (const item of $input.all()) {
  const text = item.json.text;
  const found = text.match(pattern);

  if (found) {
    found.forEach(match => {
      matches[match] = (matches[match] || 0) + 1;
    });
  }
}

return [{json: {matches}}];
```

### 3. 数据转换与丰富

映射字段、规范化格式、加计算字段

```javascript
const items = $input.all();

return items.map(item => {
  const data = item.json;
  const nameParts = data.name.split(' ');

  return {
    json: {
      first_name: nameParts[0],
      last_name: nameParts.slice(1).join(' '),
      email: data.email,
      created_at: new Date().toISOString()
    }
  };
});
```

### 4. Top N 过滤与排名

排序并限制结果

```javascript
const items = $input.all();

const topItems = items
  .sort((a, b) => (b.json.score || 0) - (a.json.score || 0))
  .slice(0, 10);

return topItems.map(item => ({json: item.json}));
```

### 5. 聚合与报告

求和、计数、分组

```javascript
const items = $input.all();
const total = items.reduce((sum, item) => sum + (item.json.amount || 0), 0);

return [{
  json: {
    total,
    count: items.length,
    average: total / items.length,
    timestamp: new Date().toISOString()
  }
}];
```

**详见**: [COMMON_PATTERNS.md](COMMON_PATTERNS.md) 10 个详细生产模式

---

## 错误防范 - Top 5 错误

### #1:代码为空或缺 return(最常见)

```javascript
// ❌ 错误: 无 return
const items = $input.all();
// ... 处理代码 ...
// 忘记 return!

// ✅ 正确: 始终返回数据
const items = $input.all();
// ... 处理 ...
return items.map(item => ({json: item.json}));
```

### #2:表达式语法混淆

```javascript
// ❌ 错误: 在代码中用 n8n 表达式语法
const value = "{{ $json.field }}";

// ✅ 正确: 用 JavaScript 模板字面量
const value = `${$json.field}`;

// ✅ 正确: 直接访问
const value = $input.first().json.field;
```

### #3:返回包裹错误

```javascript
// ❌ 错误: 返回对象而非数组
return {json: {result: 'success'}};

// ✅ 正确: 必须有数组包裹
return [{json: {result: 'success'}}];
```

### #4:缺少空值检查

```javascript
// ❌ 错误: 字段不存在时崩溃
const value = item.json.user.email;

// ✅ 正确: 用可选链安全访问
const value = item.json?.user?.email || 'no-email@example.com';

// ✅ 正确: 守卫子句
if (!item.json.user) {
  return [];
}
const value = item.json.user.email;
```

### #5:Webhook body 嵌套

```javascript
// ❌ 错误: 直接访问 webhook 数据
const email = $json.email;

// ✅ 正确: Webhook 数据在 .body 下
const email = $json.body.email;
```

**详见**: [ERROR_PATTERNS.md](ERROR_PATTERNS.md) 完整错误指南

---

## 内置函数与辅助

### `$helpers.httpRequest()`

在代码中发 HTTP 请求:

```javascript
const response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/data',
  headers: {
    'Authorization': 'Bearer token',
    'Content-Type': 'application/json'
  }
});

return [{json: {data: response}}];
```

### `DateTime`(Luxon)

日期时间操作:

```javascript
// 当前时间
const now = DateTime.now();

// 格式化日期
const formatted = now.toFormat('yyyy-MM-dd');
const iso = now.toISO();

// 日期运算
const tomorrow = now.plus({days: 1});
const lastWeek = now.minus({weeks: 1});

return [{
  json: {
    today: formatted,
    tomorrow: tomorrow.toFormat('yyyy-MM-dd')
  }
}];
```

### `$jmespath()`

查询 JSON 结构:

```javascript
const data = $input.first().json;

// 过滤数组
const adults = $jmespath(data, 'users[?age >= `18`]');

// 提取字段
const names = $jmespath(data, 'users[*].name');

return [{json: {adults, names}}];
```

**详见**: [BUILTIN_FUNCTIONS.md](BUILTIN_FUNCTIONS.md) 完整参考

---

## 最佳实践

### 1. 始终校验输入数据

```javascript
const items = $input.all();

// 检查数据是否存在
if (!items || items.length === 0) {
  return [];
}

// 校验结构
if (!items[0].json) {
  return [{json: {error: 'Invalid input format'}}];
}

// 继续处理...
```

### 2. 用 try-catch 处理错误

```javascript
try {
  const response = await $helpers.httpRequest({
    url: 'https://api.example.com/data'
  });

  return [{json: {success: true, data: response}}];
} catch (error) {
  return [{
    json: {
      success: false,
      error: error.message
    }
  }];
}
```

### 3. 优先用数组方法而非循环

```javascript
// ✅ 良好: 函数式
const processed = $input.all()
  .filter(item => item.json.valid)
  .map(item => ({json: {id: item.json.id}}));

// ❌ 较慢: 手动循环
const processed = [];
for (const item of $input.all()) {
  if (item.json.valid) {
    processed.push({json: {id: item.json.id}});
  }
}
```

### 4. 早过滤,晚处理

```javascript
// ✅ 良好: 先过滤以减少处理量
const processed = $input.all()
  .filter(item => item.json.status === 'active')  // 先减数据集
  .map(item => expensiveTransformation(item));  // 再转换

// ❌ 浪费: 全转换再过滤
const processed = $input.all()
  .map(item => expensiveTransformation(item))  // 浪费 CPU
  .filter(item => item.json.status === 'active');
```

### 5. 用描述性变量名

```javascript
// ✅ 良好: 意图清晰
const activeUsers = $input.all().filter(item => item.json.active);
const totalRevenue = activeUsers.reduce((sum, user) => sum + user.json.revenue, 0);

// ❌ 差: 用途不明
const a = $input.all().filter(item => item.json.active);
const t = a.reduce((s, u) => s + u.json.revenue, 0);
```

### 6. 用 `console.log()` 调试

```javascript
// 调试语句出现在浏览器控制台
const items = $input.all();
console.log(`Processing ${items.length} items`);

for (const item of items) {
  console.log('Item data:', item.json);
  // 处理...
}

return result;
```

---

## 生产环境陷阱

来自真实 n8n workflow 部署的宝贵经验:

### SplitInBatches 循环语义

SplitInBatches 节点有两个输出 —— 命名违反直觉:

- `main[0]` = **done** —— 所有批次处理完后触发一次
- `main[1]` = **each batch** —— 每批触发一次(这是循环体)

始终在 done 输出后加 **Limit 1** 节点再下游处理,作为边界情况的保险(防止 done 携带额外 item)。

### 跨迭代数据累积(关键)

SplitInBatches 循环结束后,`$('Node Inside Loop').all()` 只返回**最后一次迭代**的 item,而非累积结果。这会静默丢弃除最后一批外的所有数据。

**修复**: 用 workflow static data 跨迭代累积:

```javascript
// 循环前(重置累加器):
const staticData = $getWorkflowStaticData('global');
staticData.results = [];
return $input.all();

// 循环体内(累积):
const staticData = $getWorkflowStaticData('global');
const results = [];
for (const item of $input.all()) {
  const processed = { /* ... */ };
  results.push({ json: processed });
  staticData.results.push(processed);
}
return results;

// 循环后(读取累积数据):
const staticData = $getWorkflowStaticData('global');
const allResults = staticData.results || [];
// 现在聚合所有迭代
```

### pairedItem 用于新输出 item

创建不与输入 item 1:1 映射的新 item 时,带上 `pairedItem` —— 否则下游 Set 节点会报 `paired_item_no_info`:

```javascript
const results = [];
for (let i = 0; i < $input.all().length; i++) {
  const item = $input.all()[i];
  results.push({
    json: { /* 新数据 */ },
    pairedItem: { item: i }
  });
}
return results;
```

### 正确的节点引用语法

```javascript
// ❌ 错误 - 节点引用直接 .json
const data = $('HTTP Request').json;

// ✅ 正确 - 先调用 .first() 再访问 .json
const data = $('HTTP Request').first().json;

// ✅ 也正确 - 获取所有 item
const allData = $('HTTP Request').all();
```

### 浮点精度用于价格/货币比较

比较价格或货币值时,浮点噪声会导致误报。圆整到分:

```javascript
// ❌ 不可靠 - 浮点比较
if (newPrice !== oldPrice) { /* 噪声触发 */ }

// ✅ 可靠 - 在分级别比较
if (Math.round(newPrice * 100) !== Math.round(oldPrice * 100)) {
  // 真实价格变化已检测
}
```

---

## 何时使用 Code 节点

适用:

- ✅ 复杂的多步转换
- ✅ 自定义计算或业务逻辑
- ✅ 递归操作
- ✅ 复杂结构的 API 响应解析
- ✅ 多步条件
- ✅ 跨 item 数据聚合

考虑其他节点:

- ❌ 简单字段映射 → 用 **Set** 节点
- ❌ 基础过滤 → 用 **Filter** 节点
- ❌ 简单条件 → 用 **IF** 或 **Switch** 节点
- ❌ 仅 HTTP 请求 → 用 **HTTP Request** 节点

**Code 节点擅长**: 需要链式多个简单节点的复杂逻辑

---

## 与其他 SKILL 的协作

### 协同

**n8n Expression Syntax**:

- 其他节点用 `{{ }}` 表达式
- Code 节点用直接的 JavaScript(无 `{{ }}`)
- 何时用表达式 vs Code

**n8n MCP Tools Expert**:

- 查找 Code 节点: `search_nodes({query: "code"})`
- 获取配置帮助: `get_node({nodeType: "nodes-base.code"})`
- 校验 Code: `validate_node({nodeType: "nodes-base.code", config: {...}})`

**n8n Node Configuration**:

- Mode 选择(All Items vs Each Item)
- 语言选择(JavaScript vs Python)
- 理解属性依赖

**n8n Workflow Patterns**:

- 转换步骤中的 Code 节点
- Webhook → Code → API 模式
- workflow 中的错误处理

**n8n Validation Expert**:

- 校验 Code 节点配置
- 处理校验错误
- 自动修复常见问题

---

## 快速参考清单

部署 Code 节点前,验证:

- [ ] **代码非空** - 必须有有意义的逻辑
- [ ] **存在 return 语句** - 必须返回对象数组
- [ ] **正确的返回格式** - 每项: `{json: {...}}`
- [ ] **数据访问正确** - 用 `$input.all()`、`$input.first()`、或 `$input.item`
- [ ] **无 n8n 表达式** - 用 JavaScript 模板字面量: `` `${value}` ``
- [ ] **错误处理** - 对 null/undefined 输入用守卫子句
- [ ] **Webhook 数据** - 若来自 webhook,通过 `.body` 访问
- [ ] **Mode 选择** - 大多数场景用 "All Items"
- [ ] **性能** - 优先用 map/filter 而非手动循环
- [ ] **输出一致** - 所有代码路径返回相同结构

---

## 其他资源

### 相关文件

- [DATA_ACCESS.md](DATA_ACCESS.md) - 完整数据访问模式
- [COMMON_PATTERNS.md](COMMON_PATTERNS.md) - 10 个生产验证模式
- [ERROR_PATTERNS.md](ERROR_PATTERNS.md) - Top 5 错误与解决方案
- [BUILTIN_FUNCTIONS.md](BUILTIN_FUNCTIONS.md) - 完整内置参考

### n8n 文档

- Code 节点指南: https://docs.n8n.io/code/code-node/
- 内置方法: https://docs.n8n.io/code-examples/methods-variables-reference/
- Luxon 文档: https://moment.github.io/luxon/

---

**准备好在 n8n Code 节点写 JavaScript 了!** 从简单转换开始,用错误模式指南避开常见错误,参考模式库获取生产可用示例。
