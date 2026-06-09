# n8n 表达式示例

来自 n8n workflow 的真实可用示例。

---

## 示例 1:Webhook 表单提交

**场景**: 表单提交 webhook 推送到 Slack

**Workflow**: Webhook → Slack

**Webhook 输入**(POST):

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "company": "Acme Corp",
  "message": "Interested in your product"
}
```

**Webhook 节点输出**:

```json
{
  "headers": {"content-type": "application/json"},
  "params": {},
  "query": {},
  "body": {
    "name": "John Doe",
    "email": "john@example.com",
    "company": "Acme Corp",
    "message": "Interested in your product"
  }
}
```

**在 Slack 节点的 text 字段**:

```
New form submission! 📝

Name: {{$json.body.name}}
Email: {{$json.body.email}}
Company: {{$json.body.company}}
Message: {{$json.body.message}}
```

**输出**:

```
New form submission! 📝

Name: John Doe
Email: john@example.com
Company: Acme Corp
Message: Interested in your product
```

---

## 示例 2:HTTP API 到数据库

**场景**: 从 API 拉取用户数据并插入数据库

**Workflow**: Schedule → HTTP Request → Postgres

**HTTP Request 返回**:

```json
{
  "data": {
    "users": [
      {
        "id": 123,
        "name": "Alice Smith",
        "email": "alice@example.com",
        "role": "admin"
      }
    ]
  }
}
```

**在 Postgres 节点中**(INSERT 语句):

```sql
INSERT INTO users (user_id, name, email, role, synced_at)
VALUES (
  {{$json.data.users[0].id}},
  '{{$json.data.users[0].name}}',
  '{{$json.data.users[0].email}}',
  '{{$json.data.users[0].role}}',
  '{{$now.toFormat('yyyy-MM-dd HH:mm:ss')}}'
)
```

**结果**: 用户以当前时间戳插入

---

## 示例 3:多节点数据流

**场景**: Webhook → HTTP Request → Email

**Workflow 结构**:

1. Webhook 接收 order ID
2. HTTP Request 拉取订单详情
3. Email 发送确认

### 节点 1:Webhook

**接收**:

```json
{
  "body": {
    "order_id": "ORD-12345"
  }
}
```

### 节点 2:HTTP Request

**URL 字段**:

```
https://api.example.com/orders/{{$json.body.order_id}}
```

**返回**:

```json
{
  "order": {
    "id": "ORD-12345",
    "customer": "Bob Jones",
    "total": 99.99,
    "items": ["Widget", "Gadget"]
  }
}
```

### 节点 3:Email

**主题**:

```
Order {{$node["Webhook"].json.body.order_id}} Confirmed
```

**正文**:

```
Dear {{$node["HTTP Request"].json.order.customer}},

Your order {{$node["Webhook"].json.body.order_id}} has been confirmed!

Total: ${{$node["HTTP Request"].json.order.total}}
Items: {{$node["HTTP Request"].json.order.items.join(', ')}}

Thank you for your purchase!
```

**邮件结果**:

```
Subject: Order ORD-12345 Confirmed

Dear Bob Jones,

Your order ORD-12345 has been confirmed!

Total: $99.99
Items: Widget, Gadget

