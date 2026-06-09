# 常见关联模式参考

## 模式 1: 主从表（订单 → 订单项）

最常见的一对多模式。

**表结构**：
- `orders` — 订单主表
- `order_items` — 订单明细

**创建顺序**：orders → order_items

```
# Step 1: 创建 orders
collections { action: "create", name: "orders", title: "订单", fields: [
  { name: "order_no", interface: "input", uiSchema: { title: "订单号" } },
  { name: "total_amount", interface: "number", uiSchema: { title: "总金额" } },
  { name: "status", interface: "select", uiSchema: { title: "状态" } }
]}

# Step 2: 创建 order_items
collections { action: "create", name: "order_items", title: "订单明细", fields: [
  { name: "product_name", interface: "input", uiSchema: { title: "商品名称" } },
  { name: "quantity", interface: "integer", uiSchema: { title: "数量" } },
  { name: "price", interface: "number", uiSchema: { title: "单价" } },
  { name: "subtotal", interface: "number", uiSchema: { title: "小计" } }
]}

# Step 3: 创建关联 order_items → orders
fields { action: "create", collection: "order_items", field: {
  name: "order",
  interface: "m2o",
  type: "belongsTo",
  target: "orders",
  foreignKey: "order_id",
  uiSchema: { title: "所属订单" },
  reverseField: {
    name: "items",
    interface: "o2m",
    type: "hasMany",
    uiSchema: { title: "订单明细" }
  }
}}
```

**对应 SQL**：
```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    order_no VARCHAR(255),
    total_amount DOUBLE PRECISION DEFAULT 0,
    status VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    product_name VARCHAR(255),
    quantity BIGINT DEFAULT 0,
    price DOUBLE PRECISION DEFAULT 0,
    subtotal DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 模式 2: 客户 → 订单 → 订单项（三层关联）

**创建顺序**：customers → orders → order_items

```
# Step 1: customers
collections { action: "create", name: "customers", title: "客户", fields: [
  { name: "name", interface: "input", uiSchema: { title: "客户名称" } },
  { name: "phone", interface: "phone", uiSchema: { title: "联系电话" } },
  { name: "email", interface: "email", uiSchema: { title: "邮箱" } }
]}

# Step 2: orders + 关联到 customers
# 先创建 orders 普通字段
collections { action: "create", name: "orders", title: "订单", fields: [
  { name: "order_no", interface: "input", uiSchema: { title: "订单号" } },
  { name: "total_amount", interface: "number", uiSchema: { title: "总金额" } }
]}
# 再添加 m2o 关联
fields { action: "create", collection: "orders", field: {
  name: "customer", interface: "m2o", type: "belongsTo",
  target: "customers", foreignKey: "customer_id",
  uiSchema: { title: "客户" },
  reverseField: { name: "orders", interface: "o2m", type: "hasMany", uiSchema: { title: "订单" } }
}}

# Step 3: order_items + 关联到 orders
collections { action: "create", name: "order_items", title: "订单明细", fields: [...] }
fields { action: "create", collection: "order_items", field: {
  name: "order", interface: "m2o", type: "belongsTo",
  target: "orders", foreignKey: "order_id",
  uiSchema: { title: "订单" },
  reverseField: { name: "items", interface: "o2m", type: "hasMany", uiSchema: { title: "明细" } }
}}
```

## 模式 3: 多对多（商品 ↔ 标签）

**表结构**：
- `products` — 商品
- `tags` — 标签
- `products_tags` — 中间表（NocoBase 自动创建）

**创建顺序**：products → tags → 关联

```
# Step 1: products
collections { action: "create", name: "products", title: "商品", fields: [
  { name: "name", interface: "input", uiSchema: { title: "商品名称" } },
  { name: "price", interface: "number", uiSchema: { title: "价格" } }
]}

# Step 2: tags
collections { action: "create", name: "tags", title: "标签", fields: [
  { name: "name", interface: "input", uiSchema: { title: "标签名" } },
  { name: "color", interface: "colorPicker", uiSchema: { title: "颜色" } }
]}

# Step 3: m2m 关联
fields { action: "create", collection: "products", field: {
  name: "tags",
  interface: "m2m",
  type: "belongsToMany",
  target: "tags",
  through: "products_tags",
  sourceKey: "id",
  foreignKey: "product_id",
  otherKey: "tag_id",
  targetKey: "id",
  uiSchema: { title: "标签" },
  reverseField: {
    name: "products",
    interface: "m2m",
    type: "belongsToMany",
    uiSchema: { title: "商品" }
  }
}}
```

**对应 SQL**：
```sql
CREATE TABLE products_tags (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id),
    tag_id BIGINT NOT NULL REFERENCES tags(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 模式 4: 树形结构（分类 → 子分类）

使用 NocoBase 的 `tree` 模板。

```
collections { action: "create", name: "categories", title: "分类",
  template: "tree",
  fields: [
    { name: "name", interface: "input", uiSchema: { title: "分类名称" } },
    { name: "icon", interface: "icon", uiSchema: { title: "图标" } },
    { name: "sort", interface: "sort", uiSchema: { title: "排序" } }
  ]
}
```

> `tree` 模板自动创建 `parentId`、`parent`、`children` 字段，不需要手动添加。

**对应 SQL**：
```sql
CREATE TABLE categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255),
    parent_id BIGINT REFERENCES categories(id),
    sort INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 模式 5: 文件附件（合同 + 附件）

使用 `attachment` interface。

```
collections { action: "create", name: "contracts", title: "合同", fields: [
  { name: "title", interface: "input", uiSchema: { title: "合同名称" } },
  { name: "contract_no", interface: "input", uiSchema: { title: "合同编号" } },
  { name: "sign_date", interface: "datePicker", uiSchema: { title: "签订日期" } },
  { name: "attachments", interface: "attachment", uiSchema: { title: "附件" } }
]}
```

## 模式 6: 继承表（人员 → 学生/教师）

```
# 基表
collections { action: "create", name: "people", title: "人员", fields: [
  { name: "name", interface: "input", uiSchema: { title: "姓名" } },
  { name: "email", interface: "email", uiSchema: { title: "邮箱" } },
  { name: "phone", interface: "phone", uiSchema: { title: "电话" } }
]}

# 继承表
collections { action: "create", name: "students", title: "学生",
  template: "inherit", inherits: "people",
  fields: [
    { name: "student_no", interface: "input", uiSchema: { title: "学号" } },
    { name: "grade", interface: "input", uiSchema: { title: "年级" } }
  ]
}
```

## 批量创建 UI 模板

完成所有建表后，依次创建管理 UI：

```
table_ui { action: "create", collection_name: "customers", group_title: "客户管理" }
table_ui { action: "create", collection_name: "orders", group_title: "订单管理" }
table_ui { action: "create", collection_name: "order_items", group_title: "订单管理" }
table_ui { action: "create", collection_name: "products", group_title: "商品管理" }
```
