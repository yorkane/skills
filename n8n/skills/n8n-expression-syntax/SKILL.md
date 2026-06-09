---
name: n8n-expression-syntax
description: 校验 n8n 表达式语法并修复常见错误。当编写 n8n 表达式、使用 {{}} 语法、访问 $json/$node 变量、排查表达式错误、跨节点映射数据、或在 workflow 中引用 webhook 数据时使用。在配置任何引用前序节点数据的节点字段时都应该激活本 SKILL —— 表达式是 n8n 节点间传递数据的方式，语法错误是 workflow 失败的最常见原因。
---

# n8n 表达式语法

编写正确 n8n 表达式的专家指南。

---

## 表达式格式

n8n 中所有动态内容都使用**双花括号**包裹:

```
{{expression}}
```

**示例**:

```
✅ {{$json.email}}
✅ {{$json.body.name}}
✅ {{$node["HTTP Request"].json.data}}
❌ $json.email  (没有花括号,会被当作纯文本)
❌ {$json.email}  (单花括号,无效)
```

---

## 核心变量

### $json - 当前节点输出

访问当前节点的数据:

```javascript
{{$json.fieldName}}
{{$json['field with spaces']}}
{{$json.nested.property}}
{{$json.items[0].name}}
```

### $node - 引用其他节点

访问任意前序节点的数据:

```javascript
{{$node["Node Name"].json.fieldName}}
{{$node["HTTP Request"].json.data}}
{{$node["Webhook"].json.body.email}}
```

**重要**:

- 节点名**必须**用引号包裹
- 节点名**区分大小写**
- 必须与 workflow 中实际的节点名完全一致

### $now - 当前时间戳

获取当前日期/时间:

```javascript
{{$now}}
{{$now.toFormat('yyyy-MM-dd')}}
{{$now.toFormat('HH:mm:ss')}}
{{$now.plus({days: 7})}}
```

### $env - 环境变量

访问环境变量:

```javascript
{{$env.API_KEY}}
{{$env.DATABASE_URL}}
```

**警告**: 部分 n8n 实例开启了 `N8N_BLOCK_ENV_ACCESS_IN_NODE`,会完全阻断 `$env` 访问。如 `$env` 报错,可改用以下方案:

- 将值存放在 Credentials 中
- 使用 Set 节点手动填入
- 通过 webhook 的 query 参数传入

---

## 🚨 关键点:Webhook 数据结构

**最常见错误**: Webhook 数据**不在**根上!

### Webhook 节点输出结构

```javascript
{
  "headers": {...},
  "params": {...},
  "query": {...},
  "body": {           // ⚠️ 用户数据在这里!
    "name": "John",
    "email": "john@example.com",
    "message": "Hello"
  }
}
```

### 正确的 Webhook 数据访问

```javascript
❌ 错误: {{$json.name}}
❌ 错误: {{$json.email}}

✅ 正确: {{$json.body.name}}
✅ 正确: {{$json.body.email}}
✅ 正确: {{$json.body.message}}
```

**原因**: Webhook 节点会把传入数据放在 `.body` 属性下,以保留 headers、params、query 参数。

---

## 常见模式

### 访问嵌套字段

```javascript
// 简单嵌套
{{$json.user.email}}

// 数组访问
{{$json.data[0].name}}
{{$json.items[0].id}}

// 带空格的字段用中括号
{{$json['field name']}}
{{$json['user data']['first name']}}
```

### 引用其他节点

```javascript
// 节点名无空格
{{$node["Set"].json.value}}

// 节点名有空格(常见!)
{{$node["HTTP Request"].json.data}}
{{$node["Respond to Webhook"].json.message}}

// Webhook 节点
{{$node["Webhook"].json.body.email}}
```

### 组合变量

```javascript
// 自动拼接
Hello {{$json.body.name}}!

// 在 URL 中
https://api.example.com/users/{{$json.body.user_id}}

// 在对象属性中
{
  "name": "={{$json.body.name}}",
  "email": "={{$json.body.email}}"
}
```

---

## 不应使用表达式的场景

