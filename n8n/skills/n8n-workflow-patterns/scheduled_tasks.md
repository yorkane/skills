# 定时任务模式

**用例**: 按计划自动运行的周期性自动化 workflow。

---

## 模式结构

```
Schedule Trigger → [拉取数据] → [处理] → [投递] → [记录/通知]
```

**关键特征**: 基于时间的自动化执行

---

## 核心组件

### 1. Schedule Trigger

**用途**: 在指定时间执行 workflow

**模式**:

- **Interval** - 每 X 分钟/小时/天
- **Cron** - 特定时间(高级)
- **Days & Hours** - 简单的周期计划

### 2. 数据源

**常见来源**:

- HTTP Request(API)
- 数据库查询
- 文件读取
- 特定服务节点

### 3. 处理

**典型操作**:

- 过滤/转换数据
- 聚合统计
- 生成报告
- 检查条件

### 4. 投递

**输出渠道**:

- Email
- Slack/Discord/Teams
- 文件存储
- 数据库写入

### 5. 记录

**用途**: 跟踪执行历史

**方法**:

- 数据库日志条目
- 文件追加
- 监控服务

---

## Schedule 配置

### Interval 模式

**最佳场景**: 简单的周期任务

**示例**:

```javascript
// 每 15 分钟
{
  mode: "interval",
  interval: 15,
  unit: "minutes"
}

// 每 2 小时
{
  mode: "interval",
  interval: 2,
  unit: "hours"
}

// 每天午夜
{
  mode: "interval",
  interval: 1,
  unit: "days"
}
```

### Days & Hours 模式

**最佳场景**: 特定日期与时间

**示例**:

```javascript
// 工作日 9:00
{
  mode: "daysAndHours",
  days: ["monday", "tuesday", "wednesday", "thursday", "friday"],
  hour: 9,
  minute: 0
}

// 每周一 18:00
{
  mode: "daysAndHours",
  days: ["monday"],
  hour: 18,
  minute: 0
}
```

### Cron 模式(高级)

**最佳场景**: 复杂计划

**示例**:

```javascript
// 每个工作日 9:00
{
  mode: "cron",
  expression: "0 9 * * 1-5"
}

// 每月 1 号午夜
{
  mode: "cron",
  expression: "0 0 1 * *"
}

// 工作时间(9:00 - 17:00)每 15 分钟
{
  mode: "cron",
  expression: "*/15 9-17 * * 1-5"
}
```

**Cron 格式**: `minute hour day month weekday`
- `*` = 任意值
- `*/15` = 每 15 个单位
- `1-5` = 范围(周一至周五)
- `1,15` = 特定值

**Cron 示例**:

```
0 */6 * * *      每 6 小时
0 9,17 * * *     每天 9:00 与 17:00
0 0 * * 0        每周日午夜
*/30 * * * *     每 30 分钟
0 0 1,15 * *     每月 1 号与 15 号
```

---

## 常见用例

### 1. 每日报告

**流程**: Schedule → 拉取数据 → 聚合 → 格式化 → Email

**示例**(销售报告):

```
1. Schedule(每天 9:00)

2. Postgres(查询昨天的销售)
   SELECT date, SUM(amount) as total, COUNT(*) as orders
   FROM orders
   WHERE date = CURRENT_DATE - INTERVAL '1 day'
   GROUP BY date

3. Code(计算指标)
   - 总收入
   - 订单数
   - 平均订单价值
   - 与前一天对比

4. Set(格式化邮件正文)
   Subject: 每日销售报告 - {{$json.date}}
   Body: 含指标的格式化 HTML

5. Email(发给 team@company.com)

6. Slack(摘要发到 #sales)
```

### 2. 数据同步

**流程**: Schedule → 从源拉取 → 转换 → 写入目标

**示例**(CRM 到数据仓库同步):

```
1. Schedule(每小时)

2. Set(存储上次同步时间)
   SELECT MAX(synced_at) FROM sync_log

3. HTTP Request(拉取上次同步以来的新 CRM 联系人)
   GET /api/contacts?updated_since={{$json.last_sync}}

4. IF(检查是否存在新记录)

5. Set(转换 CRM schema 到数据仓库 schema)

6. Postgres(数据仓库 - INSERT 新联系人)

7. Postgres(UPDATE sync_log SET synced_at = NOW())

8. IF(发生错误)
   └─ Slack(告警 #data-team)
```

### 3. 监控与健康检查

**流程**: Schedule → 检查端点 → 宕机时告警

**示例**(网站可用性监控):