Thank you for your purchase!
```

---

## 示例 4:日期格式化

**场景**: 各种日期格式输出

**当前时间**: 2025-10-20 14:30:45

### ISO 格式

```javascript
{{$now.toISO()}}
```

**输出**: `2025-10-20T14:30:45.000Z`

### 自定义日期格式

```javascript
{{$now.toFormat('yyyy-MM-dd')}}
```

**输出**: `2025-10-20`

### 仅时间

```javascript
{{$now.toFormat('HH:mm:ss')}}
```

**输出**: `14:30:45`

### 完整可读格式

```javascript
{{$now.toFormat('MMMM dd, yyyy')}}
```

**输出**: `October 20, 2025`

### 日期运算 - 未来

```javascript
{{$now.plus({days: 7}).toFormat('yyyy-MM-dd')}}
```

**输出**: `2025-10-27`

### 日期运算 - 过去

```javascript
{{$now.minus({hours: 24}).toFormat('yyyy-MM-dd HH:mm')}}
```

**输出**: `2025-10-19 14:30`

---

## 示例 5:数组操作

**数据**:

```json
{
  "users": [
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"},
    {"name": "Charlie", "email": "charlie@example.com"}
  ]
}
```

### 第一个用户

```javascript
{{$json.users[0].name}}
```

**输出**: `Alice`

### 最后一个用户

```javascript
{{$json.users[$json.users.length - 1].name}}
```

**输出**: `Charlie`

### 所有邮箱(拼接)

```javascript
{{$json.users.map(u => u.email).join(', ')}}
```

**输出**: `alice@example.com, bob@example.com, charlie@example.com`

### 数组长度

```javascript
{{$json.users.length}}
```

**输出**: `3`

---

## 示例 6:条件逻辑

**数据**:

```json
{
  "order": {
    "status": "completed",
    "total": 150
  }
}
```

### 三元运算符

```javascript
{{$json.order.status === 'completed' ? 'Order Complete ✓' : 'Pending...'}}
```

**输出**: `Order Complete ✓`

### 默认值

```javascript
{{$json.order.notes || 'No notes provided'}}
```

**输出**: `No notes provided`(若 notes 字段不存在)

### 多重条件

```javascript
{{$json.order.total > 100 ? 'Premium Customer' : 'Standard Customer'}}
```

**输出**: `Premium Customer`

---

## 示例 7:字符串操作

**数据**:

```json
{
  "user": {
    "email": "JOHN@EXAMPLE.COM",
    "message": "  Hello World  "
  }
}
```

### 小写

```javascript
{{$json.user.email.toLowerCase()}}
```

**输出**: `john@example.com`

### 大写

```javascript
{{$json.user.message.toUpperCase()}}
```

**输出**: `  HELLO WORLD  `

### 去空格

```javascript
{{$json.user.message.trim()}}
```

**输出**: `Hello World`

### 子串

```javascript
{{$json.user.email.substring(0, 4)}}
```

**输出**: `JOHN`

### 替换

```javascript
{{$json.user.message.replace('World', 'n8n')}}
```

**输出**: `  Hello n8n  `

---

## 示例 8:含空格的字段

**数据**:

```json
{
  "user data": {
    "first name": "Jane",
    "last name": "Doe",
    "phone number": "+1234567890"
  }
}
```

### 中括号语法

```javascript
{{$json['user data']['first name']}}
```

**输出**: `Jane`

### 组合

```javascript
{{$json['user data']['first name']}} {{$json['user data']['last name']}}
```

**输出**: `Jane Doe`

### 嵌套空格

```javascript
Contact: {{$json['user data']['phone number']}}
```

**输出**: `Contact: +1234567890`

---

## 示例 9:Code 节点(直接访问)

**Code 节点**: 转换 webhook 数据

**输入**(来自 Webhook 节点):

```json
{
  "body": {
    "items": ["apple", "banana", "cherry"]
  }
}
```

**代码**(JavaScript):

```javascript
// ✅ 直接访问(无 {{ }})
const items = $json.body.items;

// 转换为大写
const uppercased = items.map(item => item.toUpperCase());

// 用 n8n 格式返回
return [{
  json: {
    original: items,
    transformed: uppercased,
    count: items.length
  }
}];
```

**输出**:

```json
{
  "original": ["apple", "banana", "cherry"],
  "transformed": ["APPLE", "BANANA", "CHERRY"],
  "count": 3
}
```

---

## 示例 10:环境变量

**设置**: 环境变量 `API_KEY=secret123`

### 在 HTTP Request 头部中

```javascript
Authorization: Bearer {{$env.API_KEY}}
```

**结果**: `Authorization: Bearer secret123`

### 在 URL 中

```javascript
https://api.example.com/data?key={{$env.API_KEY}}
```

**结果**: `https://api.example.com/data?key=secret123`

---

## 真实 workflow 模板

**基于 n8n 模板 #2947**(Weather to Slack)

### Workflow 结构

Webhook → OpenStreetMap API → Weather API → Slack

### Webhook 斜杠命令

**输入**: `/weather London`

**Webhook 接收**:

```json
{
  "body": {
    "text": "London"
  }
}
```

### OpenStreetMap API

**URL**:

```
https://nominatim.openstreetmap.org/search?q={{$json.body.text}}&format=json
```

### Weather API (NWS)

**URL**:

```
https://api.weather.gov/points/{{$node["OpenStreetMap"].json[0].lat}},{{$node["OpenStreetMap"].json[0].lon}}
```

### Slack 消息

```
Weather for {{$json.body.text}}:

Temperature: {{$node["Weather API"].json.properties.temperature.value}}°C
Conditions: {{$node["Weather API"].json.properties.shortForecast}}
```

---

## 小结

**关键模式**:

1. Webhook 数据在 `.body` 下
2. 用 `{{}}` 表示表达式(Code 节点除外)
3. 用 `$node["Node Name"].json` 引用其他节点
4. 含空格的字段用中括号
5. 节点名区分大小写

**最常用**:

- `{{$json.body.field}}` - Webhook 数据
- `{{$node["Name"].json.field}}` - 其他节点数据
- `{{$now.toFormat('yyyy-MM-dd')}}` - 时间戳
- `{{$json.array[0].field}}` - 数组访问
- `{{$json.field || 'default'}}` - 默认值

---

**相关**: 错误示例与修复见 [COMMON_MISTAKES.md](COMMON_MISTAKES.md)