### ❌ Code 节点

Code 节点使用**直接的 JavaScript 访问**,不用表达式!

```javascript
// ❌ Code 节点中错误
const email = '={{$json.email}}';
const name = '{{$json.body.name}}';

// ✅ Code 节点中正确
const email = $json.email;
const name = $json.body.name;

// 或者用 Code 节点 API
const email = $input.item.json.email;
const allItems = $input.all();
```

### ❌ Webhook 路径

```javascript
// ❌ 错误
path: "{{$json.user_id}}/webhook"

// ✅ 正确
path: "user-webhook"  // 只能使用静态路径
```

### ❌ 凭据字段

```javascript
// ❌ 错误
apiKey: "={{$env.API_KEY}}"

// ✅ 正确
使用 n8n 凭据系统,而不是表达式
```

---

## 校验规则

### 1. 必须使用 {{}}

表达式**必须**用双花括号包裹。

```javascript
❌ $json.field
✅ {{$json.field}}
```

### 2. 含空格或特殊字符时必须用引号

字段名或节点名含空格、变音符、特殊字符时,必须使用**中括号**语法:

```javascript
❌ {{$json.field name}}
✅ {{$json['field name']}}

❌ {{$node.HTTP Request.json}}
✅ {{$node["HTTP Request"].json}}

// 键含特殊字符时中括号是必须的
✅ {{$json['Gross Price w/o shipment']}}
✅ {{$json['Cena brutto zł']}}
```

### 3. 节点名必须精确匹配

节点引用**区分大小写**:

```javascript
❌ {{$node["http request"].json}}  // 全小写
❌ {{$node["Http Request"].json}}  // 大小写错误
✅ {{$node["HTTP Request"].json}}  // 精确匹配
```

### 4. 不要嵌套 {{}}

不要重复包裹:

```javascript
❌ {{{$json.field}}}
✅ {{$json.field}}
```

---

## 常见错误

完整错误目录与修复方法见 [COMMON_MISTAKES.md](COMMON_MISTAKES.md)

### 速查修复

| 错误写法 | 正确写法 |
|---------|---------|
| `$json.field` | `{{$json.field}}` |
| `{{$json.field name}}` | `{{$json['field name']}}` |
| `{{$node.HTTP Request}}` | `{{$node["HTTP Request"]}}` |
| `{{{$json.field}}}` | `{{$json.field}}` |
| `{{$json.name}}` (webhook) | `{{$json.body.name}}` |
| `'={{$json.email}}'` (Code 节点) | `$json.email` |

---

## 实际示例

完整 workflow 示例见 [EXAMPLES.md](EXAMPLES.md)

### 示例 1:Webhook → Slack

**Webhook 接收**:

```json
{
  "body": {
    "name": "John Doe",
    "email": "john@example.com",
    "message": "Hello!"
  }
}
```

**在 Slack 节点的 text 字段中**:

```
New form submission!

Name: {{$json.body.name}}
Email: {{$json.body.email}}
Message: {{$json.body.message}}
```

### 示例 2:HTTP Request → Email

**HTTP Request 返回**:

```json
{
  "data": {
    "items": [
      {"name": "Product 1", "price": 29.99}
    ]
  }
}
```

**在 Email 节点中**(引用 HTTP Request):

```
Product: {{$node["HTTP Request"].json.data.items[0].name}}
Price: ${{$node["HTTP Request"].json.data.items[0].price}}
```

### 示例 3:格式化时间戳

```javascript
// 当前日期
{{$now.toFormat('yyyy-MM-dd')}}
// 结果: 2025-10-20

// 时间
{{$now.toFormat('HH:mm:ss')}}
// 结果: 14:30:45

// 完整日期时间
{{$now.toFormat('yyyy-MM-dd HH:mm')}}
// 结果: 2025-10-20 14:30
```

---

## 数据类型处理

### 数组

```javascript
// 第一项
{{$json.users[0].email}}

// 数组长度
{{$json.users.length}}

// 最后一项
{{$json.users[$json.users.length - 1].name}}
```

### 对象