```
1. Schedule(每 5 分钟)

2. HTTP Request(GET https://example.com/health)
   - timeout: 10 秒
   - continueOnFail: true

3. IF(status !== 200 OR 响应时间 > 2000ms)

4. Redis(检查告警冷却 - 不刷屏)
   - Key: alert:website_down
   - TTL: 30 分钟

5. IF(未发送最近告警)

6. [告警动作]
   ├─ Slack(通知 #ops-team)
   ├─ PagerDuty(创建事故)
   ├─ Email(alert@company.com)
   └─ Redis(设告警冷却)

7. Postgres(记录可用性检查结果)
```

### 4. 清理与维护

**流程**: Schedule → 查找旧数据 → 归档/删除 → 报告

**示例**(数据库清理):

```
1. Schedule(每周日 2:00)

2. Postgres(查找旧记录)
   SELECT * FROM logs
   WHERE created_at < NOW() - INTERVAL '90 days'
   LIMIT 10000

3. IF(记录存在)

4. Code(导出为 JSON 用于归档)

5. Google Drive(上传归档文件)
   - Filename: logs_archive_{{$now.format('YYYY-MM-DD')}}.json

6. Postgres(DELETE 归档记录)
   DELETE FROM logs
   WHERE id IN ({{$json.archived_ids}})

7. Slack(报告: "归档 X 记录,删除 Y 记录")
```

### 5. 数据富化

**流程**: Schedule → 查找不完整记录 → 富化 → 更新

**示例**(用公司数据富化联系人):

```
1. Schedule(每晚 3:00)

2. Postgres(查找无公司数据的联系人)
   SELECT id, email, domain FROM contacts
   WHERE company_name IS NULL
   AND created_at > NOW() - INTERVAL '7 days'
   LIMIT 100

3. Split In Batches(每批 10 个联系人)

4. HTTP Request(调用 Clearbit 富化 API)
   - 对每个联系人域名
   - 限流: 批次间等 1 秒

5. Set(映射 API 响应到数据库 schema)

6. Postgres(UPDATE 联系人的公司数据)

7. Wait(1 秒 - 限流)

8. Loop(回到步骤 4 直到所有批处理完)

9. Email(摘要: "富化了 X 联系人")
```

### 6. 备份自动化

**流程**: Schedule → 导出数据 → 压缩 → 存储 → 验证

**示例**(数据库备份):

```
1. Schedule(每天 2:00)

2. Code(执行 pg_dump)
   const { exec } = require('child_process');
   exec('pg_dump -h db.example.com mydb > backup.sql')

3. Code(压缩备份)
   const zlib = require('zlib');
   // 压缩 backup.sql 为 backup.sql.gz

4. AWS S3(上传压缩备份)
   - Bucket: backups
   - Key: db/backup-{{$now.format('YYYY-MM-DD')}}.sql.gz

5. AWS S3(列出旧备份)
   - 仅保留最近 30 天

6. AWS S3(删除旧备份)

7. IF(发生错误)
   ├─ PagerDuty(紧急告警)
   └─ Email(备份失败!)
   ELSE
   └─ Slack(#devops: "✅ 备份完成")
```

### 7. 内容发布

**流程**: Schedule → 拉取内容 → 格式化 → 发布

**示例**(自动社交媒体帖):

```
1. Schedule(工作时间每 3 小时)
   - Cron: 0 9,12,15,18 * * 1-5

2. Google Sheets(读内容队列)
   - Sheet: "Scheduled Posts"
   - 过滤: status=pending AND publish_time <= NOW()

3. IF(有可用帖)

4. HTTP Request(在帖中缩短 URL)

5. HTTP Request(POST 到 Twitter API)

6. HTTP Request(POST 到 LinkedIn API)

7. Google Sheets(更新 status=published)

8. Slack(通知 #marketing: "已发: {{$json.title}}")
```

---

## 时区考虑

### 设置 Workflow 时区

```javascript
// 在 workflow 设置中
{
  timezone: "America/New_York"  // EST/EDT
}
```

### 常用时区

```
America/New_York    - 东部(美)
America/Chicago     - 中部(美)
America/Denver      - 山地(美)
America/Los_Angeles - 太平洋(美)
Europe/London       - GMT/BST
Europe/Paris        - CET/CEST
Asia/Tokyo          - JST
Australia/Sydney    - AEDT
UTC                 - 协调世界时
```

### 处理夏令时

**最佳实践**: 用时区感知的调度

