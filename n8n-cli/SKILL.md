---
name: n8n-cli
description: n8n-cli 构建与运维支持。指导远程状态检查、导入、预览(dry-run)、部署(apply)和 linter 执行。
allowed-tools: Read, Bash, Glob, Grep
---

# n8n-cli 运维技能

使用 n8n-cli 管理 n8n 工作流的技能指南。

## 环境配置

n8n-cli 已全局安装，使用前需确认当前文件夹下存在 `.env` 文件（**不要读取 .env 的内容**）。

`.env` 文件中应包含 `N8N_API_URL` 和 `N8N_API_KEY`，n8n-cli 会自动读取。

```bash
test -f .env && echo ".env 已存在，n8n-cli 可直接使用"
```

如果 `.env` 不存在，提示用户创建。

## 常用命令

### 1. 查看远程工作流状态

**查看指定工作流：**
```bash
n8n-cli workflow get <workflow-id>
n8n-cli -o table workflow get <workflow-id>
n8n-cli workflow get <workflow-id> > /tmp/remote-workflow.json
```

**列出工作流：**
```bash
n8n-cli workflow list
n8n-cli -o table workflow list
n8n-cli workflow list --active
```

### 2. 导入工作流（远程 → 本地）

**导入前先检查本地文件格式：**
```bash
ls -la definitions/*<workflow-id>* definitions/**/*<workflow-id>*
```

根据格式选择导入方式：
- `.json` 文件：仅使用 `--ids`
- `.yaml`/`.yml` 文件：同时使用 `--ids` 和 `--yaml`

**导入指定工作流：**
```bash
n8n-cli import --ids=<workflow-id>
n8n-cli import --ids=<workflow-id> --yaml
n8n-cli import --ids=<workflow-id> -d ./my-dir
```

**导入多个工作流：**
```bash
n8n-cli import --ids=abc123,def456,ghi789
```

**导入所有工作流：**
```bash
n8n-cli import
```

**附加选项：**

| 选项 | 说明 |
|------|------|
| `--include-archived` | 包含已归档的工作流 |
| `--cleanup-orphans` | 删除没有匹配 ID 的孤立文件 |
| `-t, --threshold <int>` | 代码外提取的最小行数（默认：0） |
| `--dry-run` | 仅预览（不修改文件） |
| `--tags <tags>` | 按标签名过滤（逗号分隔，AND 条件） |

### 3. 预览变更（Dry-run）

**部署前务必先执行 dry-run 验证：**
```bash
n8n-cli apply --dry-run
n8n-cli apply --dry-run --ids=<workflow-id>
n8n-cli apply --dry-run -d definitions/path/to/workflow.json
```

**示例输出：**
```
=== CREATE (1 workflow) ===
  + new-workflow.json (name: "New Automation")

=== UPDATE (2 workflows) ===
  ~ existing.json (id: R2cTI0LDzCJSnvNG)
    - name: "Old Name" -> "New Name"
    - nodes: 3 -> 5 nodes

=== SKIP (1 workflow) ===
  = unchanged.json (no changes)

Summary (dry-run): 1 to create, 2 to update, 1 unchanged
```

### 4. 部署（Apply）

**AI 助手必须始终使用 --ids 指定工作流：**

```bash
n8n-cli apply --ids=<workflow-id>
n8n-cli apply -d definitions/path/to/workflow.json
n8n-cli apply --ids=<workflow-id> --force
```

**禁止操作：**
```bash
n8n-cli apply -d definitions/
n8n-cli apply
```

**附加选项：**

| 选项 | 说明 |
|------|------|
| `--from-git-changes <spec>` | 仅应用 Git diff 中变更的文件 |
| `--yaml` / `--no-yaml` | 启用/禁用 YAML 处理 |
| `--warn-duplicates` | 同名工作流已存在时发出警告 |
| `--no-auto-tag` | 禁用自动标签（managed-as-code） |
| `-p, --project <id>` | 指定目标项目 ID |

**环境变量：**
- `APPLY_FILTER_BY_TAGS` - 按标签名过滤（逗号分隔，AND 条件）

**Git diff 模式：**
```bash
n8n-cli apply --from-git-changes origin/main..HEAD
n8n-cli apply --from-git-changes origin/main..HEAD --dry-run
n8n-cli apply --from-git-changes HEAD~3..HEAD
```

三方冲突检测：指定 `--from-git-changes` 时，通过比较 Base（参考点）、Local（当前）和 Remote（服务端）来识别真正的冲突。

### 5. Linter（质量检查）

**Linter 已集成到 CLI 中，无需单独构建。不支持位置参数，必须用 `-f` 或 `-d` 指定文件/目录。**

