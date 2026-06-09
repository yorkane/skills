# 误报指南

何时校验警告可接受,以及如何处理。

---

## 什么是误报?

**定义**: 技术上算"问题"但在你的特定场景下可接受的校验警告

**要点**: 不是所有警告都要修复!

许多警告取决于场景:
- 约 40% 的警告在特定场景下可接受
- 用 `ai-friendly` profile 可减少 60% 误报

---

## 理念

### ✅ 良好实践

```
1. 用 'runtime' profile 运行校验
2. 修复所有错误
3. 评估每个警告
4. 判断在你的场景下是否可接受
5. 记录为什么接受
6. 自信部署
```

### ❌ 不良实践

```
1. 盲目忽视所有警告
2. 用 'minimal' profile 避开警告
3. 不理解风险就部署
```

---

## 常见误报

### 1. 缺少错误处理

**警告**:

```json
{
  "type": "best_practice",
  "message": "No error handling configured",
  "suggestion": "Add continueOnFail: true and retryOnFail: true"
}
```

#### 可接受场景

**✅ 开发/测试 Workflow**

```javascript
// 测试 workflow - 失败是显而易见的
{
  "name": "Test Slack Integration",
  "nodes": [{
    "type": "n8n-nodes-base.slack",
    "parameters": {
      "resource": "message",
      "operation": "post",
      "channel": "#test"
      // 无错误处理 - 测试场景 OK
    }
  }]
}
```

**理由**: 测试时你希望看到失败。

**✅ 非关键通知**

```javascript
// 锦上添花的通知
{
  "name": "Optional Slack Notification",
  "parameters": {
    "channel": "#general",
    "text": "FYI: Process completed"
    // 即便失败也无所谓
  }
}
```

**理由**: 通知失败不影响核心功能。

**✅ Manual 触发 Workflow**

```javascript
// 手动 workflow - 用户在盯
{
  "nodes": [{
    "type": "n8n-nodes-base.webhook",
    "parameters": {
      "path": "manual-test"
      // 无错误处理 - 用户会手动重试
    }
  }]
}
```

**理由**: 用户在场能看到并处理错误。

#### 应修复场景

**❌ 生产自动化**

```javascript
// 错误: 关键 workflow 没有错误处理
{
  "name": "Process Customer Orders",
  "nodes": [{
    "type": "n8n-nodes-base.postgres",
    "parameters": {
      "query": "INSERT INTO orders..."
      // ❌ 应该有错误处理!
    }
  }]
}
```

**修复**:

```javascript
{
  "parameters": {
    "query": "INSERT INTO orders...",
    "continueOnFail": true,
    "retryOnFail": true,
    "maxTries": 3,
    "waitBetweenTries": 1000
  }
}
```

**❌ 关键集成**

```javascript
// 错误: 支付处理没有错误处理
{
  "name": "Process Payment",
  "type": "n8n-nodes-base.stripe"
  // ❌ 支付失败必须处理!
}
```

---

### 2. 无重试逻辑

**警告**:

```json
{
  "type": "best_practice",
  "message": "External API calls should retry on failure",
  "suggestion": "Add retryOnFail: true, maxTries: 3, waitBetweenTries: 1000"
}
```

#### 可接受场景

**✅ 自带重试的 API**

```javascript
// Stripe、Twilio 等已内置重试
{
  "type": "n8n-nodes-base.stripe"
  // Stripe API 自行重试
}
```

**✅ 幂等操作**

```javascript
// 重复执行结果相同的操作
{
  "operation": "update",
  // 更新为相同值是安全的
}
```

**✅ Manual 触发**

```javascript
// 人工触发
{
  "type": "n8n-nodes-base.manualTrigger"
  // 用户可手动重试
}
```

#### 应修复场景

**❌ 不稳定的外部服务**

```javascript
// 错误: 老旧的第三方 API
{
  "type": "n8n-nodes-base.httpRequest",
  "url": "https://flaky-api.example.com"
  // ❌ 应该加重试!
}
```

**❌ 生产自动化**

```javascript
// 错误: 关键生产 workflow
{
  "name": "Production Sync",
  "schedule": "*/15 * * * *"
  // ❌ 失败需要自动重试
}
```

---

### 3. 缺少限流

**警告**:

```json
{
  "type": "best_practice",
  "message": "No rate limiting configured for high-volume API calls"
}
```

#### 可接受场景

**✅ 内部 API(无限流)**

```javascript
// 内部服务,无外部限流
{
  "url": "https://internal.company.com/api"
  // 内部 API,通常无限流
}
```

**✅ 低量 Workflow**

```javascript
// 每天 1 次
{
  "schedule": "0 9 * * *"
  // 1 天 1 次,无需限流
}
```

**✅ 服务端限流的 API**

```javascript
// 服务端自行限流
{
  "type": "n8n-nodes-base.sendgrid"
  // SendGrid 等服务端限流
}
```

#### 应修复场景

**❌ 公共 API(高量)**

