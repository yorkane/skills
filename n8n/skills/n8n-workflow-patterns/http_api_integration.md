# HTTP API 集成模式

**用例**: 从 REST API 拉取数据,转换后用于 workflow。

---

## 模式结构

```
Trigger → HTTP Request → [Transform] → [Action] → [Error Handler]
```

**关键特征**: 外部数据获取与错误处理

---

## 核心组件

### 1. 触发器

**选项**:

- **Schedule** - 周期性获取(最常见)
- **Webhook** - 由外部事件触发
- **Manual** - 按需执行

### 2. HTTP Request 节点

**用途**: 调用外部 REST API

**配置**:

```javascript
{
  method: "GET",                    // GET、POST、PUT、DELETE、PATCH
  url: "https://api.example.com/users",
  authentication: "predefinedCredentialType",
  sendQuery: true,
  queryParameters: {
    "page": "={{$json.page}}",
    "limit": "100"
  },
  sendHeaders: true,
  headerParameters: {
    "Accept": "application/json",
    "X-API-Version": "v1"
  }
}
```

### 3. 响应处理

**用途**: 提取并转换 API 响应数据

**典型流程**:

```
HTTP Request → Code(解析)→ Set(映射字段)→ Action
```

### 4. 动作

**常见动作**:

- 存入数据库
- 发送到另一个 API
- 创建通知
- 更新电子表格

### 5. 错误处理

**用途**: 优雅处理 API 失败

**Error Trigger Workflow**:

```
Error Trigger → 记录错误 → 通知管理员 → 重试逻辑(可选)
```

---

## 常见用例

### 1. 数据获取与存储

**流程**: Schedule → HTTP Request → 转换 → 数据库

**示例**(拉取 GitHub issues):

```
1. Schedule(每小时)
2. HTTP Request
   - Method: GET
   - URL: https://api.github.com/repos/owner/repo/issues
   - Auth: Bearer Token
   - Query: state=open
3. Code(按 label 过滤)
4. Set(映射到数据库 schema)
5. Postgres(upsert issues)
```

**响应处理**:

```javascript
// Code 节点 - 过滤 issues
const issues = $input.all();
return issues
  .filter(item => item.json.labels.some(l => l.name === 'bug'))
  .map(item => ({
    json: {
      id: item.json.id,
      title: item.json.title,
      created_at: item.json.created_at
    }
  }));
```

### 2. API 到 API 集成

**流程**: Trigger → 从 API A 拉取 → 转换 → 发送到 API B

**示例**(Jira 到 Slack):

```
1. Schedule(每 15 分钟)
2. HTTP Request(GET 今天更新的 Jira 工单)
3. IF(检查工单是否存在)
4. Set(格式化为 Slack 消息)
5. HTTP Request(POST 到 Slack webhook)
```

### 3. 数据富化

**流程**: Trigger → 拉取基础数据 → 调用富化 API → 合并 → 存储

**示例**(用公司数据富化联系人):

```
1. Postgres(SELECT 新联系人)
2. Code(提取公司域名)
3. HTTP Request(对每个域名调用 Clearbit API)
4. Set(合并联系人 + 公司数据)
5. Postgres(UPDATE 联系人的富化数据)
```

### 4. 监控与告警

**流程**: Schedule → 检查 API 健康 → IF 不健康 → 告警

**示例**(API 健康检查):

```
1. Schedule(每 5 分钟)
2. HTTP Request(GET /health 端点)
3. IF(status !== 200 OR 响应时间 > 2000ms)
4. Slack(告警 #ops-team)
5. PagerDuty(创建事故)
```

### 5. 批处理

**流程**: Trigger → 拉取大数据集 → Split in Batches → 处理 → 循环

**示例**(处理所有用户):

```
1. Manual Trigger
2. HTTP Request(GET /api/users?limit=1000)
3. Split In Batches(每批 100 项)
4. HTTP Request(对每批 POST /api/process)
5. Wait(批次间 2 秒 - 限流)
6. Loop(回到步骤 4 直到全部处理完)
```

---

## 认证方式

### 1. 无认证(公共 API)

