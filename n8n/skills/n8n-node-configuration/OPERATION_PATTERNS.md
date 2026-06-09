# Operation 配置模式

按节点类型分类的常见配置模式。

---

## HTTP Request(nodes-base.httpRequest)

最通用的节点。配置变化大,取决于 method 和认证。

### GET 请求

```javascript
{
  "method": "GET",
  "url": "https://api.example.com/users",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "httpHeaderAuth",
  "sendQuery": true,
  "queryParameters": {
    "parameters": [
      {"name": "limit", "value": "100"},
      {"name": "offset", "value": "0"}
    ]
  }
}
```

### POST JSON

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/users",
  "authentication": "none",
  "sendBody": true,
  "body": {
    "contentType": "json",
    "content": {
      "name": "John Doe",
      "email": "john@example.com"
    }
  }
}
```

### POST 表单

```javascript
{
  "method": "POST",
  "url": "https://api.example.com/form",
  "sendBody": true,
  "body": {
    "contentType": "form-urlencoded",
    "content": {
      "field1": "value1",
      "field2": "value2"
    }
  }
}
```

### 带认证

```javascript
{
  "method": "GET",
  "url": "https://api.example.com/protected",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "httpHeaderAuth"
  // 凭据在 n8n Credentials 中配置
}
```

### 带自定义头部

```javascript
{
  "method": "GET",
  "url": "https://api.example.com/data",
  "sendHeaders": true,
  "headers": {
    "parameters": [
      {"name": "X-API-Key", "value": "secret"},
      {"name": "Accept", "value": "application/json"}
    ]
  }
}
```

### 带分页

```javascript
{
  "method": "GET",
  "url": "https://api.example.com/items",
  "sendQuery": true,
  "queryParameters": {
    "parameters": [
      {"name": "page", "value": "={{$json.page || 1}}"},
      {"name": "per_page", "value": "100"}
    ]
  },
  "options": {
    "response": {
      "response": {
        "pagination": {
          "nextUrl": "={{$response.body.next}}"
        }
      }
    }
  }
}
```

---

## Webhook(nodes-base.webhook)

接收 HTTP 请求的入口点。

### 基础 Webhook

```javascript
{
  "httpMethod": "POST",
  "path": "my-webhook",
  "responseMode": "onReceived",
  "responseData": "allEntries"
}
```

### 带认证的 Webhook

```javascript
{
  "httpMethod": "POST",
  "path": "secure-webhook",
  "authentication": "headerAuth",
  "options": {
    "rawBody": false
  }
}
```

### 响应自定义数据

```javascript
{
  "httpMethod": "POST",
  "path": "process",
  "responseMode": "responseNode",  // 用 Respond to Webhook 节点
  "responseData": "allEntries"
}
```

---

## Slack(nodes-base.slack)

发消息、读频道等。

### 发消息

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#general",
  "text": "Hello from n8n!",
  "otherOptions": {
    "mrkdwn": true
  }
}
```

### 消息带 Block

```javascript
{
  "resource": "message",
  "operation": "post",
  "channel": "#alerts",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Alert:* {{$json.message}}"
      }
    }
  ]
}
```

### 更新消息

```javascript
{
  "resource": "message",
  "operation": "update",
  "channel": "#general",
  "messageId": "={{$json.ts}}",
  "text": "Updated message"
}
```

### 创建频道

```javascript
{
  "resource": "channel",
  "operation": "create",
  "name": "new-channel",
  "isPrivate": false
}
```

---

## Gmail(nodes-base.gmail)

发送和接收邮件。

### 发送邮件

```javascript
{
  "resource": "message",
  "operation": "send",
  "to": "user@example.com",
  "subject": "Hello from n8n",
  "message": "This is the body of the email",
  "options": {
    "cc": "cc@example.com",
    "bcc": "bcc@example.com"
  }
}
```

### 带附件

```javascript
{
  "resource": "message",
  "operation": "send",
  "to": "user@example.com",
  "subject": "Report",
  "message": "See attached report",
  "attachments": "={{$binary.attachment}}"
}
```

### 草稿

```javascript
{
  "resource": "draft",
  "operation": "create",
  "to": "user@example.com",
  "subject": "Draft",
  "message": "Draft body"
}
```

---

## Postgres(nodes-base.postgres)

SQL 数据库操作。

### 查询

```javascript
{
  "operation": "executeQuery",
  "query": "SELECT * FROM users WHERE active = $1",
  "additionalFields": {
    "queryParams": "true"
  },
  "queryReplacement": "=true,1"
}
```

### 插入

```javascript
{
  "operation": "insert",
  "table": "users",
  "columns": "name,email,created_at",
  "values": "={{[$json.name, $json.email, $now.toISO()]}}"
}
```

### 更新

```javascript
{
  "operation": "update",
  "table": "users",
  "where": "id = $1",
  "values": "name = $2, email = $3",
  "additionalFields": {
    "queryParams": "true"
  },
  "queryReplacement": "=true,{{$json.id}},{{$json.name}},{{$json.email}}"
}
```

### Upsert(INSERT ... ON CONFLICT)

```javascript
{
  "operation": "executeQuery",
  "query": "INSERT INTO users (email, name) VALUES ($1, $2) ON CONFLICT (email) DO UPDATE SET name = $2"
}
```

---

## Set(nodes-base.set)

字段映射与转换。

### 简单映射

