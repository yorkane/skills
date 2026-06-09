---
name: n8n-workflow-patterns
description: 来自真实 n8n workflow 的成熟架构模式。构建新 workflow、设计 workflow 结构、选择 workflow 模式、规划 workflow 架构,或询问 webhook 处理、HTTP API 集成、数据库操作、AI agent workflow、批处理、定时任务时使用。当用户要求创建、构建或设计 n8n workflow、自动化流程、连接服务时(即使未明确提到"模式"),应始终查阅本 SKILL。覆盖 webhook、API、数据库、AI、批处理、定时自动化等架构。
---

# 全局原则(本 subagent 范围内)

- 创建 workflow 时,始终以 **manual trigger** 开始,验证通过后再添加其他触发器节点。
- 始终对 workflow 进行测试,保证 **manual trigger** 先验证通过再测试其他 trigger,确保 workflow 可以正确执行。
- **Code 节点始终使用 JavaScript** 编写(95% 场景最佳)。
- 涉及到数据库操作的，不要在Code节点中编写SQL语句，而是使用Database节点, 选择指定的表去操作。插入和更新时，节点中`Data Mode`选择 `Map Each Column Manually` 模式，指定要操作的字段
- 如需解析 HTML 页面,**先在本地测试通过**,再把代码写入 n8n Code 节点。
- 等待 workflow 执行时间通常**不要超过 15 秒**;超过此阈值的 workflow 应考虑拆分或异步化。
- 使用本 subagent 时,**优先从 [n8n-subagent 入口 SKILL.md](../../SKILL.md) 开始**,再按需进入下方 6 大分项。

# 连接 N8N(从 .env 读取凭证)

```bash
source ./.env && curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" "${N8N_API_URL}/api/v1/workflows"
```

---

# n8n Workflow 模式

构建 n8n workflow 的成熟架构模式。

---

## 6 大核心模式

基于真实 workflow 使用情况分析:

1. **[Webhook 处理](webhook_processing.md)**(最常用)
   - 接收 HTTP 请求 → 处理 → 输出
   - 模式: Webhook → 校验 → 转换 → 响应/通知

2. **[HTTP API 集成](http_api_integration.md)**
   - 从 REST API 获取 → 转换 → 存储/使用
   - 模式: 触发器 → HTTP Request → 转换 → 动作 → 错误处理

3. **[数据库操作](database_operations.md)**
   - 读/写/同步数据库数据
   - 模式: 定时 → 查询 → 转换 → 写入 → 验证

4. **[AI Agent Workflow](ai_agent_workflow.md)**
   - 带工具和记忆的 AI agent
   - 模式: 触发器 → AI Agent(模型 + 工具 + 记忆) → 输出

5. **[定时任务](scheduled_tasks.md)**
   - 周期性自动化 workflow
   - 模式: 定时 → 拉取 → 处理 → 投递 → 日志

6. **批处理**(本 SKILL 内含)
   - 处理受 API 速率限制的大数据集
   - 模式: 准备 → SplitInBatches → 逐批处理 → 累积 → 聚合

---

## 模式选择指南

### 何时使用各模式

**Webhook 处理** —— 用于:
- 接收外部系统的数据
- 构建集成(Slack 命令、表单提交、GitHub webhooks)
- 需要即时响应事件
- 示例: "接收 Stripe 支付 webhook → 更新数据库 → 发送确认"

**HTTP API 集成** —— 用于:
- 从外部 API 获取数据
- 与第三方服务同步
- 构建数据管道
- 示例: "拉取 GitHub issues → 转换 → 创建 Jira 工单"

**数据库操作** —— 用于:
- 数据库之间同步
- 定时运行数据库查询
- ETL workflow
- 示例: "读取 Postgres 记录 → 转换 → 写入 MySQL"

**AI Agent Workflow** —— 用于:
- 构建对话式 AI
- 需要带工具访问的 AI
- 多步推理任务
- 示例: "可搜索文档、查询数据库、发送邮件的 AI 聊天"

**定时任务** —— 用于:
- 周期性报告或汇总
- 周期性数据获取
- 维护任务
- 示例: "每天: 拉取分析数据 → 生成报告 → 邮件给团队"

**批处理** —— 用于:
- 处理超过 API 批量限制的大型数据集
- 需要跨多个 API 调用累积结果
- 嵌套循环(如多个类别 × 每个类别的分页 API 调用)
- 示例: "拉取 4 个市场 × 每 API 1000 条商品 → 聚合所有结果"

