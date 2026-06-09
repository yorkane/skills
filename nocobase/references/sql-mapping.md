# NocoBase Interface → SQL 类型完整映射

## 标量字段映射

| NocoBase interface | NocoBase type | PostgreSQL 类型 | MySQL 类型 | 说明 |
|---|---|---|---|---|
| `input` | `string` | `VARCHAR(255)` | `VARCHAR(255)` | 短文本 |
| `textarea` | `text` | `TEXT` | `TEXT` | 长文本 |
| `richText` | `text` | `TEXT` | `LONGTEXT` | 富文本 HTML |
| `email` | `string` | `VARCHAR(255)` | `VARCHAR(255)` | 邮箱 |
| `phone` | `string` | `VARCHAR(20)` | `VARCHAR(20)` | 电话 |
| `password` | `string` | `VARCHAR(255)` | `VARCHAR(255)` | 加密密码 |
| `url` | `string` | `VARCHAR(1024)` | `VARCHAR(1024)` | URL |
| `number` | `float` | `DOUBLE PRECISION` | `DOUBLE` | 浮点数 |
| `integer` | `bigInt` | `BIGINT` | `BIGINT` | 整数 |
| `percent` | `float` | `DOUBLE PRECISION` | `DOUBLE` | 百分比 |
| `float` | `float` | `DOUBLE PRECISION` | `DOUBLE` | 浮点数 |
| `checkbox` | `boolean` | `BOOLEAN` | `TINYINT(1)` | 布尔 |
| `select` | `string` | `VARCHAR(64)` | `VARCHAR(64)` | 枚举选择 |
| `radioGroup` | `string` | `VARCHAR(64)` | `VARCHAR(64)` | 单选按钮组 |
| `checkboxGroup` | `json` | `JSONB` | `JSON` | 多选 |
| `datePicker` | `date` | `DATE` 或 `TIMESTAMPTZ` | `DATE` 或 `DATETIME` | 日期/日期时间 |
| `timePicker` | `time` | `TIME` | `TIME` | 时间 |
| `datetime` | `date` | `TIMESTAMPTZ` | `DATETIME` | 完整日期时间 |
| `dateOnly` | `date` | `DATE` | `DATE` | 仅日期 |
| `colorPicker` | `string` | `VARCHAR(32)` | `VARCHAR(32)` | 颜色值 |
| `icon` | `string` | `VARCHAR(64)` | `VARCHAR(64)` | 图标名 |
| `json` | `json` | `JSONB` | `JSON` | JSON 数据 |
| `sort` | `integer` | `INTEGER` | `INT` | 排序序号 |
| `attachment` | `belongsToMany` | _(中间表)_ | _(中间表)_ | 附件关联 |

## 语义推断映射

根据字段名模式推断更精确的 interface：

| 字段名模式 | 推荐 interface | 说明 |
|---|---|---|
| `*_email` / `email` | `email` | 邮箱格式 |
| `*_phone` / `*_tel` / `*_mobile` | `phone` | 电话号码 |
| `*_url` / `*_link` / `*_website` | `url` | 网址 |
| `*_password` / `*_pwd` | `password` | 密码 |
| `*_color` / `*_colour` | `colorPicker` | 颜色 |
| `*_icon` | `icon` | 图标 |
| `sort` / `*_sort` / `*_order` | `sort` | 排序 |
| `status` (有限值) | `select` | 状态枚举 |
| `*_type` (有限值) | `select` | 类型枚举 |
| `is_*` / `has_*` / `*_flag` | `checkbox` | 布尔标记 |
| `*_content` / `*_body` / `*_html` | `richText` | 富文本内容 |
| `*_price` / `*_amount` / `*_total` / `*_fee` | `number` | 金额 |
| `*_count` / `*_quantity` / `*_qty` / `*_num` | `integer` | 计数 |
| `*_rate` / `*_percent` / `*_ratio` | `percent` | 百分比 |
| `*_code` / `*_no` (有规律) | `input` | 编码/序号 |

## 关联字段映射

| NocoBase interface | NocoBase type | SQL 表现 | FK 位置 |
|---|---|---|---|
| `m2o` | `belongsTo` | `BIGINT REFERENCES target(id)` | 当前表 |
| `o2m` | `hasMany` | _(反向，FK 在目标表)_ | 目标表 |
| `m2m` | `belongsToMany` | 中间表 + 两个 FK | 中间表 |
| `o2o` (owner) | `hasOne` | _(反向)_ | 目标表 |
| `o2o` (owned) | `belongsTo` | `BIGINT REFERENCES target(id)` | 当前表 |

## 系统字段（general 模板自动创建）

| 字段名 | SQL 类型 | 说明 |
|---|---|---|
| `id` | `BIGSERIAL PRIMARY KEY` | 主键 |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | 创建时间 |
| `updated_at` | `TIMESTAMPTZ DEFAULT NOW()` | 更新时间 |
| `created_by_id` | `BIGINT` | 创建人 |
| `updated_by_id` | `BIGINT` | 更新人 |

## SQL DDL 生成模板

```sql
-- ============================================================
-- Table: <name> (<title>)
-- Auto-managed by NocoBase, do not execute directly
-- ============================================================

CREATE TABLE IF NOT EXISTS <name> (
    id              BIGSERIAL       PRIMARY KEY,
    <field_name>    <sql_type>      DEFAULT <default>,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW(),
    created_by_id   BIGINT,
    updated_by_id   BIGINT
);

COMMENT ON TABLE <name> IS '<title>';
-- 每个字段的注释
COMMENT ON COLUMN <name>.<field> IS '<field_title>';

-- 外键约束 (m2o 关联)
-- ALTER TABLE <name> ADD CONSTRAINT fk_<name>_<field>
--     FOREIGN KEY (<fk_column>) REFERENCES <target>(id);
```
