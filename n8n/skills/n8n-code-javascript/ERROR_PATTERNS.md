# 错误模式 - JavaScript Code 节点

JavaScript Code 节点中常见错误的综合指南与解决方案。

---

## 概览

按发生频率排序的常见错误:

1. **空代码或缺 return 语句**(35%)
2. **表达式语法混淆**(20%)
3. **返回包装格式错误**(15%)
4. **未匹配的花括号**(10%)
5. **缺空值检查**(10%)
6. **UnsupportedFunctionError**(5%)
7. **$env 未定义**(5%)

---

## 错误 #1:空代码或缺 return 语句

**最常见错误**

### ❌ 错误:无 return

```javascript
const items = $input.all();
// ... 处理代码 ...
// 忘记 return!

// 或仅有 console.log
console.log('Processing items');
```

### ✅ 正确:始终返回数据

```javascript
const items = $input.all();

const processed = items.map(item => ({
  json: {
    ...item.json,
    processed: true
  }
}));

return processed;  // 关键!
```

### 空 return

```javascript
// ✅ 条件返回空数组
const items = $input.all();

if (items.length === 0) {
  return [];  // 无数据时返回空数组
}

return items.map(item => ({ json: item.json }));
```

### 在条件分支中缺 return

```javascript
// ❌ 错误: 一个分支无 return
function processItem(item) {
  if (item.json.active) {
    return [{ json: { ...item.json, status: 'active' } }];
  }
  // 隐式返回 undefined!
}

// ✅ 正确: 所有分支 return
function processItem(item) {
  if (item.json.active) {
    return [{ json: { ...item.json, status: 'active' } }];
  }
  return [{ json: { ...item.json, status: 'inactive' } }];
}
```

---

## 错误 #2:表达式语法混淆

在 Code 节点中,n8n 表达式 `{{ }}` **不工作**!

### ❌ 错误:用 n8n 表达式

```javascript
// ❌ 错误: 这是字面字符串
const value = "{{ $json.field }}";
const name = "={{$json.name}}";  // 也错

// 输出: 字面字符串 "{{ $json.field }}"
```

### ✅ 正确:用 JavaScript

```javascript
// ✅ 模板字面量
const value = `${$json.field}`;

// ✅ 直接访问
const value = $json.field;

// ✅ 通过 $input
const value = $input.first().json.field;
```

### 完整示例

```javascript
// ❌ 错误方式 - 写时想着表达式
const email = "{{$json.body.email}}";
const name = '{{$json.body.name}}';

// ✅ 正确方式 - 直接 JavaScript
const email = $json.body.email;
const name = $json.body.name;

// 或用 $input
const { email, name } = $input.first().json.body;
```

---

## 错误 #3:返回包装格式错误

**关键规则**: 必须返回 `[{json: {...}}]`,而非 `{json: {...}}`

### ❌ 错误:无数组包裹

```javascript
// 错误 1: 返回对象
return {
  json: {result: 'success'}
};

// 错误 2: 无 json 键
return [
  {data: 'value'}
];

// 错误 3: 纯字符串
return "processed";

// 错误 4: 原始数据
return $input.all();  // 缺 .map()
```

### ✅ 正确:数组 + json 包装

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

// ✅ 转换后数组
const transformed = $input.all()
  .filter(item => item.json.valid)
  .map(item => ({
    json: {
      id: item.json.id,
      processed: true
    }
  }));
return transformed;

// ✅ 空数组
return [];
```

### 复杂对象返回

```javascript
// 返回单个复杂对象
const result = {
  json: {
    status: 'success',
    data: {
      items: [...],
      total: 100
    },
    metadata: {
      processedAt: new Date().toISOString(),
      count: 42
    }
  }
};

return [result];  // 数组包裹!
```

---

## 错误 #4:未匹配的表达式花括号

**注意**: 此错误在 Code 节点中**不太可能**,但模板字符串中可能

### ❌ 错误:嵌入的 {{ }}

```javascript
// Code 节点中实际上无害,但仍不推荐
const message = "Hello {{$json.name}}";
// 输出: 字面字符串 "Hello {{$json.name}}"
```

### ✅ 正确:用模板字面量

```javascript
// 用 ${} 语法
const message = `Hello ${$json.name}`;
// 输出: "Hello John"