---

## 通用 Workflow 组件

所有模式共享以下构件:

### 1. 触发器
- **Webhook** - HTTP 端点(即时)
- **Schedule** - 基于 Cron 的定时(周期)
- **Manual** - 点击执行(测试)
- **Polling** - 定时检查变化(间隔)

### 2. 数据源
- **HTTP Request** - REST API
- **Database 节点** - Postgres、MySQL、MongoDB
- **Service 节点** - Slack、Google Sheets 等
- **Code** - 自定义 JavaScript/Python

### 3. 转换
- **Set** - 映射/转换字段
- **Code** - 复杂逻辑
- **IF/Switch** - 条件路由
- **Merge** - 合并数据流

### 4. 输出
- **HTTP Request** - 调用 API
- **Database** - 写入数据
- **Communication** - Email、Slack、Discord
- **Storage** - 文件、云存储

### 5. 错误处理
- **Error Trigger** - 捕获 workflow 错误
- **IF** - 检查错误条件
- **Stop and Error** - 显式失败
- **Continue On Fail** - 节点级设置

---

## Workflow 创建清单

构建任何 workflow 时,遵循以下清单:

### 规划阶段
- [ ] 确定模式(webhook、API、数据库、AI、定时)
- [ ] 列出所需节点(用 `search_nodes`)
- [ ] 理解数据流(输入 → 转换 → 输出)
- [ ] 规划错误处理策略

### 实现阶段
- [ ] 用合适的触发器创建 workflow
- [ ] 添加数据源节点
- [ ] 配置认证/凭据
- [ ] 添加转换节点(Set、Code、IF)
- [ ] 添加输出/动作节点
- [ ] 配置错误处理

### 校验阶段
- [ ] 校验每个节点配置(`validate_node`)
- [ ] 校验完整 workflow(`validate_workflow`)
- [ ] 用样本数据测试
- [ ] 处理边界情况(空数据、错误)

### 部署阶段
- [ ] 检查 workflow 设置(执行顺序、超时、错误处理)
- [ ] 用 `activateWorkflow` 操作激活
- [ ] 监控首次执行
- [ ] 记录 workflow 用途与数据流

---

## 数据流模式

### 线性流

```
Trigger → Transform → Action → End
```

**适用**: 简单 workflow,单一路径

### 分支流

```
Trigger → IF → [True 路径]
             └→ [False 路径]
```

**适用**: 根据条件执行不同动作

### 并行处理

```
Trigger → [Branch 1] → Merge
       └→ [Branch 2] ↗
```

**适用**: 可同时运行的独立操作

### 循环模式

```
Trigger → Split in Batches → Process → Loop(直到结束)
```

**适用**: 大数据集分块处理

### 错误处理模式

```
Main Flow → [Success 路径]
         └→ [Error Trigger → Error Handler]
```

**适用**: 需要独立的错误处理 workflow

---

## 批处理模式

### SplitInBatches 循环

SplitInBatches 节点将大数据集拆成更小的批次处理。理解其输出至关重要:

- `main[0]` = **done** —— 所有批次处理完成后触发一次
- `main[1]` = **each batch** —— 每批触发一次(这是循环体)

```
Prepare Items → SplitInBatches → [main[1]: Process Batch] → (loops back)
                                  [main[0]: Done] → Limit 1 → Aggregate
```

始终在 done 输出后加 **Limit 1** 节点。

### 跨迭代数据

循环结束后,`$('Node Inside Loop').all()` 只返回**最后一批**的 items。若要跨迭代累积,需在循环内的 Code 节点中使用 `$getWorkflowStaticData('global')`。完整模式见 n8n Code JavaScript SKILL。

### 嵌套循环

处理 N 个类别 × 每个类别 M 项(API 有批量限制时):

```
Define Categories (N items)
  → Outer Loop (SplitInBatches, batchSize=1)
    → Prepare category data
    → Inner Loop (SplitInBatches, batchSize=1000)
      → API Call → Verify → (loops back to Inner Loop via main[1])
    → Inner done[0] → Rate Limit Delay → back to Outer Loop
  → Outer done[0] → Limit 1 → Final Aggregate
```

**连接坑**: 内层 done[0] 必须连回**外层**循环的输入,而不是聚合节点。外层 done[0] 馈入最终聚合。

### API 分页

对于无多 ID 过滤的 API,使用 `id_from` + 时间窗口分页:

```
Schedule → Set Date Window → Fetch Page → Process
  → IF 还有更多? → [true] 更新 id_from → Fetch Page(循环)
                  → [false] → Aggregate → Output
```

### Dry-Run / 验证容差

测试时禁用 API 写入节点(用于 dry run),下游校验节点会收到请求体而不是响应。需要让校验具有容差:

```javascript
// 在校验 Code 节点中
const body = $input.first().json;
const looksLikeRequest = body.method && body.parameters && !body.status;
if (looksLikeRequest) {
  return [{ json: { status: 'SKIPPED', message: 'Upstream disabled for testing' }}];
}
// 正常响应校验逻辑继续...
```

---

## 集成相关坑

### Google Sheets

- **绝不要**在含公式列的 sheet 上用 `append` —— 会破坏公式。使用 HTTP Request 节点调用 Google Sheets API `values.update`(PUT),配 `googleApi` 凭据
- **写数字,不是字符串** —— 对依赖公式的列,字符串 "4.98" 会破坏 `ADD()` 公式。在 Code 节点中用 `parseFloat()`
- **逐项执行陷阱**: Google Sheets 节点对每个 input item 独立执行一次。若需单次批量写入,先在 Code 节点中聚合
- **UNFORMATTED_VALUE 返回数字**而非 "N/A" 这类文本 —— 在 Code 节点中显式过滤

### Google Drive

- **`convertToGoogleDocument: true` 创建的是 Google Doc(文本)**,**不是** Google Sheet —— 若上传 CSV 提供下载,省略此选项
- **CSV 下载链接格式**: `https://drive.google.com/uc?id={fileId}&export=download` —— 用它替代 `/view` 链接

### 双向阈值检查

比较数值(价格、数量、指标)时,务必检查两个方向:

```javascript
// ❌ 只捕捉增长
if (diff > threshold) { flag(); }

// ✅ 同时捕捉暴涨和暴跌 —— 两者都是数据质量信号
if (Math.abs(diff) > threshold) { flag(); }
```

---

## 常见坑

### 1. Webhook 数据结构

**问题**: 无法访问 webhook 负载数据

**解决**: 数据嵌套在 `$json.body` 下

```javascript
❌ {{$json.email}}
✅ {{$json.body.email}}
```

详见: n8n Expression Syntax SKILL

### 2. 多个输入项

**问题**: 节点处理全部 input items,但我只要一个

**解决**: 使用 "Execute Once" 模式或仅处理首项

```javascript
{{$json[0].field}}  // 仅首项
```

### 3. 认证问题

**问题**: API 调用报 401/403

**解决**:
- 正确配置凭据
- 用 "Credentials" 区,而不是 parameters
- 激活 workflow 前测试凭据

### 4. 节点执行顺序

**问题**: 节点执行顺序不符合预期

**解决**: 检查 workflow 设置 → Execution Order
- v0: 自上而下(旧)
- v1: 基于连接(推荐)

### 5. 表达式错误

**问题**: 表达式显示为纯文本

**解决**: 用 {{}} 包裹

- 详见 n8n Expression Syntax SKILL

---

## 与其他 SKILL 的协作

本 SKILL 与其他 SKILL 协同使用:

**n8n MCP Tools Expert** —— 用于:
- 查找本模式所需的节点(`search_nodes`)
- 理解节点 operations(`get_node`)
- 创建 workflow(`n8n_create_workflow`)
- 部署模板(`n8n_deploy_template`)
- 用 `ai_agents_guide()` 获取 AI 模式指导
- 用 `n8n_manage_datatable` 管理数据表

**n8n Expression Syntax** —— 用于:
- 在转换节点中写表达式
- 正确访问 webhook 数据(`{{$json.body.field}}`)
- 引用前序节点(`{{$node["Node Name"].json.field}}`)

**n8n Node Configuration** —— 用于:
- 配置模式中各节点的特定 operation
- 理解节点特定要求

**n8n Validation Expert** —— 用于:
- 校验 workflow 结构
- 修复校验错误
- 部署前确保 workflow 正确

---

## 模式统计

常见 workflow 模式:

**最常用触发器**:
1. Webhook - 35%
2. Schedule(定时任务) - 28%
3. Manual(测试/管理) - 22%
4. Service 触发器(Slack、email 等) - 15%

**最常用转换**:
1. Set(字段映射) - 68%
2. Code(自定义逻辑) - 42%
3. IF(条件路由) - 38%
4. Switch(多条件) - 18%

