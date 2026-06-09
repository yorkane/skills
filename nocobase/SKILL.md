---
name: nocobase-config
description: >-
  NocoBase 数据库优先开发模式。当用户需要数据库设计、数据表创建、数据接口、或任何涉及数据存储的场景时触发。
  核心原则：所有数据库表设计通过 NocoBase API 完成（建表 + 字段 + 关联），同时生成 SQL DDL 文档用于结构描述和版本管理，
  每个表设计完成后自动通过 table_ui 创建 NocoBase 后台管理界面。
  涵盖：数据建模、SQL 文档生成、管理 UI 自动创建、数据 CRUD 接口调用。
  本 Skill 通过本地 Python 脚本直接调用 NocoBase REST API，无需 MCP Server。
argument-hint: "[数据表描述或 SQL DDL]"
allowed-tools: shell, local file reads
---

# NocoBase 数据库优先开发模式

## 环境要求

运行本 Skill 脚本前，确保 NocoBase 已安装运行，并设置以下环境变量（两种认证方式任选其一）：

**方式一：API Key（推荐）**
```bash
export NOCO_BASE_URL="http://<服务器IP>:13000"
export NOCO_API_KEY="<JWT Token>"              # v2.1+: 纯 JWT Token（无前缀），作为 Bearer Token 使用
```

**方式二：邮箱密码**
```bash
export NOCO_BASE_URL="http://<服务器IP>:13000"
export NOCO_EMAIL="admin@nocobase.com"
export NOCO_PASSWORD="your-password"
```

> 首次部署 NocoBase 实例（Docker Compose + 外部 PostgreSQL）、建库、创建 API Key 等，详见 [install-and-init.md](./references/install-and-init.md)。

脚本位置：`.codebuddy/skills/nocobase-config/scripts/`

---

## 核心原则

**任何需要数据库的场景，都使用 NocoBase 进行数据库设计和数据接口调用。**

这意味着：

1. 不直接操作底层数据库（PostgreSQL/MySQL），而是通过 NocoBase API 完成所有建表、字段管理、关联关系操作
2. 同时生成一份 SQL DDL 文档，用于结构描述、版本管理和团队沟通
3. 每个数据库表设计完成后，自动通过 `table_ui` 创建 NocoBase 后台管理 UI
4. 所有数据读写通过 NocoBase REST API 接口（`records` 工具）完成

## 脚本调用方式

所有脚本通过 `python3 <script>` 调用，参数以 JSON 字符串传入：

```bash
# 方式1：命令行参数
python3 scripts/noco_collections.py '{"action":"list"}'

# 方式2：stdin 管道
echo '{"action":"list"}' | python3 scripts/noco_collections.py
```

### 可用脚本

| 脚本 | 说明 | action |
|------|------|--------|
| `noco_collections.py` | 数据表管理 | list, get, create, update, delete |
| `noco_fields.py` | 字段管理 | list, create, update, delete |
| `noco_records.py` | 记录 CRUD | list, create, update, delete, batch_create |
| `noco_routes.py` | 菜单路由管理 | list, create_group, create_page, delete |
| `noco_schemas.py` | UI Schema 管理 | create, get, update, delete |
| `noco_flow_models.py` | Flow Engine 模型 | create, attach, find, list, save, destroy |
| `noco_table_ui.py` | 一站式建表 UI | create, delete |
| `noco_plugins.py` | 插件管理 | list, enable, disable, init |

## 触发条件

用户提到以下意图时激活本 SKILL：

- "建表"、"创建数据表"、"数据库设计"
- "需要存储 xxx 数据"、"加个字段"、"添加关联"
- 提供了 SQL DDL（CREATE TABLE / ALTER TABLE）
- 提供了实体描述（如"需要一个订单表，包含..."）
- 需要数据 CRUD 操作（增删改查）
- 任何涉及数据持久化的需求

## 硬规则

1. **所有建表操作必须通过脚本调用 NocoBase REST API 完成**，禁止直接 SQL DDL 执行
2. **每个表创建后必须生成 SQL DDL 文档**，存放在项目的 `docs/sql/` 目录下
3. **每个表创建后必须调用 `noco_table_ui.py` 创建管理 UI**，确保立即可视化管理
4. **关联字段必须在基础字段之后创建**，遵循依赖顺序（父表 → 子表）
5. **禁止在 `fields` 数组中包含系统字段**（id/createdAt/updatedAt/createdBy/updatedBy 由模板自动创建）
6. **禁止关联字段的 `name` 与 `foreignKey` 同名**
7. **所有字段必须有中文标题**（通过 `uiSchema.title` 或 `title`）
8. 创建集合后必须同步字段：`noco_collections.py` action `get` 确认字段已生成