```javascript
// 错误: Twitter API 有限流
{
  "type": "n8n-nodes-base.twitter"
  // ❌ 公共 API 严格限流
}
```

**❌ 实时 workflow**

```javascript
// 错误: 高频触发
{
  "trigger": "webhook",
  "expectedVolume": "1000/hour"
  // ❌ 需要限流
}
```

---

### 4. 无界数据库查询

**警告**:

```json
{
  "type": "performance",
  "message": "SELECT without LIMIT can return massive datasets"
}
```

#### 可接受场景

**✅ 已知的小数据集**

```javascript
// 已知最多 100 行的配置表
{
  "query": "SELECT * FROM config"
  // 已知是小表
}
```

**✅ 聚合查询**

```javascript
// COUNT、SUM 等聚合,不需要 LIMIT
{
  "query": "SELECT COUNT(*) FROM users"
}
```

**✅ 开发/测试**

```javascript
// 仅测试用
{
  "query": "SELECT * FROM users"
  // 仅在开发环境
}
```

#### 应修复场景

**❌ 大表上的生产查询**

```javascript
// 错误: 大表,无 LIMIT
{
  "query": "SELECT * FROM users WHERE active = true"
  // ❌ 可能返回百万行
}
```

**修复**:

```javascript
{
  "query": "SELECT * FROM users WHERE active = true LIMIT 1000"
}
```

---

### 5. 缺少输入校验

**警告**:

```json
{
  "type": "best_practice",
  "message": "Webhook should validate input data"
}
```

#### 可接受场景

**✅ 内部 webhook(受信源)**

```javascript
// 来自内部系统的 webhook
{
  "path": "internal-events"
  // 内部系统,数据可信
}
```

**✅ 开发中**

```javascript
// 还在开发
{
  "path": "dev-test"
  // 测试用
}
```

#### 应修复场景

**❌ 公共 webhook**

```javascript
// 错误: 暴露在公网的 webhook
{
  "path": "public-form"
  // ❌ 需要校验输入
}
```

**修复**: 在 webhook 后加 IF/Switch 节点校验必填字段

---

### 6. 硬编码凭据

**警告**:

```json
{
  "type": "security",
  "message": "Hardcoded API key detected",
  "severity": "high"
}
```

#### 应始终修复

**没有可接受场景**!硬编码凭据是安全风险。

**修复**: 用 n8n 凭据系统,而不是硬编码:

```javascript
// ❌ 错误
{
  "url": "https://api.example.com",
  "headers": {
    "Authorization": "Bearer sk-1234567890"
  }
}

// ✅ 正确 - 使用凭据
{
  "url": "https://api.example.com",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "httpHeaderAuth"
}
```

---

## 处理策略

### 策略 1:渐进式严格度

按场景调整 profile:

```
开发中:      profile: "ai-friendly"  // 减少噪声
生产部署前:   profile: "runtime"      // 平衡校验
生产部署后:   profile: "strict"       // 最大化
```

### 策略 2:按 Workflow 类型分类

```javascript
// 关键 workflow:始终 strict
if (workflow.critical) {
  validate_workflow({profile: "strict"})
}

// 内部工具 workflow:runtime 即可
if (workflow.internal) {
  validate_workflow({profile: "runtime"})
}

// 实验性 workflow:ai-friendly
if (workflow.experimental) {
  validate_workflow({profile: "ai-friendly"})
}
```

---

## 该不该修这个警告?

用这个决策框架:

### 应始终修复

- 安全问题(硬编码凭据、SQL 注入)
- 实际错误(找不到节点、缺必填字段)
- 真实数据丢失风险

### 通常应修复

- 生产 workflow 的缺错误处理
- 关键 API 的缺重试
- 性能影响(无界查询、O(n²) 循环)

### 经常可接受

- 测试 workflow 的缺错误处理
- 内部 API 的缺限流
- 已知小数据集的无界查询

### 始终可接受

- 非关键通知
- 一次性 workflow
- 受信任源的输入

---

## 已知误报问题

### Issue #304: IF 节点元数据警告

**问题**: IF 节点报告缺 `conditions.options` 元数据

**实际**: 自动清洗会在保存时添加

**行动**: 忽略,自动修复

### Issue #306: Switch 分支数

**问题**: 警告 Switch 有 N 个规则但只有 M 个输出

**实际**: 有意的!未连接的规则作为默认分支

**行动**: 仅在真的不匹配预期时修复

### Issue #338: 测试模式下的凭据校验

**问题**: 测试时凭据校验失败

**实际**: 测试模式可关闭凭据检查

**行动**: 部署到生产前测试凭据有效性

---

## 小结

**关键决策点**:

1. 修复所有错误(必须)
2. 评估警告(场景相关)
3. 记录接受的警告
4. 用合适的 profile

**决策框架**:

- 关键生产工作 → 修复一切
- 内部工具 → 接受少量警告
- 开发/测试 → 宽松的校验

**记住**: 警告是建议,不是要求。