// 多变量
const greeting = `Hello ${$json.name}, you are ${$json.age} years old`;
```

### 何时用 `{{ }}`

**仅在非 Code 节点的表达式字段**:

```javascript
// 在 Slack 节点的 text 字段中(不是 Code 节点):
"New message from {{$json.body.name}}"

// 在 Email 节点的 subject 中:
"Order {{$json.body.order_id}} confirmed"
```

---

## 错误 #5:缺空值检查 / Undefined 访问

**常见崩溃原因**

### ❌ 错误:无检查

```javascript
// 可能崩如果字段缺失
const value = item.json.user.email;
const length = item.json.items.length;
const result = item.json.data.value.toUpperCase();
```

### ✅ 正确:可选链 + 默认值

```javascript
// 可选链
const email = item.json?.user?.email;

// 带默认值
const email = item.json?.user?.email || 'no-email@example.com';
const length = (item.json?.items || []).length;
const result = (item.json?.data?.value || '').toUpperCase();
```

### 守卫子句

```javascript
const item = $input.first();

if (!item || !item.json) {
  return [{
    json: {
      error: 'Invalid input data',
      timestamp: new Date().toISOString()
    }
  }];
}

if (!item.json.user) {
  return [{
    json: {
      error: 'Missing user data',
      input: item.json
    }
  }];
}

const email = item.json.user.email;
return [{ json: { email } }];
```

### try-catch

```javascript
try {
  const items = $input.all();
  const processed = items.map(item => {
    // 可能抛错的代码
    return {
      json: {
        value: item.json.data.value.toUpperCase(),
        valid: true
      }
    };
  });
  return processed;
} catch (error) {
  return [{
    json: {
      error: error.message,
      stack: error.stack,
      valid: false
    }
  }];
}
```

---

## 错误 #6:UnsupportedFunctionError(Auth Helpers 被阻止)

**n8n 安全沙箱**阻止某些函数以防凭据泄露

### ❌ 不允许的函数

```javascript
// ❌ 不允许
const response = await $helpers.httpRequestWithAuthentication.call(
  this,
  'httpHeaderAuth',
  { url: 'https://api.example.com' }
);
```

### ✅ 允许的替代

**模式 1:无认证的 HTTP 请求**

```javascript
// ✅ 用 $helpers.httpRequest()(无认证)
const response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/data',
  headers: {
    'Authorization': 'Bearer ' + $env.API_TOKEN  // 用环境变量
  }
});
```

**模式 2:用 HTTP Request 节点做认证调用**

```
HTTP Request 节点(配 credentials)
  → Code 节点(处理响应)
```

**模式 3:用环境变量 + 手动认证**

```javascript
// ✅ 从环境变量读 token
const apiKey = $env.API_KEY;

const response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/data',
  headers: {
    'Authorization': `Bearer ${apiKey}`
  }
});
```

---

## 错误 #7:$env 未定义 / 无法访问 $env

当 N8N_BLOCK_ENV_ACCESS_IN_NODE=true 时会发生

### ❌ 错误:$env 未定义

```javascript
// 当 N8N_BLOCK_ENV_ACCESS_IN_NODE=true 时崩
const apiKey = $env.API_KEY;
// 错误: $env is not defined
```

### ✅ 解决方案

**方案 1:用 n8n Credentials**

```
HTTP Request 节点
  - 认证: predefinedCredentialType
  - nodeCredentialType: httpHeaderAuth
  - 在 Credentials 中配置 API key
```

**方案 2:Set 节点 + 表达式**

```
Set 节点
  - apiKey: ={{$env.API_KEY}}  // Set 节点中 $env 仍可用!
  ↓
Code 节点
  const apiKey = $input.first().json.apiKey;
```

**方案 3:Webhook query 参数**

```
Webhook (?api_key=xxx)
  ↓
Code 节点
  const apiKey = $input.first().json.query.api_key;