**最常用输出**:
1. HTTP Request(API) - 45%
2. Slack - 32%
3. Database 写入 - 28%
4. Email - 24%

**平均 Workflow 复杂度**:
- 简单(3-5 节点): 42%
- 中等(6-10 节点): 38%
- 复杂(11+ 节点): 20%

---

## 快速入门示例

### 示例 1:简单 Webhook → Slack

```
1. Webhook(path: "form-submit", POST)
2. Set(映射表单字段)
3. Slack(发消息到 #notifications)
```

### 示例 2:定时报告

```
1. Schedule(每天 9:00)
2. HTTP Request(拉取分析数据)
3. Code(聚合数据)
4. Email(发送格式化报告)
5. Error Trigger → Slack(失败时通知)
```

### 示例 3:数据库同步

```
1. Schedule(每 15 分钟)
2. Postgres(查询新记录)
3. IF(检查是否有记录)
4. MySQL(插入记录)
5. Postgres(更新同步时间戳)
```

### 示例 4:AI 助手

```
1. Webhook(接收聊天消息)
2. AI Agent
   ├─ OpenAI Chat Model (ai_languageModel)
   ├─ HTTP Request Tool (ai_tool)
   ├─ Database Tool (ai_tool)
   └─ Window Buffer Memory (ai_memory)
3. Webhook Response(发送 AI 回复)
```

### 示例 5:API 集成

```
1. Manual Trigger(用于测试)
2. HTTP Request(GET /api/users)
3. Split In Batches(每次处理 100)
4. Set(转换用户数据)
5. Postgres(upsert 用户)
6. Loop(回到步骤 3 直到结束)
```

---

## 详细模式文件

每个模式的完整指南:

- **[webhook_processing.md](webhook_processing.md)** - Webhook 模式、数据结构、响应处理
- **[http_api_integration.md](http_api_integration.md)** - REST API、认证、分页、重试
- **[database_operations.md](database_operations.md)** - 查询、同步、事务、批处理
- **[ai_agent_workflow.md](ai_agent_workflow.md)** - AI agent、工具、记忆、langchain 节点
- **[scheduled_tasks.md](scheduled_tasks.md)** - Cron 定时、报告、维护任务

---

## 真实模板示例

来自 n8n 模板库:

**模板 #2947**: Weather to Slack
- 模式: 定时任务
- 节点: Schedule → HTTP Request(天气 API) → Set → Slack
- 复杂度: 简单(4 节点)

**Webhook 处理**: 最常用模式
- 最常见: 表单提交、支付 webhook、聊天集成

**HTTP API**: 常见模式
- 最常见: 数据获取、第三方集成

**数据库操作**: 常见模式
- 最常见: ETL、数据同步、备份 workflow

**AI Agent**: 增长中
- 最常见: 聊天机器人、内容生成、数据分析

用 `search_templates` 与 `get_template` 查找示例!

---

## 最佳实践

### ✅ 应该

- 从能解决问题的最简模式开始
- 构建前规划 workflow 结构
- 所有 workflow 添加错误处理
- 激活前用样本数据测试
- 遵循 workflow 创建清单
- 使用描述性节点名
- 记录复杂 workflow(notes 字段)
- 部署后监控 workflow 执行

### ❌ 不应

- 一次性构建 workflow(要迭代!平均 56s/编辑)
- 激活前跳过校验
- 忽略错误场景
- 简单场景使用复杂模式
- 在参数中硬编码凭据
- 忘记处理空数据情况
- 无清晰边界地混合多种模式
- 不测试就部署

---

## 小结

**要点**:

1. **6 大核心模式**覆盖 90%+ workflow 用例
2. **Webhook 处理**是最常用模式
3. 每个 workflow 都要用 **workflow 创建清单**
4. **规划模式** → **选节点** → **构建** → **校验** → **部署**
5. 与其他 SKILL 协作以完成 workflow 开发全流程

**下一步**:

1. 确定用例模式
2. 读详细模式文件
3. 用 n8n MCP Tools Expert 找节点
4. 遵循 workflow 创建清单
5. 用 n8n Validation Expert 校验

**相关 SKILL**:
- n8n MCP Tools Expert - 查找与配置节点
- n8n Expression Syntax - 正确编写表达式
- n8n Validation Expert - 校验并修复错误
- n8n Node Configuration - 配置特定 operation
