# 数据库操作模式

**用例**: 在 workflow 中读、写、同步、管理数据库数据。

---

## 模式结构

```
Trigger → [Query/Read] → [Transform] → [Write/Update] → [Verify/Log]
```

**关键特征**: 数据持久化与同步

---

## 核心组件

### 1. 触发器

**选项**:

- **Schedule** - 周期同步/维护(最常见)
- **Webhook** - 事件驱动写入
- **Manual** - 一次性操作

### 2. 数据库读节点

**支持的数据库**:

- Postgres
- MySQL
- MongoDB
- Microsoft SQL
- SQLite
- Redis
- 以及更多(通过社区节点)

### 3. 转换

**用途**: 在不同数据库 schema 或格式间映射

**典型节点**:

- **Set** - 字段映射
- **Code** - 复杂转换
- **Merge** - 合并多源数据

### 4. 数据库写节点

**操作**:

- INSERT - 创建新记录
- UPDATE - 修改现有记录
- UPSERT - 插入或更新
- DELETE - 删除记录

### 5. 验证

**用途**: 确认操作成功

**方法**:

- 查询验证记录
- 计算受影响行数
- 记录结果

---

## 常见用例

### 1. 数据同步

**流程**: Schedule → 读源 DB → 转换 → 写目标 DB → 记录

**示例**(Postgres 到 MySQL 同步):

```
1. Schedule(每 15 分钟)
2. Postgres(SELECT * FROM users WHERE updated_at > {{$json.last_sync}})
3. IF(检查记录是否存在)
4. Set(映射 Postgres schema 到 MySQL schema)
5. MySQL(INSERT 或 UPDATE users)
6. Postgres(UPDATE sync_log SET last_sync = NOW())
7. Slack(通知: "Synced X users")
```

**增量同步查询**:

```sql
SELECT *
FROM users
WHERE updated_at > $1
ORDER BY updated_at ASC
LIMIT 1000
```

**参数**:

```javascript
{
  "parameters": [
    "={{$node['Get Last Sync'].json.last_sync}}"
  ]
}
```

### 2. ETL(Extract、Transform、Load)

**流程**: 从多源提取 → 转换 → 加载到数据仓库

**示例**(合并数据):

```
1. Schedule(每天 2:00)
2. [并行分支]
   ├─ Postgres(SELECT orders)
   ├─ MySQL(SELECT customers)
   └─ MongoDB(SELECT products)
3. Merge(合并所有数据)
4. Code(转换为数据仓库 schema)
5. Postgres(warehouse - INSERT into fact_sales)
6. Email(发送汇总报告)
```

### 3. 数据校验与清理

**流程**: Schedule → 查询 → 校验 → 更新/删除无效记录

**示例**(清理孤立记录):

```
1. Schedule(每周)
2. Postgres(SELECT users WHERE email IS NULL OR email = '')
3. IF(存在无效记录)
4. Postgres(UPDATE users SET status='inactive' WHERE email IS NULL)
5. Postgres(DELETE FROM users WHERE created_at < NOW() - INTERVAL '1 year' AND status='inactive')
6. Slack(告警: "Cleaned X invalid records")
```

### 4. 备份与归档

**流程**: Schedule → 查询 → 导出 → 存储

**示例**(归档旧记录):

```
1. Schedule(每月)
2. Postgres(SELECT * FROM orders WHERE created_at < NOW() - INTERVAL '2 years')
3. Code(转为 JSON)
4. Write File(存为 archive.json)
5. Google Drive(上传归档)
6. Postgres(DELETE FROM orders WHERE created_at < NOW() - INTERVAL '2 years')
```

### 5. 实时数据更新

**流程**: Webhook → 解析 → 更新数据库

**示例**(更新用户状态):

```
1. Webhook(接收状态更新)
2. Postgres(UPDATE users SET status = {{$json.body.status}} WHERE id = {{$json.body.user_id}})
3. IF(影响行数 > 0)
4. Redis(SET user:{{$json.body.user_id}}:status {{$json.body.status}})
5. Webhook Response({"success": true})
```

---

## 数据库节点配置

### Postgres

#### SELECT 查询

```javascript
{
  operation: "executeQuery",
  query: "SELECT id, name, email FROM users WHERE created_at > $1 LIMIT $2",
  parameters: [
    "={{$json.since_date}}",
    "100"
  ]
}
```

#### INSERT