```bash
n8n-cli lint -f definitions/<filename>
n8n-cli lint -d ./definitions/example-project
n8n-cli lint -d ./definitions
n8n-cli lint -d ./definitions -o json
```

**选项：**

| 选项 | 说明 |
|------|------|
| `-d, --dir <path>` | 定义文件目录 |
| `-f, --file <files...>` | 指定文件 |
| `-c, --config <path>` | 配置文件路径（.n8nlintrc.json） |
| `--disable-rule <name>` | 禁用指定规则 |
| `--list-rules` | 列出所有规则 |
| `-o, --output <format>` | 输出格式：text, json（默认：text） |

**规则（11 条）：**

| 规则 | 级别 | 说明 |
|------|------|------|
| `json-syntax` | error | JSON 语法检查 |
| `required-fields` | error | 必填字段（name, nodes, connections）检查 |
| `connection-reference` | error | 连接目标节点是否存在 |
| `webhook-id-required` | error | webhook 和 formTrigger 节点是否有 webhookId 字段 |
| `orphaned-node` | warning | 孤立节点检测 |
| `implicit-json-ref` | warning | 隐式 `$json` 引用检测 |
| `expression-mode-prefix` | warning | 缺少 `=` 前缀检测 |
| `ai-agent-output-ref` | warning | AI Agent 输出引用错误检测 |
| `node-params` | warning | 节点参数 schema 验证 |
| `node-ref-field-check` | warning | 引用字段是否存在 |
| `node-ref-cardinality` | warning | `.item`/`.first()` 用法验证 |

**配置文件（.n8nlintrc.json）：**

```json
{
  "rules": {
    "json-syntax": "error",
    "required-fields": "error",
    "orphaned-node": "warning",
    "implicit-json-ref": "off"
  }
}
```

配置文件查找顺序：
1. `--config` 指定的路径
2. 目标目录下的 `.n8nlintrc.json` / `.n8nlintrc`
3. 当前目录下的 `.n8nlintrc.json` / `.n8nlintrc`

### 6. 格式化（Formatter）

**注意：`fmt` 接受位置参数作为文件（没有 `-f` 选项）。**

```bash
n8n-cli fmt definitions/<filename>
n8n-cli fmt definitions/file1.yaml definitions/file2.yaml
n8n-cli fmt -d ./definitions
n8n-cli fmt -d ./definitions --dry-run
```

### 7. 测试（Test）

**通过测试 Webhook 测试工作流：**

```bash
n8n-cli test <workflow-id>
n8n-cli test <workflow-id> -d '{"email": "test@example.com"}'
n8n-cli test <workflow-id> --wait-execution
n8n-cli test <workflow-id> --activate
n8n-cli test <workflow-id> --dry-run
n8n-cli test <workflow-id> --show-inputs
```

**选项：**

| 选项 | 说明 |
|------|------|
| `-d, --data <json>` | 测试数据（JSON 字符串） |
| `--timeout <duration>` | HTTP 超时（默认：30s） |
| `--wait-execution` | 等待执行完成并显示结果 |
| `--activate` | 自动激活未激活的工作流 |
| `--dry-run` | 仅检查 Webhook URL |
| `--show-inputs` | 显示输入参数 |
| `-o, --output <fmt>` | 输出格式：json, table（默认：json） |

**从本地文件测试：**
```bash
n8n-cli test ./definitions/my-workflow.json
```

### 8. 执行记录（Execution）

**列出最近执行记录：**

```bash
n8n-cli execution list
n8n-cli -o table execution list
n8n-cli execution list --status error
n8n-cli execution list --status success
n8n-cli execution list --workflow <workflow-id>
n8n-cli execution list --limit 5
n8n-cli execution list --workflow <workflow-id> --status error --limit 10
```

**获取执行详情：**

```bash
n8n-cli execution get <execution-id>
n8n-cli -o table execution get <execution-id>
n8n-cli -o table execution get <execution-id> --show-data
```

**`execution list` 选项：**

| 选项 | 说明 |
|------|------|
| `-w, --workflow <id>` | 按工作流 ID 过滤 |
| `-s, --status <status>` | 按状态过滤（success, error, running, waiting） |
| `-l, --limit <n>` | 最大记录数（默认：20） |

**`execution get` 选项：**

| 选项 | 说明 |
|------|------|
| `--show-data` | 在输出中包含节点执行摘要 |

**错误信息字段：**

| 字段 | 说明 |
|------|------|
| Error Node | 发生错误的节点 |
| Error Message | 错误消息 |
| Error Details | 附加错误描述（如有） |
| Last Node | 最后执行的节点 |

**典型调试流程：**

```bash
n8n-cli -o table execution list --status error --limit 5
n8n-cli -o table execution get <execution-id> --show-data
```

### 9. 格式转换（Convert）