## 完整工作流（6 步 SOP）

### Step 1: 需求分析 & 实体建模

收到需求后，先做实体建模分析：

- 确定需要哪些数据表
- 确定每张表的字段、类型、中文标题
- 确定表之间的关联关系（m2o / o2m / m2m / o2o）
- 确定创建顺序（拓扑排序外键依赖）

输出：用自然语言向用户确认设计方案，列出表名、字段、关联关系。

### Step 2: 通过脚本创建数据表

使用 `noco_collections.py` 创建集合，使用 `noco_fields.py` 添加关联字段。

**创建顺序**：先父表（被引用表），后子表（有外键的表）。

**每张表的创建步骤**：

```bash
# 1. 创建集合
python3 scripts/noco_collections.py '{"action":"create","project":"xxx","tab":"yyy","title":"中文标题","fields":[{"name":"field1","interface":"input","title":"字段1"}]}'

# 2. 验证字段
python3 scripts/noco_collections.py '{"action":"get","name":"xxx_yyy-YYMMDD"}'

# 3. 如有关联 → 添加关联字段
python3 scripts/noco_fields.py '{"action":"create","collection":"xxx_yyy-YYMMDD","field":{"name":"category","interface":"m2o","type":"belongsTo","target":"categories","foreignKey":"category_id","title":"所属分类"}}'
```

**命名规则**：集合名自动生成为 `{project}_{tab}-{YYMMDD}` 格式（如 `poll_polls-260419`）。

**字段 interface 选择参考**：

| 数据类型 | interface | type | 说明 |
|---------|-----------|------|------|
| 短文本 | `input` | `string` | 名称、编码等 |
| 长文本 | `textarea` | `text` | 描述、备注、内容 |
| 整数 | `integer` | `bigInt` | 数量、计数、排序 |
| 小数/金额 | `number` | `float` | 价格、金额、比例 |
| 布尔 | `checkbox` | `boolean` | 是否、开关 |
| 下拉选择 | `select` | `string` | 状态、类型（需配合 uiSchema enum） |
| 日期 | `datePicker` | `date` | 日期选择 |
| 时间 | `timePicker` | `time` | 时间选择 |
| 日期时间 | `datetime` | `date` | 完整日期时间 |
| 邮箱 | `email` | `string` | 邮箱 |
| 电话 | `phone` | `string` | 电话号码 |
| URL | `url` | `string` | 链接 |
| 密码 | `password` | `string` | 加密存储 |
| 百分比 | `percent` | `float` | 百分比 |
| 富文本 | `richText` | `text` | HTML 内容 |
| 附件 | `attachment` | `belongsToMany` | 文件上传 |
| JSON | `json` | `json` | JSON 结构数据 |
| 多对一 | `m2o` | `belongsTo` | FK 在当前表 |
| 一对多 | `o2m` | `hasMany` | FK 在目标表 |
| 多对多 | `m2m` | `belongsToMany` | 通过中间表 |

### Step 3: 生成 SQL DDL 文档

为每个创建的表生成对应的 SQL DDL，保存在 `docs/sql/<collection_name>.sql`。

**SQL 生成规则参考** [sql-mapping.md](./references/sql-mapping.md)。

### Step 4: 自动创建管理 UI

每张表创建完成后，立即调用 `noco_table_ui.py` 创建管理页面：

```bash
python3 scripts/noco_table_ui.py '{"action":"create","collection_name":"xxx","group_title":"业务管理","group_icon":"📦","page_title":"订单管理","icon":"📋"}'
```

**分组策略**：
- 单表 → 默认分组"数据管理"
- 多表按业务域分组（如"订单管理"、"用户管理"）
- 有关联的表放在同一分组

**典型多表 UI 创建示例**：

```bash
# 第一张表 - 创建分组并设置图标
python3 scripts/noco_table_ui.py '{"action":"create","collection_name":"poll_polls-260419","group_title":"投票应用","group_icon":"🗳️","page_title":"投票管理","icon":"🗳️"}'

# 后续表 - 复用同一分组（stripEmoji 匹配）
python3 scripts/noco_table_ui.py '{"action":"create","collection_name":"poll_options-260419","group_title":"投票应用","group_icon":"🗳️","page_title":"选项管理","icon":"📋"}'
```

