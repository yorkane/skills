# Webhook 处理模式

**用例**: 接收来自外部系统的 HTTP 请求并即时处理。

---

## 模式结构

```
Webhook → [Validate] → [Transform] → [Action] → [Response/Notify]
```

**关键特征**: 即时事件驱动处理

---

## 核心组件

### 1. Webhook 节点(触发器)

**用途**: 创建 HTTP 端点以接收数据

**配置**:

```javascript
{
  path: "form-submit",        // URL 路径: https://n8n.example.com/webhook/form-submit
  httpMethod: "POST",         // GET、POST、PUT、DELETE
  responseMode: "onReceived", // 或 "lastNode" 用于自定义响应
  responseData: "allEntries"  // 或 "firstEntryJson"
}
```

**关键坑**: 数据嵌套在 `$json.body` 下

```javascript
❌ {{$json.email}}
✅ {{$json.body.email}}
```

### 2. 校验(可选但推荐)

**用途**: 处理前校验传入数据

**选项**:

- **IF 节点** - 检查必填字段存在
- **Code 节点** - 自定义校验逻辑
- **Stop and Error** - 优雅失败并提示

**示例**:

```javascript
// IF 节点条件
{{$json.body.email}} is not empty AND
{{$json.body.name}} is not empty
```

### 3. 转换

**用途**: 将 webhook 数据映射为所需格式

**典型节点**:

- **Set** - 字段映射
- **Code** - 复杂转换

**示例**(Set 节点):

```javascript
{
  "user_email": "={{$json.body.email}}",
  "user_name": "={{$json.body.name}}",
  "timestamp": "={{$now}}"
}
```

### 4. 动作

**用途**: 用数据做点什么

**常见动作**:

- 存入数据库(Postgres、MySQL、MongoDB)
- 发送通知(Slack、Email、Discord)
- 调用另一个 API(HTTP Request)
- 更新外部系统(CRM、工单)

### 5. 响应(若 responseMode: "lastNode")

**用途**: 发送自定义 HTTP 响应

**Webhook Response 节点**:

```javascript
{
  statusCode: 200,
  headers: {
    "Content-Type": "application/json"
  },
  body: {
    "status": "success",
    "message": "Form received"
  }
}
```

---

## 常见用例

### 1. 表单提交

**流程**: 表单 → Webhook → 校验 → 数据库 → 邮件确认

**示例**:

```
1. Webhook(path: "contact-form", POST)
2. IF(检查 email 与 message 非空)
3. Postgres(插入 contacts 表)
4. Email(给用户发确认)
5. Slack(在 #leads 通知团队)
6. Webhook Response({"status": "success"})
```

**实际数据访问**:

```javascript
Name: {{$json.body.name}}
Email: {{$json.body.email}}
Message: {{$json.body.message}}
```

### 2. 支付 Webhook(Stripe、PayPal)

**流程**: 支付提供商 → Webhook → 验证 → 更新数据库 → 发送收据

**安全**: 验证 webhook 签名

```javascript
// Code 节点 - 验证 Stripe 签名
const crypto = require('crypto');
const signature = $input.item.headers['stripe-signature'];
const secret = $credentials.stripeWebhookSecret;

// 验证签名匹配
const expectedSig = crypto
  .createHmac('sha256', secret)
  .update($input.item.body)
  .digest('hex');

if (signature !== expectedSig) {
  throw new Error('Invalid webhook signature');
}

return $input.item.body; // 返回已验证的 body
```

### 3. 聊天平台集成(Slack、Discord、Teams)

**流程**: 聊天命令 → Webhook → 处理 → 响应

**示例**(Slack 斜杠命令):

```
1. Webhook(path: "slack-command", POST)
2. Code(解析 Slack payload: $json.body.text, $json.body.user_id)
3. HTTP Request(从 API 拉取数据)
4. Set(格式化 Slack 消息)
5. Webhook Response(即时 Slack 响应)
```

**Slack 数据访问**:

```javascript
Command: {{$json.body.command}}
Text: {{$json.body.text}}
User ID: {{$json.body.user_id}}
Channel ID: {{$json.body.channel_id}}
```

### 4. GitHub/GitLab Webhook

**流程**: Git 事件 → Webhook → 解析 → 通知/部署

**示例**(新 PR 通知):

```
1. Webhook(path: "github", POST)
2. IF(检查 $json.body.action 等于 "opened")
3. Set(提取 PR 详情: title、author、url)
4. Slack(通知 #dev-team)
5. Webhook Response(200 OK)
```

**GitHub 数据访问**:

```javascript
Event Type: {{$json.headers['x-github-event']}}
Action: {{$json.body.action}}
PR Title: {{$json.body.pull_request.title}}
Author: {{$json.body.pull_request.user.login}}
URL: {{$json.body.pull_request.html_url}}
```

### 5. IoT 设备数据

**流程**: 设备 → Webhook → 校验 → 存储 → 告警(超阈值时)

**示例**(温度传感器):

```
1. Webhook(path: "sensor-data", POST)
2. Set(提取传感器读数)
3. Postgres(插入 sensor_readings)
4. IF(temperature > 80)
5. Email(告警管理员)
```

---

## Webhook 数据结构

### 标准结构