**在 JSON 和 YAML 格式之间转换工作流文件（仅本地操作，无需 API）：**

```bash
n8n-cli convert -d ./definitions --format yaml
n8n-cli convert -d ./definitions --format json --ids <workflow-id>
n8n-cli convert -d ./definitions --format yaml --dry-run
n8n-cli convert -d ./definitions --format yaml --keep
n8n-cli convert --format yaml definitions/<filename>.json
```

**选项：**

| 选项 | 说明 |
|------|------|
| `--format <format>` | 目标格式：`json` 或 `yaml`（必填） |
| `-d, --directory <dir>` | 扫描工作流文件的目录 |
| `--ids <ids>` | 逗号分隔的工作流 ID |
| `--tags <tags>` | 按标签过滤（逗号分隔，AND 条件） |
| `-t, --threshold <n>` | 代码外提取的最小行数（JSON→YAML） |
| `--dry-run` | 仅预览 |
| `--keep` | 保留原始文件 |

**行为说明：**
- JSON→YAML：生成 YAML 文件 + `_subfiles/` 目录存放外提取的代码
- YAML→JSON：解析 `!include` 引用并删除 `_subfiles/`
- 已是目标格式的文件会被跳过
- 转换后默认删除原文件，使用 `--keep` 可保留

### 10. 数据表（Data Tables）

**管理数据表和行：**

```bash
n8n-cli data-tables list
n8n-cli -o table data-tables list
n8n-cli data-tables get <data-table-id>
n8n-cli data-tables create --name "My Table" --columns '[{"name":"col1","type":"string"},{"name":"col2","type":"number"}]'
n8n-cli data-tables update <data-table-id> --name "New Name"
n8n-cli data-tables delete <data-table-id> --force
```

**行操作：**

```bash
n8n-cli data-tables rows list <data-table-id>
n8n-cli data-tables rows list <data-table-id> --limit 10 --search "keyword"
n8n-cli data-tables rows insert <data-table-id> --data '[{"col1":"hello","col2":42}]'
n8n-cli data-tables rows insert <data-table-id> --data '[{"col1":"value"}]' --return-type all
n8n-cli data-tables rows update <data-table-id> \
  --filter '{"type":"and","filters":[{"columnName":"col1","condition":"eq","value":"hello"}]}' \
  --data '{"col2":99}' --dry-run
n8n-cli data-tables rows upsert <data-table-id> \
  --filter '{"type":"and","filters":[{"columnName":"col1","condition":"eq","value":"hello"}]}' \
  --data '{"col1":"hello","col2":100}'
n8n-cli data-tables rows delete <data-table-id> \
  --filter '{"type":"and","filters":[{"columnName":"col1","condition":"eq","value":"hello"}]}' \
  --force
```

**选项：**

| 子命令 | 关键选项 |
|--------|----------|
| `list` | `--limit`, `--filter <json>`, `--sort-by <field:dir>` |
| `rows list` | `--limit`, `--filter <json>`, `--sort-by`, `--search <text>` |
| `rows insert` | `-d, --data <json>`（必填）, `--return-type count\|id\|all` |
| `rows update` | `--filter <json>`（必填）, `-d, --data <json>`（必填）, `--return-data`, `--dry-run` |
| `rows upsert` | `--filter <json>`（必填）, `-d, --data <json>`（必填）, `--return-data`, `--dry-run` |
| `rows delete` | `--filter <json>`（必填）, `--return-data`, `--dry-run`, `--force` |

支持的列类型：`string`, `number`, `boolean`, `date`, `json`。

### 11. 数据流追踪（Trace）

**分析工作流中的数据流和基数：**

```bash
n8n-cli trace -f definitions/<filename>
n8n-cli trace -f definitions/<filename> -o json
```

**输出列：**

| 列 | 说明 |
|----|------|
| Node | 节点名称 |
| Type | n8n 节点类型 |
| Cardinality | 输出基数：`1:1`, `1:N`, `N:1`, `pass-through`, `variable`, `unknown` |
| Items | 预估输出项数：`1`, `N`, `?`, `loop` 等 |
| Inputs | 上游节点 |
| Outputs | 下游节点 |

**基数含义：**

| 基数 | 含义 |
|------|------|
| `1:1` | 一个输入项产生一个输出项 |
| `1:N` | 一个输入项产生多个输出项 |
| `N:1` | 多个输入项产生一个输出项（如聚合） |
| `pass-through` | 项原样传递（如 Filter, If, Set） |
| `variable` | 输出数量取决于运行时行为（如 Code, HTTP Request） |
| `unknown` | 节点类型没有基数定义 |

**解读预估项数中的 `?`：**