```javascript
{
  operation: "insert",
  table: "users",
  columns: "id, name, email, created_at",
  values: [
    {
      id: "={{$json.id}}",
      name: "={{$json.name}}",
      email: "={{$json.email}}",
      created_at: "={{$now}}"
    }
  ]
}
```

#### UPDATE

```javascript
{
  operation: "update",
  table: "users",
  updateKey: "id",
  columns: "name, email, updated_at",
  values: {
    id: "={{$json.id}}",
    name: "={{$json.name}}",
    email: "={{$json.email}}",
    updated_at: "={{$now}}"
  }
}
```

#### UPSERT(INSERT ... ON CONFLICT)

```javascript
{
  operation: "executeQuery",
  query: `
    INSERT INTO users (id, name, email)
    VALUES ($1, $2, $3)
    ON CONFLICT (id)
    DO UPDATE SET name = $2, email = $3, updated_at = NOW()
  `,
  parameters: [
    "={{$json.id}}",
    "={{$json.name}}",
    "={{$json.email}}"
  ]
}
```

### MySQL

#### SELECT with JOIN

```javascript
{
  operation: "executeQuery",
  query: `
    SELECT u.id, u.name, o.order_id, o.total
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    WHERE u.created_at > ?
  `,
  parameters: [
    "={{$json.since_date}}"
  ]
}
```

#### Bulk INSERT

```javascript
{
  operation: "insert",
  table: "orders",
  columns: "user_id, total, status",
  values: $json.orders  // 对象数组
}
```

### MongoDB

#### Find Documents

```javascript
{
  operation: "find",
  collection: "users",
  query: JSON.stringify({
    created_at: { $gt: new Date($json.since_date) },
    status: "active"
  }),
  limit: 100
}
```

#### Insert Document

```javascript
{
  operation: "insert",
  collection: "users",
  document: JSON.stringify({
    name: $json.name,
    email: $json.email,
    created_at: new Date()
  })
}
```

#### Update Document

```javascript
{
  operation: "update",
  collection: "users",
  query: JSON.stringify({ _id: $json.user_id }),
  update: JSON.stringify({
    $set: {
      status: $json.status,
      updated_at: new Date()
    }
  })
}
```

---

## 批处理

### 模式 1:Split In Batches

**适用**: 处理大数据集以避免内存问题

```
Postgres(SELECT 10000 records)
  → Split In Batches(每批 100 项)
  → 转换
  → MySQL(写入批)
  → Loop(直到全部处理完)
```

### 模式 2:分页查询

**适用**: 数据库有百万级记录

```
Set(初始化: offset=0, limit=1000)
  → Loop Start
  → Postgres(SELECT * FROM large_table LIMIT {{$json.limit}} OFFSET {{$json.offset}})
  → IF(返回了记录)
    ├─ 处理记录
    ├─ Set(offset 增加 1000)
    └─ Loop back
  └─ [无记录] → 结束
```

**查询**:

```sql
SELECT * FROM large_table
ORDER BY id
LIMIT $1 OFFSET $2
```

### 模式 3:基于游标的分页

**大数据集性能更佳**:

```
Set(初始化: last_id=0)
  → Loop Start
  → Postgres(SELECT * FROM table WHERE id > {{$json.last_id}} ORDER BY id LIMIT 1000)
  → IF(返回了记录)
    ├─ 处理记录
    ├─ Code(从批次获取 max id)
    └─ Loop back
  └─ [无记录] → 结束
```

**查询**:

```sql
SELECT * FROM table
WHERE id > $1
ORDER BY id ASC
LIMIT 1000
```

---

## 事务处理

### 模式 1:BEGIN/COMMIT/ROLLBACK

**用于支持事务的数据库**:

```javascript
// 节点 1: 开始事务
{
  operation: "executeQuery",
  query: "BEGIN"
}

// 节点 2-N: 你的操作
{
  operation: "executeQuery",
  query: "INSERT INTO ...",
  continueOnFail: true
}

// 节点 N+1: 提交或回滚
{
  operation: "executeQuery",
  query: "={{$node['Operation'].json.error ? 'ROLLBACK' : 'COMMIT'}}"
}
```

### 模式 2:原子操作

**用数据库特性保证原子性**:

```sql
-- Upsert 示例(原子)
INSERT INTO inventory (product_id, quantity)
VALUES ($1, $2)
ON CONFLICT (product_id)
DO UPDATE SET quantity = inventory.quantity + $2
```

### 模式 3:错误时回滚

**手动错误回滚**:

```
Try Operations:
  Postgres(INSERT orders)
  MySQL(INSERT order_items)

Error Trigger:
  Postgres(DELETE FROM orders WHERE id = {{$json.order_id}})
  MySQL(DELETE FROM order_items WHERE order_id = {{$json.order_id}})
```

---

## 数据转换

### Schema 映射

```javascript
// Code 节点 - 映射 schemas
const sourceData = $input.all();

return sourceData.map(item => ({
  json: {
    // 源 → 目标映射
    user_id: item.json.id,
    full_name: `${item.json.first_name} ${item.json.last_name}`,
    email_address: item.json.email,
    registration_date: new Date(item.json.created_at).toISOString(),
    // 计算字段
    is_premium: item.json.plan_type === 'pro',
    // 默认值
    status: item.json.status || 'active'
  }
}));
```

### 数据类型转换

```javascript
// Code 节点 - 转换数据类型
return $input.all().map(item => ({
  json: {
    // 字符串转数字
    user_id: parseInt(item.json.user_id),
    // 字符串转日期
    created_at: new Date(item.json.created_at),
    // 数字转布尔
    is_active: item.json.active === 1,
    // JSON 字符串转对象
    metadata: JSON.parse(item.json.metadata || '{}'),
    // null 处理
    email: item.json.email || null
  }
}));
```

### 聚合

```javascript
// Code 节点 - 聚合数据
const items = $input.all();

const summary = items.reduce((acc, item) => {
  const date = item.json.created_at.split('T')[0];
  if (!acc[date]) {
    acc[date] = { count: 0, total: 0 };
  }
  acc[date].count++;
  acc[date].total += item.json.amount;
  return acc;
}, {});

return Object.entries(summary).map(([date, data]) => ({
  json: {
    date,
    count: data.count,
    total: data.total,
    average: data.total / data.count
  }
}));
```

---

## 性能优化

### 1. 使用索引

确保数据库有合适的索引:

```sql
-- 为同步查询加索引
CREATE INDEX idx_users_updated_at ON users(updated_at);

-- 为查找加索引
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

### 2. 限制结果集

始终用 LIMIT:

```sql
-- ✅ 良好
SELECT * FROM large_table
WHERE created_at > $1
LIMIT 1000

-- ❌ 差(无界)
SELECT * FROM large_table
WHERE created_at > $1
```

### 3. 使用预编译语句

参数化查询更快:

```javascript
// ✅ 良好 - 预编译语句
{
  query: "SELECT * FROM users WHERE id = $1",
  parameters: ["={{$json.id}}"]
}

// ❌ 差 - 字符串拼接
{
  query: "SELECT * FROM users WHERE id = '={{$json.id}}'"
}
```

### 4. 批量写入

一次写多条记录:

```javascript
// ✅ 良好 - 批量插入
{
  operation: "insert",
  table: "orders",
  values: $json.items  // 100 项的数组
}

// ❌ 差 - 循环中单条插入
// 100 个独立的 INSERT 语句
```

### 5. 连接池

在凭据中配置:

```javascript
{
  host: "db.example.com",
  database: "mydb",
  user: "user",
  password: "pass",
  // 连接池设置
  min: 2,
  max: 10,
  idleTimeoutMillis: 30000
}
```

---

## 错误处理

### 模式 1:检查影响行数

```
Database Operation(UPDATE users...)
  → IF({{$json.rowsAffected === 0}})
    └─ 告警: "No rows updated - record not found"
```

### 模式 2:约束违反

```javascript
// 数据库操作配 continueOnFail: true
{
  operation: "insert",
  continueOnFail: true
}

// 下一节点:检查错误
IF({{$json.error !== undefined}})
  → IF({{$json.error.includes('duplicate key')}})
    └─ 记录: "Record already exists - skipping"
  → ELSE
    └─ 告警: "Database error: {{$json.error}}"
```

### 模式 3:错误时回滚

```
Try Operations:
  → Database Write 1
  → Database Write 2
  → Database Write 3

Error Trigger:
  → 回滚操作
  → 告警管理员
```

---

## 安全最佳实践

### 1. 用参数化查询(防 SQL 注入)

```javascript
// ✅ 安全 - 参数化
{
  query: "SELECT * FROM users WHERE email = $1",
  parameters: ["={{$json.email}}"]
}

// ❌ 危险 - SQL 注入风险
{
  query: "SELECT * FROM users WHERE email = '={{$json.email}}'"
}
```

### 2. 最小权限访问

**创建专用 workflow 用户**:

```sql
-- ✅ 良好 - 有限权限
CREATE USER n8n_workflow WITH PASSWORD 'secure_password';
GRANT SELECT, INSERT, UPDATE ON orders TO n8n_workflow;
GRANT SELECT ON users TO n8n_workflow;