```json
{
  "headers": {
    "content-type": "application/json",
    "user-agent": "...",
    "x-custom-header": "..."
  },
  "params": {
    "id": "123"  // 来自 URL: /webhook/form/:id
  },
  "query": {
    "token": "abc"  // 来自 URL: /webhook/form?token=abc
  },
  "body": {
    // ⚠️ 你的数据在这里!
    "name": "John",
    "email": "john@example.com"
  }
}
```

### 访问不同部分

```javascript
// Headers
{{$json.headers['content-type']}}
{{$json.headers['x-api-key']}}

// URL 参数
{{$json.params.id}}

// Query 参数
{{$json.query.token}}
{{$json.query.page}}

// Body(最常用)
{{$json.body.email}}
{{$json.body.user.name}}
{{$json.body.items[0].price}}
```

---

## 认证与安全

### 1. Query 参数 Token

**简单但安全性较低**

```javascript
// IF 节点 - 验证 token
{{$json.query.token}} equals "your-secret-token"
```

### 2. Header 认证

**更好的安全性**

```javascript
// IF 节点 - 检查 header
{{$json.headers['x-api-key']}} equals "your-api-key"
```

### 3. 签名验证

**最佳安全性**(用于 Stripe、GitHub 等服务的 webhook)

```javascript
// Code 节点
const crypto = require('crypto');
const signature = $input.item.headers['x-signature'];
const secret = $credentials.webhookSecret;

const calculatedSig = crypto
  .createHmac('sha256', secret)
  .update(JSON.stringify($input.item.body))
  .digest('hex');

if (signature !== `sha256=${calculatedSig}`) {
  throw new Error('Invalid signature');
}

return $input.item.body;
```

### 4. IP 白名单

**按 IP 限制访问**(n8n workflow 设置)

- 在 workflow 设置中配置
- 仅允许特定 IP 段
- 用于内部系统

---

## 响应模式

### onReceived(默认)

**行为**: 立即返回 200 OK 响应,workflow 在后台继续

**适用场景**:

- 长时间运行的 workflow
- 响应不依赖 workflow 结果
- 即发即忘的处理

**配置**:

```javascript
{
  responseMode: "onReceived",
  responseCode: 200
}
```

### lastNode(自定义响应)

**行为**: 等待 workflow 完成,发送自定义响应

**适用场景**:

- 需要给调用方返回数据
- 需要同步处理
- 表单提交后需确认

**配置**:

```javascript
{
  responseMode: "lastNode"
}
```

**然后加 Webhook Response 节点**:

```javascript
{
  statusCode: 200,
  headers: {
    "Content-Type": "application/json"
  },
  body: {
    "id": "={{$json.record_id}}",
    "status": "success"
  }
}
```

---

## 错误处理

### 模式 1:Try-Catch + Error Trigger

```
主流程:
  Webhook → [nodes...] → Success Response

错误流程:
  Error Trigger → 记录错误 → Slack 告警 → 错误响应
```

**Error Trigger 配置**:

```javascript
{
  workflowId: "current-workflow-id"
}
```

**错误响应**(若 responseMode: "lastNode"):

```javascript
{
  statusCode: 500,
  body: {
    "status": "error",
    "message": "Processing failed"
  }
}
```

---

## 测试 Webhook

用 curl 模拟 webhook 调用:

```bash
curl -X POST https://n8n.example.com/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "email": "test@example.com"}'
```

**注意**: 必须先**激活** workflow,webhook 才生效。

---

## 性能考量

### Webhook 超时

- 默认 30 秒
- 可在 workflow 设置中调整
- 长任务用 `onReceived` 模式

### 速率限制

- 取决于 n8n 实例配置
- 高量 webhook 考虑队列

### 数据大小

- 单次最大负载 ~16MB
- 大文件用二进制模式

---

## 常见坑

### 1. 忘记 `.body`

**问题**: 数据访问返回 undefined

**解决**: 始终用 `$json.body.field`

### 2. Webhook 未激活

**问题**: curl 调用返回 404

**解决**: 激活 workflow(webhook 需激活才生效)

### 3. 同步响应等待

**问题**: 长任务导致调用方超时

**解决**: 用 `onReceived` 模式

### 4. 缺认证

**问题**: 公开 webhook 被滥用

**解决**: 加 header auth、签名验证、IP 白名单

---

## 真实模板示例

来自 n8n 模板库:

- **模板 #1566**: Stripe Webhook → 数据库 + 邮件
- **模板 #2034**: Typeform Webhook → Slack + Sheets
- **模板 #2947**: 天气到 Slack
- **模板 #1822**: GitHub PR → Slack

用 `search_templates` 与 `get_template` 查找!

---

## Webhook Workflow 清单

- [ ] 路径名清晰有描述
- [ ] HTTP method 正确(POST 用于写入,GET 用于读取)
- [ ] 数据访问用 `$json.body`
- [ ] 必填字段校验
- [ ] 认证/签名验证
- [ ] 错误处理(Error Trigger)
- [ ] 响应模式合理(`onReceived` vs `lastNode`)
- [ ] workflow 已激活
- [ ] 监控 webhook 调用

---

## 小结

**核心要点**:

1. Webhook 数据**始终在 `.body` 下**
2. 用合适的认证(query token、header、签名)
3. 选对响应模式(即时 vs 同步)
4. 添加错误处理
5. 测试用 curl

**何时使用**:

- 接收外部事件(表单、支付、聊天命令)
- 构建 webhook 集成
- 即时事件处理
- API 网关模式

**相关 SKILL**: n8n Expression Syntax、n8n MCP Tools Expert、n8n Validation Expert