```javascript
{
  "values": {
    "string": [
      {"name": "fullName", "value": "={{$json.firstName}} {{$json.lastName}}"},
      {"name": "email", "value": "={{$json.email}}"}
    ]
  },
  "options": {}
}
```

### 包含原字段

```javascript
{
  "values": {
    "string": [
      {"name": "id", "value": "={{$json.id}}"},
      {"name": "computed", "value": "={{$json.a + $json.b}}"}
    ]
  },
  "options": {
    "dotNotation": true
  }
}
```

### 仅保留特定字段

```javascript
{
  "values": {
    "string": [
      {"name": "id", "value": "={{$json.id}}"},
      {"name": "email", "value": "={{$json.email}}"}
    ]
  },
  "options": {
    "dotNotation": true,
    "keepOnlySet": true  // 丢弃其他字段
  }
}
```

---

## Code(nodes-base.code)

自定义 JavaScript/Python 代码。

### Run Once for All Items

```javascript
// jsCode 字段
const items = $input.all();
return items.map(item => ({
  json: {
    ...item.json,
    processed: true,
    timestamp: new Date().toISOString()
  }
}));
```

### 完整配置

```javascript
{
  "mode": "runOnceForAllItems",
  "language": "javaScript",
  "jsCode": "const items = $input.all();\nreturn items.map(item => ({ json: { ...item.json, processed: true } }));"
}
```

### Run Once for Each Item

```javascript
{
  "mode": "runOnceForEachItem",
  "language": "javaScript",
  "jsCode": "const item = $input.item;\nreturn [{ json: { ...item.json, processed: true } }];"
}
```

---

## IF(nodes-base.if)

条件分支。

### 字符串比较

```javascript
{
  "conditions": {
    "string": [
      {
        "value1": "={{$json.status}}",
        "operation": "equals",
        "value2": "active"
      }
    ]
  }
}
```

### 多条件(AND)

```javascript
{
  "conditions": {
    "number": [
      {
        "value1": "={{$json.age}}",
        "operation": "greaterOrEqual",
        "value2": 18
      }
    ],
    "string": [
      {
        "value1": "={{$json.country}}",
        "operation": "equals",
        "value2": "US"
      }
    ]
  },
  "combinator": "and"
}
```

### 存在性检查

```javascript
{
  "conditions": {
    "string": [
      {
        "value1": "={{$json.email}}",
        "operation": "isEmpty",
        "singleValue": true  // 自动清洗会加
      }
    ]
  }
}
```

---

## Switch(nodes-base.switch)

多路分支。

### 基础 Switch

```javascript
{
  "rules": {
    "values": [
      {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.status}}",
              "operation": "equals",
              "value2": "active"
            }
          ]
        },
        "renameOutput": true,
        "outputKey": "Active"
      },
      {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.status}}",
              "operation": "equals",
              "value2": "pending"
            }
          ]
        },
        "renameOutput": true,
        "outputKey": "Pending"
      }
    ]
  },
  "options": {
    "fallbackOutput": "extra",  // 不匹配时走 fallback
    "renameFallbackOutput": "Default"
  }
}
```

---

## OpenAI(nodes-langchain.openAi)

AI 模型调用。

### 基础 Chat

```javascript
{
  "resource": "chat",
  "operation": "message",
  "modelId": {
    "__rl": true,
    "value": "gpt-4",
    "mode": "list",
    "cachedResultName": "gpt-4"
  },
  "messages": {
    "values": [
      {
        "role": "user",
        "content": "={{$json.prompt}}"
      }
    ]
  },
  "options": {}
}
```

### 带系统提示

```javascript
{
  "resource": "chat",
  "operation": "message",
  "modelId": {"value": "gpt-4"},
  "messages": {
    "values": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "={{$json.question}}"}
    ]
  }
}
```

### JSON 模式

```javascript
{
  "resource": "chat",
  "operation": "message",
  "modelId": {"value": "gpt-4"},
  "messages": {
    "values": [
      {"role": "system", "content": "You output valid JSON only."},
      {"role": "user", "content": "Extract: {{$json.text}}"}
    ]
  },
  "options": {
    "responseFormat": "json_object"
  }
}
```

---

## Schedule Trigger(nodes-base.scheduleTrigger)

定时触发 workflow。

### Cron 表达式

```javascript
{
  "rule": {
    "interval": [
      {
        "cronExpression": "0 9 * * 1-5"  // 工作日 9:00
      }
    ]
  }
}
```

### 间隔

```javascript
{
  "rule": {
    "interval": [
      {
        "field": "minutes",
        "minutesInterval": 15,
        "triggerAtMinute": 0
      }
    ]
  }
}
```

### 多个规则

```javascript
{
  "rule": {
    "interval": [
      {"cronExpression": "0 9 * * *"},  // 每天 9:00
      {"cronExpression": "0 17 * * *"}  // 每天 17:00
    ]
  }
}
```

---

## 小结

**通用原则**:

1. 用 `get_node` 看特定要求
2. 校验配置
3. 从最小化开始
4. 切 operation 时检查

**关键模式**:

- Resource/Operation 节点: 选 resource → 选 operation → 配置
- HTTP 节点: method 决定 sendBody/sendQuery 等
- 数据库: operation 决定 SQL 类型
- AI 节点: model + messages + options

**相关**: 完整属性依赖指南见 [DEPENDENCIES.md](DEPENDENCIES.md)