### Step 5: 数据操作（CRUD）

通过 `noco_records.py` 进行数据操作：

```bash
# 查询
python3 scripts/noco_records.py '{"action":"list","collection":"xxx","pageSize":20,"sort":["-created_at"]}'

# 创建
python3 scripts/noco_records.py '{"action":"create","collection":"xxx","record":{"field1":"value1"}}'

# 批量创建
python3 scripts/noco_records.py '{"action":"batch_create","collection":"xxx","records":[{"field1":"v1"},{"field1":"v2"}]}'

# 更新
python3 scripts/noco_records.py '{"action":"update","collection":"xxx","filterByTk":1,"record":{"field1":"new_value"}}'

# 删除
python3 scripts/noco_records.py '{"action":"delete","collection":"xxx","filterByTk":1}'
```

### Step 6: 验证

每步操作后进行验证：

1. **建表验证**：`noco_collections.py` action `get` → 确认字段完整
2. **字段验证**：检查 interface、type、title 是否正确
3. **关联验证**：确认 FK 字段和反向字段都已创建
4. **UI 验证**：`noco_routes.py` action `list` → 确认菜单页面已创建
5. **数据验证**：`noco_records.py` action `list` pageSize=1 → 确认可读写

## 多表场景决策矩阵

| 场景 | 操作顺序 | 说明 |
|------|---------|------|
| 单个独立表 | 建表 → SQL → UI | 无依赖，一步到位 |
| 两个关联表 | 父表 → SQL → UI → 子表 → SQL → UI | 先创建被引用表 |
| 三个以上关联表 | 拓扑排序 → 依次建表 → 批量 SQL → 批量 UI | 按依赖顺序 |
| 需要修改已有表 | fields create/update → 更新 SQL → 刷新 UI | 增量修改 |
| 需要删除表 | table_ui delete → collections delete → 删除 SQL | 先删 UI 后删表 |

## 常见陷阱

### P1: 关联字段 name 与 foreignKey 冲突
- `name` 是逻辑名（如 `category`），`foreignKey` 是数据库列名（如 `category_id`）
- 两者不能相同，否则报 `Naming collision`

### P2: 系统字段重复创建
- 模板自动创建 id/createdAt/updatedAt/createdBy/updatedBy（含底层 FK 列 createdById/updatedById）
- 不要在 fields 数组中手动添加这些字段

### P3: 关联字段缺少 type
- m2o 必须指定 `"type": "belongsTo"`
- o2m 必须指定 `"type": "hasMany"`
- m2m 必须指定 `"type": "belongsToMany"`

### P4: select 字段缺少 uiSchema
- `select` 类型需要通过 `uiSchema` 定义枚举选项

### P5: titleField 设置
- 创建表时系统自动选择文本字段作为 titleField
- 选择优先级：name → title → label → content → caption → subject → displayName → description → 第一个文本字段

### P6: 分组 emoji 重复创建
- 多个页面使用不同 `icon` 时，`group_icon` 必须显式指定
- 分组匹配逻辑会去除 emoji 前缀后比较

## 目录结构

```
project/
├── docs/
│   └── sql/                    ← SQL DDL 文档目录
│       ├── _schema_overview.md  ← 全库结构概览
│       ├── orders.sql            ← 单表 DDL
│       └── products.sql
└── .codebuddy/skills/nocobase-config/
    ├── SKILL.md                  ← 本文件
    ├── scripts/
    │   ├── noco_api.py           ← 核心 API 客户端
    │   ├── noco_constants.py     ← 常量与映射
    │   ├── noco_collections.py   ← 数据表管理
    │   ├── noco_fields.py        ← 字段管理
    │   ├── noco_records.py       ← 记录 CRUD
    │   ├── noco_routes.py        ← 菜单路由
    │   ├── noco_schemas.py       ← UI Schema
    │   ├── noco_flow_models.py   ← Flow Engine 模型
    │   ├── noco_table_ui.py      ← 一站式建表 UI
    │   └── noco_plugins.py       ← 插件启用管理
    └── references/
        ├── sql-mapping.md        ← SQL 类型映射
        ├── relation-patterns.md  ← 关联模式参考
        └── install-and-init.md   ← 安装部署指南
```

## 参考文档

| 文档 | 用途 |
|------|------|
| [sql-mapping.md](./references/sql-mapping.md) | NocoBase interface → SQL 类型完整映射表 |
| [relation-patterns.md](./references/relation-patterns.md) | 常见关联模式（订单、树形、继承、文件等） |