```javascript
// ❌ 差: UTC 调度 "本地 9:00"
// 在 DST 转换时会差 1 小时

// ✅ 良好: 设置 workflow 时区
{
  timezone: "America/New_York",
  schedule: {
    mode: "daysAndHours",
    hour: 9  // 始终 9:00 东部时间,无论 DST
  }
}
```

---

## 错误处理

### 模式 1:Error Trigger Workflow

**主 workflow**: 正常执行
**错误 workflow**: 告警与恢复

**主**:

```
Schedule → 拉取 → 处理 → 投递
```

**错误**:

```
Error Trigger(针对主 workflow)
  → Set(提取错误详情)
  → Slack(#ops-team: "❌ 定时任务失败")
  → Email(管理员告警)
  → Postgres(记录错误供分析)
```

### 模式 2:重试带回退

```
Schedule → HTTP Request(continueOnFail: true)
  → IF(错误)
    ├─ Wait(5 分钟)
    ├─ HTTP Request(重试 1)
    └─ IF(仍错)
      ├─ Wait(15 分钟)
      ├─ HTTP Request(重试 2)
      └─ IF(仍错)
        └─ 告警管理员
```

### 模式 3:部分失败处理

```
Schedule → Split In Batches
  → 处理(continueOnFail: true)
  → Code(跟踪成功与失败)
  → 报告:
    "✅ 已处理: 95/100"
    "❌ 失败: 5/100"
```

---

## 性能优化

### 1. 批处理

大数据集:

```
Schedule → 查询(LIMIT 10000)
  → Split In Batches(每批 100)
  → 处理批次
  → 循环
```

### 2. 并行处理

操作独立时:

```
Schedule
  ├─ [分支 1: 更新 DB]
  ├─ [分支 2: 发邮件]
  └─ [分支 3: 生成报告]
  → Merge(等待全部) → 最终通知
```

### 3. 已在运行时跳过

防止执行重叠:

```
Schedule → Redis(检查锁)
  → IF(锁存在)
    └─ 结束(跳过本次执行)
  → ELSE
    ├─ Redis(设锁,TTL 30 分钟)
    ├─ [执行 workflow]
    └─ Redis(删除锁)
```

### 4. 无数据时早退出

无内容时不浪费时间:

```
Schedule → 查询(检查是否有工作)
  → IF(无结果)
    └─ 结束 workflow(提前退出)
  → ELSE
    └─ 处理数据
```

---

## 监控与日志

### 模式 1:执行日志表

```sql
CREATE TABLE workflow_executions (
  id SERIAL PRIMARY KEY,
  workflow_name VARCHAR(255),
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  status VARCHAR(50),
  records_processed INT,
  error_message TEXT
);
```

**记录执行**:

```
Schedule
  → Set(记录开始)
  → [Workflow 逻辑]
  → Postgres(INSERT execution log)
```

### 模式 2:指标收集

```
Schedule → [执行]
  → Code(计算指标)
    - 时长
    - 处理记录数
    - 成功率
  → HTTP Request(发到监控系统)
    - Datadog、Prometheus 等
```

### 模式 3:摘要通知

每日/每周执行摘要:

```
Schedule(每天 18:00)→ 查询执行日志
  → Code(汇总今天的执行)
  → Email(摘要报告)
    "今天的 Workflow 执行:
     - 24/24 成功
     - 0 失败
     - 平均时长: 2.3 分钟"
```

---

## 测试定时 Workflow

### 1. 用 Manual Trigger 测试

**开发模式**:

```
Manual Trigger(用于测试)
  → [相同的 workflow 逻辑]
  → [输出]

// 测试后,换成 Schedule Trigger
```

### 2. 用不同时间测试

```javascript
// Code 节点 - 模拟不同时间
const testTime = new Date('2024-01-15T09:00:00Z');
return [{ json: { currentTime: testTime } }];
```

### 3. Dry Run 模式

```
Schedule → Set(dryRun: true)
  → IF(dryRun)
    └─ 记录将发生什么(不执行)
  → ELSE
    └─ 正常执行
```

### 4. 短间隔用于测试

```javascript
// 测试: 每 1 分钟
{
  mode: "interval",
  interval: 1,
  unit: "minutes"
}

// 生产: 每 1 小时
{
  mode: "interval",
  interval: 1,
  unit: "hours"
}
```

---

## 常见坑

### 1. ❌ 错误:忽略时区

```javascript
Schedule(9:00)  // 哪个时区的 9:00?
```

### ✅ 正确:设置 workflow 时区

```javascript
// workflow 设置
{
  timezone: "America/New_York"
}
```