```

**方案 4:全局静态数据**

```javascript
// 之前在另一节点设置:
$getWorkflowStaticData('global').apiKey = process.env.API_KEY;

// 然后在 Code 节点中:
const apiKey = $getWorkflowStaticData('global').apiKey;
```

---

## 错误防范清单

部署 Code 节点前,验证:

- [ ] **代码非空** - 有意义逻辑
- [ ] **存在 return 语句** - 所有路径都返回
- [ ] **正确返回格式** - `[{json: {...}}]`
- [ ] **数据访问正确** - $input.all() / $input.first() / $input.item
- [ ] **无 n8n 表达式** - 用模板字面量
- [ ] **错误处理** - try-catch 或守卫子句
- [ ] **空值安全** - 可选链 + 默认值
- [ ] **Webhook .body** - 若来自 webhook
- [ ] **Mode 正确** - All Items vs Each Item
- [ ] **性能** - 数组方法 > 循环
- [ ] **输出一致** - 所有路径返回相同结构

---

## 快速错误参考

| 错误 | 症状 | 修复 |
|------|------|------|
| 缺 return | 无输出 / 警告 | 加 return [{json: ...}] |
| 表达式 `{{ }}` | 字面字符串 | 用 `\`${var}\`` 或直接访问 |
| 错返回格式 | 下游节点失败 | 用 `[{json: ...}]` 数组包裹 |
| 缺 .body | undefined (webhook) | 访问 `$json.body.field` |
| 字段未定义 | Cannot read property | 可选链 `?.` + 默认值 `||` |
| 错模式 | $input.item undefined | All Items 模式用 $input.all() |
| Auth helper 错误 | UnsupportedFunction | 用 $helpers.httpRequest() |
| $env 未定义 | 沙箱拦截 | 用 Credentials 或 Set 节点 |

---

## 调试技巧

### 1. console.log() 调试

```javascript
const items = $input.all();
console.log('Items count:', items.length);
console.log('First item:', JSON.stringify(items[0], null, 2));

const processed = items.map(item => {
  console.log('Processing:', item.json.id);
  return { json: { ...item.json, processed: true } };
});

return processed;
```

**查看 console 输出**: 浏览器开发者工具 / n8n 执行日志

### 2. 始终返回的 try-catch

```javascript
try {
  // 你的代码
  const data = $input.first().json;
  return [{ json: { result: data.value.toUpperCase() } }];
} catch (error) {
  return [{
    json: {
      error: error.message,
      stack: error.stack,
      input: $input.first().json
    }
  }];
}
```

### 3. 分步调试

```javascript
// Step 1: 验证输入
const items = $input.all();
if (!items || items.length === 0) {
  return [{ json: { error: "No input" } }];
}

// Step 2: 处理一部分
const sample = items[0];
if (!sample.json.required_field) {
  return [{ json: { error: "Missing required_field", data: sample.json } }];
}

// Step 3: 完整处理
return items.map(item => ({
  json: { ...item.json, processed: true }
}));
```

### 4. 单元测试方法

```javascript
// 测试特定输入
const testData = {
  json: {
    id: 1,
    name: "Test"
  }
};

const items = [testData];  // 模拟输入
return items.map(item => ({ json: { ...item.json, result: "ok" } }));
```

---

## 小结

**Top 5 错误(占 90% 失败)**:

1. **缺 return** - 始终 return `[{json: ...}]`
2. **用 `{{ }}`** - Code 节点用 JS 模板字面量
3. **错返回格式** - 数组 + json 包装
4. **Webhook 缺 .body** - 加 `.body`
5. **缺空值检查** - 可选链 + 默认值

**预防**:
- 用错误防范清单
- 始终 try-catch
- 调试时 console.log
- 分步验证

**记住**: Code 节点是 JavaScript,不是 n8n 表达式!

**相关**:

- [DATA_ACCESS.md](DATA_ACCESS.md) - 数据访问
- [COMMON_PATTERNS.md](COMMON_PATTERNS.md) - 生产模式
- [BUILTIN_FUNCTIONS.md](BUILTIN_FUNCTIONS.md) - 辅助函数