```javascript
{
  authentication: "none"
}
```

### 2. Bearer Token(最常见)

**设置**: 创建凭据

```javascript
{
  authentication: "predefinedCredentialType",
  nodeCredentialType: "httpHeaderAuth",
  headerAuth: {
    name: "Authorization",
    value: "Bearer YOUR_TOKEN"
  }
}
```

**workflow 中访问**:

```javascript
{
  authentication: "predefinedCredentialType",
  nodeCredentialType: "httpHeaderAuth"
}
```

### 3. API Key(Header 或 Query)

**Header 认证**:

```javascript
{
  sendHeaders: true,
  headerParameters: {
    "X-API-Key": "={{$credentials.apiKey}}"
  }
}
```

**Query 认证**:

```javascript
{
  sendQuery: true,
  queryParameters: {
    "api_key": "={{$credentials.apiKey}}"
  }
}
```

### 4. Basic Auth

**设置**: 创建 "Basic Auth" 凭据

```javascript
{
  authentication: "predefinedCredentialType",
  nodeCredentialType: "httpBasicAuth"
}
```

### 5. OAuth2

**设置**: 创建 OAuth2 凭据,含:

- Authorization URL
- Token URL
- Client ID
- Client Secret
- Scopes

```javascript
{
  authentication: "predefinedCredentialType",
  nodeCredentialType: "oAuth2Api"
}
```

---

## 处理 API 响应

### 成功响应(200-299)

**默认**: 数据流到下一节点

**访问响应**:

```javascript
// 整个响应
{{$json}}

// 特定字段
{{$json.data.id}}
{{$json.results[0].name}}
```

### 分页

#### 模式 1:基于 Offset

```
1. Set(初始化: page=1, has_more=true)
2. HTTP Request(GET /api/items?page={{$json.page}})
3. Code(检查是否还有更多页)
4. IF(has_more === true)
   └→ Set(page 自增)→ 循环到步骤 2
```

**Code 节点**(检查分页):

```javascript
const items = $input.first().json;
const currentPage = $json.page || 1;

return [{
  json: {
    items: items.results,
    page: currentPage + 1,
    has_more: items.next !== null
  }
}];
```

#### 模式 2:基于 Cursor

```
1. HTTP Request(GET /api/items)
2. Code(提取 next_cursor)
3. IF(next_cursor 存在)
   └→ Set(cursor={{$json.next_cursor}})→ 循环到步骤 1
```

#### 模式 3:Link Header

```javascript
// Code 节点 - 解析 Link header
const linkHeader = $input.first().json.headers['link'];
const hasNext = linkHeader && linkHeader.includes('rel="next"');

return [{
  json: {
    items: $input.first().json.body,
    has_next: hasNext,
    next_url: hasNext ? parseNextUrl(linkHeader) : null
  }
}];
```

### 错误响应(400-599)

**配置 HTTP Request**:

```javascript
{
  continueOnFail: true,  // 错误时 workflow 不停止
  ignoreResponseCode: true  // 错误时也获取响应
}
```

**处理错误**:

```
HTTP Request(continueOnFail: true)
  → IF(检查错误)
    ├─ [成功路径]
    └─ [错误路径] → 记录 → 重试或告警
```

**IF 条件**:

```javascript
{{$json.error}} is empty
// 或
{{$json.statusCode}} < 400
```

---

## 限流

### 模式 1:请求间等待

```
Split In Batches(每批 1 项)
  → HTTP Request
  → Wait(1 秒)
  → Loop
```

### 模式 2:指数回退

```javascript
// Code 节点
const maxRetries = 3;
let retryCount = $json.retryCount || 0;

if ($json.error && retryCount < maxRetries) {
  const delay = Math.pow(2, retryCount) * 1000; // 1s, 2s, 4s

  return [{
    json: {
      ...$json,
      retryCount: retryCount + 1,
      waitTime: delay
    }
  }];
}
```

### 模式 3:遵守限流 Headers