### 2. ❌ 错误:执行重叠

```
Schedule(每 5 分钟)→ 长时间任务(10 分钟)
// 两次执行同时跑!
```

### ✅ 正确:加执行锁

```
Schedule → Redis(检查锁)
  → IF(已锁)→ 跳过
  → ELSE → 执行
```

### 3. ❌ 错误:无错误处理

```
Schedule → API 调用 → 处理(静默失败)
```

### ✅ 正确:加错误 workflow

```
主: Schedule → 执行
错误: Error Trigger → 告警
```

### 4. ❌ 错误:一次性处理全部数据

```
Schedule → SELECT 1000000 记录 → 处理(OOM)
```

### ✅ 正确:批处理

```
Schedule → SELECT 用分页 → Split In Batches → 处理
```

### 5. ❌ 错误:硬编码日期

```javascript
query: "SELECT * FROM orders WHERE date = '2024-01-15'"
```

### ✅ 正确:动态日期

```javascript
query: "SELECT * FROM orders WHERE date = CURRENT_DATE - INTERVAL '1 day'"
```

---

## 真实模板示例

来自 n8n 模板库:

**模板 #2947**(Weather to Slack):

```
Schedule(每天 8:00)
  → HTTP Request(天气 API)
  → Set(格式化消息)
  → Slack(发到 #general)
```

**每日备份**:

```
Schedule(每晚 2:00)
  → Postgres(导出数据)
  → Google Drive(上传)
  → Email(确认)
```

**监控**:

```
Schedule(每 5 分钟)
  → HTTP Request(健康检查)
  → IF(宕机)→ PagerDuty 告警
```

用 `search_templates({query: "schedule"})` 查找更多!

---

## 定时 Workflow 清单

### 规划

- [ ] 定义调度频率(interval、cron、days & hours)
- [ ] 设置 workflow 时区
- [ ] 估算执行时长
- [ ] 规划失败与重试
- [ ] 考虑时区与 DST

### 实现

- [ ] 配置 Schedule Trigger
- [ ] 在设置中设 workflow 时区
- [ ] 为无操作情况加早退出
- [ ] 大数据实现批处理
- [ ] 加执行日志

### 错误处理

- [ ] 创建 Error Trigger workflow
- [ ] 实现重试逻辑
- [ ] 加告警通知
- [ ] 记录错误供分析
- [ ] 优雅处理部分失败

### 监控

- [ ] 记录每次执行(开始、结束、状态)
- [ ] 跟踪指标(时长、记录、成功率)
- [ ] 设置每日/每周摘要
- [ ] 连续失败时告警
- [ ] 监控资源使用

### 测试

- [ ] 先用 Manual Trigger 测试
- [ ] 验证时区行为
- [ ] 测试错误场景
- [ ] 检查执行重叠
- [ ] 验证输出质量

### 部署

- [ ] 记录 workflow 用途
- [ ] 设置监控
- [ ] 配置告警
- [ ] 在 n8n UI 中激活 workflow ⚠️ **需手动激活**(API/MCP 不能激活)
- [ ] 在生产测试(先短间隔)
- [ ] 监控前几次执行

---

## 进阶模式

### 动态调度

**根据条件改变调度**:

```
Schedule(每小时检查)→ Code(检查是否该跑)
  → IF(工作时间且工作日)
    └─ 执行 workflow
  → ELSE
    └─ 跳过
```

### 依赖调度

**链式 workflow**:

```
Workflow A(每天 2:00): 数据同步
  → 完成后 → 触发 Workflow B

Workflow B: 生成报告(依赖新数据)
```

### 条件执行

**根据外部因素跳过**:

```
Schedule → HTTP Request(检查 feature flag)
  → IF(特性启用)
    └─ 执行
  → ELSE
    └─ 跳过
```

---

## 小结

**要点**:

1. **显式设置 workflow 时区**
2. 大数据集用**批处理**
3. **错误处理**至关重要(Error Trigger + 重试)
4. 用执行锁**防止重叠**
5. **监控与记录**所有执行

**模式**: Schedule → 拉取 → 处理 → 投递 → 记录

**调度模式**:

- **Interval**: 简单周期(每 X 分钟/小时)
- **Days & Hours**: 特定日期与时间
- **Cron**: 高级复杂调度

**相关**:

- [http_api_integration.md](http_api_integration.md) - 定时拉取数据
- [database_operations.md](database_operations.md) - 定时数据库任务
- [webhook_processing.md](webhook_processing.md) - 调度的替代方案