```javascript
// 点号(无空格)
{{$json.user.email}}

// 中括号(含空格或动态键)
{{$json['user data'].email}}
```

### 字符串

```javascript
// 自动拼接
Hello {{$json.name}}!

// 字符串方法
{{$json.email.toLowerCase()}}
{{$json.name.toUpperCase()}}
```

### 数字

```javascript
// 直接使用
{{$json.price}}

// 数学运算
{{$json.price * 1.1}}  // 加 10%
{{$json.quantity + 5}}
```

---

## 进阶模式

### 条件内容

```javascript
// 三元运算符
{{$json.status === 'active' ? 'Active User' : 'Inactive User'}}

// 默认值
{{$json.email || 'no-email@example.com'}}
```

### 日期操作

```javascript
// 加天数
{{$now.plus({days: 7}).toFormat('yyyy-MM-dd')}}

// 减小时
{{$now.minus({hours: 24}).toISO()}}

// 设置指定日期
{{DateTime.fromISO('2025-12-25').toFormat('MMMM dd, yyyy')}}
```

### 字符串操作

```javascript
// 截取子串
{{$json.email.substring(0, 5)}}

// 替换
{{$json.message.replace('old', 'new')}}

// 分割与拼接
{{$json.tags.split(',').join(', ')}}
```

---

## 调试表达式

### 在表达式编辑器中测试

1. 点击带表达式的字段
2. 打开表达式编辑器(点击 "fx" 图标)
3. 查看实时预览
4. 检查标红的错误

### 常见错误提示

**"Cannot read property 'X' of undefined"**
→ 父对象不存在
→ 检查数据路径

**"X is not a function"**
→ 对非函数调用方法
→ 检查变量类型

**表达式显示为纯文本**
→ 缺少 {{ }}
→ 加上花括号

---

## 表达式辅助方法

### 可用方法

**字符串**:
- `.toLowerCase()`、`.toUpperCase()`
- `.trim()`、`.replace()`、`.substring()`
- `.split()`、`.includes()`

**数组**:
- `.length`、`.map()`、`.filter()`
- `.find()`、`.join()`、`.slice()`

**日期**(Luxon):
- `.toFormat()`、`.toISO()`、`.toLocal()`
- `.plus()`、`.minus()`、`.set()`

**数字**:
- `.toFixed()`、`.toString()`
- 数学运算: `+`、`-`、`*`、`/`、`%`

---

## 最佳实践

### ✅ 应该

- 动态内容始终用 {{ }} 包裹
- 含空格的字段名用中括号
- Webhook 数据从 `.body` 引用
- 用 `$node` 引用其他节点
- 在表达式编辑器中测试

### ❌ 不应

- 在 Code 节点里使用表达式
- 节点名含空格时忘记加引号
- 多层 {{ }} 嵌套
- 假设 Webhook 数据在根上(它在 .body!)
- 在 webhook 路径或凭据中使用表达式

---

## 相关 SKILL

- **n8n MCP Tools Expert**:学习用 MCP 工具校验表达式
- **n8n Workflow Patterns**:在实际 workflow 中看表达式用法
- **n8n Node Configuration**:理解何时需要表达式

---

## 小结

**核心规则**:

1. 表达式用 {{ }} 包裹
2. Webhook 数据在 `.body` 下
3. Code 节点中不用 {{ }}
4. 含空格的节点名要加引号
5. 节点名区分大小写

**最常见错误**:

- 漏写 {{ }} → 加上花括号
- Webhook 中 `{{$json.name}}` → 用 `{{$json.body.name}}`
- Code 节点中 `{{$json.email}}` → 用 `$json.email`
- `{{$node.HTTP Request}}` → 用 `{{$node["HTTP Request"]}}`

更多细节:
- [COMMON_MISTAKES.md](COMMON_MISTAKES.md) - 完整错误目录
- [EXAMPLES.md](EXAMPLES.md) - 实际 workflow 示例

---

**需要帮助?** 参考 n8n 表达式文档,或使用 n8n-mcp 校验工具检查表达式。