当节点显示 `?` 时，表示无法静态确定基数。AI 助手应：
1. 检查节点的 `operation` 参数——许多节点（Notion, GoogleSheets, BigQuery）有操作相关的基数
2. 检查 `limit` 参数或 SQL `LIMIT` 子句是否限制了输出
3. 对于 `Code` 节点，阅读代码判断输出是 1 还是 N 项
4. 对于 `HTTP Request`，检查响应是数组还是单个对象
5. **不要假设 `?` 意味着"多条"**——它只表示"静态分析时未知"

### 12. 凭证管理（Credential）

**查看可用凭证：**

```bash
n8n-cli credential list
n8n-cli credential get <id>
n8n-cli credential schema <typeName>
```

**设计工作流时：**
- 如果节点使用外部服务，验证对应凭证是否存在
- 如果凭证缺失，提示用户在 n8n UI 中创建

### 13. 节点 Schema（Node Schema）

**查看节点参数定义：**

```bash
n8n-cli node-schema list
n8n-cli node-schema list --output json
n8n-cli node-schema dump --type n8n-nodes-base.slack
n8n-cli node-schema dump -o ./schemas
```

**前提条件：** `n8n-nodes-base` 和 `@n8n/n8n-nodes-langchain` 必须已安装在 `node_modules` 中。

**list 选项：**

| 选项 | 说明 |
|------|------|
| `--output json` | JSON 格式输出 |
| `--group <group>` | 按分组过滤（trigger, transform 等） |

**dump 选项：**

| 选项 | 说明 |
|------|------|
| `--type <nodeType>` | 指定节点类型 schema（如 `n8n-nodes-base.slack`） |
| `-o, --output-dir <dir>` | 将所有节点导出为单独文件到指定目录 |

## 典型工作流操作

### 编辑工作流

```bash
# 1. 检查 .env
test -f .env && echo "OK"

# 2. 编辑本地文件（使用 n8n-workflow 技能）

# 3. Lint 检查
n8n-cli lint -f definitions/<filename>

# 4. Dry-run 验证
n8n-cli apply --dry-run --ids=<workflow-id>

# 5. 部署
n8n-cli apply --ids=<workflow-id>

# 6. 部署后再做一次 dry-run 确认结果
n8n-cli apply --dry-run --ids=<workflow-id>

# 7. 测试（可选）
n8n-cli test <workflow-id> --wait-execution
```

### 拉取远程变更

```bash
# 1. 检查本地文件格式（重要！）
ls -la definitions/*<workflow-id>* definitions/**/*<workflow-id>*

# 2. 查看远程状态
n8n-cli workflow get <workflow-id> > /tmp/remote.json

# 3. 与本地对比（如需要）
diff definitions/path/to/workflow.json /tmp/remote.json

# 4. 按格式导入
# JSON 格式：
n8n-cli import --ids=<workflow-id>
# YAML 格式：
n8n-cli import --ids=<workflow-id> --yaml
```

## 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 错误（JSON 无效、API 错误、网络故障） |
| 2 | 检测到冲突（仅 dry-run，远程较新时）或规则违反（lint 错误） |

## 故障排除

### 认证错误
```
Error: authentication failed
```
→ 检查 `.env` 中的 `N8N_API_KEY`

### 网络错误
```
Error: network error
```
→ 检查 `.env` 中的 `N8N_API_URL`

### 冲突错误
```
Error: conflict: remote workflow has been modified since your local file
```
→ 检查远程变更，使用 `--force` 覆盖或导入后重新编辑

## AI 助手指南

### 会话开始时

检查 `.env` 是否存在（不读取内容）：
```bash
test -f .env && echo ".env 已存在"
```

### 编辑工作流后（开发反馈循环）

1. **Lint 检查** - `n8n-cli lint -f definitions/<filename>`
2. **Dry-run 验证变更** - `n8n-cli apply --dry-run --ids=<workflow-id>`
3. **主动部署测试**（始终指定单个工作流）
   - 除非用户明确拒绝，否则在开发期间也要部署
   - 部署后分享 n8n UI URL
   - 如果发现问题，重复修复 → 部署循环
4. **部署后 Dry-run** - 确认无冲突

### 从远程导入时

**重要：保持本地格式**

1. **检查本地文件格式**
   ```bash
   ls -la definitions/*<workflow-id>* definitions/**/*<workflow-id>*
   ```

2. **确定格式**
   - `.json` → JSON 格式
   - `.yaml`/`.yml` → YAML 格式

3. **使用对应格式选项导入**
   ```bash
   # JSON 格式
   n8n-cli import --ids=<workflow-id>
   # YAML 格式
   n8n-cli import --ids=<workflow-id> --yaml
   ```

### 禁止操作

- 读取 `.env` 文件的内容
- 对整个目录执行 apply（必须使用 `--ids`）
- 随意使用 `--force`
- **导入前不检查本地文件格式**