```javascript
// Code 节点 - 检查限流
const headers = $input.first().json.headers;
const remaining = parseInt(headers['x-ratelimit-remaining'] || '999');
const resetTime = parseInt(headers['x-ratelimit-reset'] || '0');

if (remaining < 10) {
  const now = Math.floor(Date.now() / 1000);
  const waitSeconds = resetTime - now;

  return [{
    json: {
      shouldWait: true,
      waitSeconds: Math.max(waitSeconds, 0)
    }
  }];
}

return [{ json: { shouldWait: false } }];
```

---

## 请求配置

### GET 请求

```javascript
{
  method: "GET",
  url: "https://api.example.com/users",
  sendQuery: true,
  queryParameters: {
    "page": "1",
    "limit": "100",
    "filter": "active"
  }
}
```

### POST 请求(JSON Body)

```javascript
{
  method: "POST",
  url: "https://api.example.com/users",
  sendBody: true,
  bodyParametersJson: JSON.stringify({
    name: "={{$json.name}}",
    email: "={{$json.email}}",
    role: "user"
  })
}
```

### POST 请求(表单数据)

```javascript
{
  method: "POST",
  url: "https://api.example.com/upload",
  sendBody: true,
  bodyParametersUi: {
    parameter: [
      { name: "file", value: "={{$json.fileData}}" },
      { name: "filename", value: "={{$json.filename}}" }
    ]
  },
  sendHeaders: true,
  headerParameters: {
    "Content-Type": "multipart/form-data"
  }
}
```

### PUT/PATCH 请求(更新)

```javascript
{
  method: "PATCH",
  url: "https://api.example.com/users/={{$json.userId}}",
  sendBody: true,
  bodyParametersJson: JSON.stringify({
    status: "active",
    last_updated: "={{$now}}"
  })
}
```

### DELETE 请求

```javascript
{
  method: "DELETE",
  url: "https://api.example.com/users/={{$json.userId}}"
}
```

---

## 错误处理模式

### 模式 1:失败重试

```
HTTP Request(continueOnFail: true)
  → IF(发生错误)
    └→ Wait(5 秒)
    └→ HTTP Request(重试)
```

### 模式 2:回退 API

```
HTTP Request(主 API,continueOnFail: true)
  → IF(失败)
    └→ HTTP Request(回退 API)
```

### 模式 3:Error Trigger Workflow

**主 Workflow**:

```
HTTP Request → 处理数据
```

**错误 Workflow**:

```
Error Trigger
  → Set(提取错误详情)
  → Slack(告警团队)
  → Database(记录错误供分析)
```

### 模式 4:断路器

```javascript
// Code 节点 - 断路器逻辑
const failures = $json.recentFailures || 0;
const threshold = 5;

if (failures >= threshold) {
  throw new Error('Circuit breaker open - too many failures');
}

return [{ json: { canProceed: true } }];
```

---

## 响应转换

### 提取嵌套数据

```javascript
// Code 节点
const response = $input.first().json;

return response.data.items.map(item => ({
  json: {
    id: item.id,
    name: item.attributes.name,
    email: item.attributes.contact.email
  }
}));
```

### 展平数组

```javascript
// Code 节点 - 展平嵌套数组
const items = $input.all();
const flattened = items.flatMap(item =>
  item.json.results.map(result => ({
    json: {
      parent_id: item.json.id,
      ...result
    }
  }))
);

return flattened;
```

### 合并多个 API 响应

```
HTTP Request 1(用户)
  → Set(存储用户)
  → HTTP Request 2(每个用户的订单)
  → Merge(合并用户 + 订单)
```

---

## 测试与调试

### 1. 用 Manual Trigger 测试

将 Schedule 换成 Manual Trigger 以测试

### 2. 先用 Postman/Insomnia

- 在 n8n 外测试 API
- 理解响应结构
- 验证认证

### 3. 记录响应

```javascript
// Code 节点 - 记录以调试
console.log('API Response:', JSON.stringify($input.first().json, null, 2));
return $input.all();
```

### 4. 检查执行数据

- 在 n8n UI 中查看节点输出
- 检查 headers、body、状态码
- 验证数据结构

### 5. 正确使用二进制数据

用于文件下载:

```javascript
{
  method: "GET",
  url: "https://api.example.com/download/file.pdf",
  responseFormat: "file",  // 二进制数据很重要
  outputPropertyName: "data"
}
```

---

## 性能优化

### 1. 并行请求

用 **Split In Batches** + 多 item:

```
Set(创建 ID 数组)
  → Split In Batches(每批 10 项)
  → HTTP Request(并行处理 10 个)
  → Loop
```

### 2. 缓存

```
IF(检查缓存存在)
  ├─ [缓存命中]→ 使用缓存数据
  └─ [缓存未命中]→ HTTP Request → 存入缓存
```

### 3. 条件获取

仅在数据变更时获取:

```
HTTP Request(GET with If-Modified-Since header)
  → IF(status === 304)
    └→ 使用已有数据
  → IF(status === 200)
    └→ 处理新数据
```

### 4. 批 API 调用

若 API 支持批量操作:

```javascript
{
  method: "POST",
  url: "https://api.example.com/batch",
  bodyParametersJson: JSON.stringify({
    requests: $json.items.map(item => ({
      method: "GET",
      url: `/users/${item.id}`
    }))
  })
}
```

---

## 常见坑

### 1. ❌ 错误:硬编码 URL

```javascript
url: "https://api.example.com/prod/users"
```

### ✅ 正确:用环境变量

```javascript
url: "={{$env.API_BASE_URL}}/users"
```

### 2. ❌ 错误:凭据放在参数中

```javascript
headerParameters: {
  "Authorization": "Bearer sk-abc123xyz"  // ❌ 暴露!
}
```

### ✅ 正确:用凭据系统

```javascript
authentication: "predefinedCredentialType",
nodeCredentialType: "httpHeaderAuth"
```

### 3. ❌ 错误:无错误处理

```javascript
HTTP Request → Process(API 挂了则失败)
```

### ✅ 正确:处理错误

```javascript
HTTP Request(continueOnFail: true)→ IF(错误)→ 处理
```

### 4. ❌ 错误:大响应阻塞

同步处理 10,000 项

### ✅ 正确:用批处理

```
Split In Batches(100 项)→ 处理 → 循环
```

---

## 真实模板示例

来自 n8n 模板库(892 个 API 集成模板):

**GitHub to Notion**:

```
Schedule → HTTP Request(GitHub API)→ 转换 → HTTP Request(Notion API)
```

**Weather to Slack**:

```
Schedule → HTTP Request(天气 API)→ Set(格式化)→ Slack
```

**CRM 同步**:

```
Schedule → HTTP Request(CRM A)→ 转换 → HTTP Request(CRM B)
```

用 `search_templates({query: "http api"})` 查找更多!

---

## API 集成清单

### 规划

- [ ] 先用 Postman/curl 测试 API
- [ ] 理解响应结构
- [ ] 检查限流
- [ ] 审查认证方式
- [ ] 规划错误处理

### 实现

- [ ] 用凭据(永不硬编码)
- [ ] 配置正确的 HTTP method
- [ ] 设置正确的 headers(Content-Type、Accept)
- [ ] 需要时处理分页
- [ ] 正确添加 query 参数

### 错误处理

- [ ] 必要时设 `continueOnFail: true`
- [ ] 检查响应状态码
- [ ] 实现重试逻辑
- [ ] 加 Error Trigger workflow
- [ ] 失败时告警

### 性能

- [ ] 大数据集用批处理
- [ ] 必要时加限流
- [ ] 考虑缓存
- [ ] 用生产负载测试

### 安全

- [ ] 仅用 HTTPS
- [ ] secret 存入凭据
- [ ] 校验 API 响应
- [ ] 用环境变量

---

## 小结

**要点**:

1. 通过凭据系统**认证**(永不硬编码)
2. **错误处理**至关重要(continueOnFail + IF 检查)
3. 大数据集用**分页**
4. **限流**遵守 API 限制
5. **转换响应**以匹配你的需求

**模式**: Trigger → HTTP Request → 转换 → 动作 → 错误处理

**相关**:

- [webhook_processing.md](webhook_processing.md) - 接收 HTTP 请求