-- ❌ 差 - 权限过大
GRANT ALL PRIVILEGES TO n8n_workflow;
```

### 3. 校验输入数据

```javascript
// Code 节点 - 写入前校验
const email = $json.email;
const name = $json.name;

// 校验
if (!email || !email.includes('@')) {
  throw new Error('Invalid email address');
}

if (!name || name.length < 2) {
  throw new Error('Invalid name');
}

// 清理
return [{
  json: {
    email: email.toLowerCase().trim(),
    name: name.trim()
  }
}];
```

### 4. 加密敏感数据

```javascript
// Code 节点 - 存储前加密
const crypto = require('crypto');

const algorithm = 'aes-256-cbc';
const key = Buffer.from($credentials.encryptionKey, 'hex');
const iv = crypto.randomBytes(16);

const cipher = crypto.createCipheriv(algorithm, key, iv);
let encrypted = cipher.update($json.sensitive_data, 'utf8', 'hex');
encrypted += cipher.final('hex');

return [{
  json: {
    encrypted_data: encrypted,
    iv: iv.toString('hex')
  }
}];
```

---

## 常见坑

### 1. ❌ 错误:无界查询

```sql
SELECT * FROM large_table  -- 可能返回百万行
```

### ✅ 正确:用 LIMIT

```sql
SELECT * FROM large_table
ORDER BY created_at DESC
LIMIT 1000
```

### 2. ❌ 错误:查询中字符串拼接

```javascript
query: "SELECT * FROM users WHERE id = '{{$json.id}}'"
```

### ✅ 正确:参数化查询

```javascript
query: "SELECT * FROM users WHERE id = $1",
parameters: ["={{$json.id}}"]
```

### 3. ❌ 错误:多步操作无事务

```
INSERT into orders
INSERT into order_items  // 失败 → 孤立 order 记录
```

### ✅ 正确:用事务

```
BEGIN
INSERT into orders
INSERT into order_items
COMMIT(或错误时 ROLLBACK)
```

### 4. ❌ 错误:一次性处理所有 item

```
SELECT 1000000 records → 全处理 → OOM 错误
```

### ✅ 正确:批处理

```
SELECT records → Split In Batches(1000)→ 处理 → 循环
```

---

## 真实模板示例

来自 n8n 模板库(456 个数据库模板):

**数据同步**:

```
Schedule → Postgres(SELECT 新记录)→ 转换 → MySQL(INSERT)
```

**ETL 管道**:

```
Schedule → [多 DB 读]→ Merge → 转换 → Warehouse(INSERT)
```

**备份**:

```
Schedule → Postgres(SELECT 全部)→ JSON → Google Drive(upload)
```

用 `search_templates({query: "database"})` 查找更多!

---

## 数据库 Workflow 清单

### 规划

- [ ] 确定源与目标数据库
- [ ] 理解 schema 差异
- [ ] 规划转换逻辑
- [ ] 考虑大数据集的批大小
- [ ] 设计错误处理策略

### 实现

- [ ] 用参数化查询(永不拼接)
- [ ] 所有 SELECT 加 LIMIT
- [ ] 用合适的 operation(INSERT/UPDATE/UPSERT)
- [ ] 正确配置凭据
- [ ] 先用小数据集测试

### 性能

- [ ] 为查询加数据库索引
- [ ] 用批量操作
- [ ] 大数据集实现分页
- [ ] 配置连接池
- [ ] 监控查询执行时间

### 安全

- [ ] 用参数化查询(防 SQL 注入)
- [ ] 最小权限数据库用户
- [ ] 校验并清理输入
- [ ] 加密敏感数据
- [ ] 永不记录敏感数据

### 可靠性

- [ ] 必要时加事务处理
- [ ] 检查影响行数
- [ ] 处理约束违反
- [ ] 实现重试逻辑
- [ ] 加 Error Trigger workflow

---

## 小结

**要点**:

1. **始终用参数化查询**(防 SQL 注入)
2. 大数据集用**批处理**
3. 多步操作**事务处理**
4. **限制结果集**避免内存问题
5. 写入前**校验输入数据**

**模式**: Trigger → Query → Transform → Write → Verify

**相关**:

- [http_api_integration.md](http_api_integration.md) - 拉取数据存入 DB
- [scheduled_tasks.md](scheduled_tasks.md) - 周期性数据库维护
