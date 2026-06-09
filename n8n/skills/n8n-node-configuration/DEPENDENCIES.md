# 属性依赖与 displayOptions 深入

n8n 节点配置中属性依赖如何工作的完整指南。

---

## 什么是 displayOptions?

**定义**: 控制节点字段**可见性**的机制,基于其他字段的值

**目的**: 让 UI 按需显示字段,避免让用户面对海量无关选项

**位置**: 节点 schema 中,作为 `displayOptions` 键

---

## 基本格式

```javascript
{
  "name": "body",
  "type": "json",
  "displayOptions": {
    "show": {
      "sendBody": [true],
      "method": ["POST", "PUT", "PATCH"]
    }
  }
}
```

**结构说明**:

- `displayOptions.show` - 字段**显示**的条件
- 键是其他字段名
- 值是允许值的数组
- 多个键之间是 **AND** 关系
- 数组中的值是 **OR** 关系

---

## Show vs Hide

### Show(白名单)

字段在条件满足时**显示**:

```javascript
{
  "name": "channelName",
  "displayOptions": {
    "show": {
      "resource": ["channel"]
    }
  }
}
```

### Hide(黑名单)

字段在条件满足时**隐藏**:

```javascript
{
  "name": "channelName",
  "displayOptions": {
    "hide": {
      "operation": ["delete"]  // operation=delete 时隐藏
    }
  }
}
```

**注意**: `show` 和 `hide` 可以组合使用,任一条件为真即可

---

## 多重条件(AND 逻辑)

多个键在 `displayOptions.show` 内表示 **AND**:

```javascript
{
  "name": "body",
  "displayOptions": {
    "show": {
      "sendBody": [true],           // 条件 1
      "method": ["POST", "PUT"]     // 条件 2
    }
  }
}
```

**翻译**: 字段在 `sendBody=true` **且** `method` 为 POST/PUT 时显示

---

## 多值(OR 逻辑)

值数组内的多个值是 **OR** 关系:

```javascript
{
  "name": "body",
  "displayOptions": {
    "show": {
      "method": ["POST", "PUT", "PATCH", "DELETE"]
    }
  }
}
```

**翻译**: 字段在 `method` 是 POST/PUT/PATCH/DELETE 之一时显示

---

## 常见依赖模式

### 模式 1:布尔开关

**示例**: HTTP Request `sendBody`

```javascript
// sendBody=true 时显示 body
{
  "sendBody": true
  // body 字段出现
}
```

**Schema 结构**:

```javascript
{
  "name": "body",
  "displayOptions": {
    "show": {
      "sendBody": [true]
    }
  }
}
```

### 模式 2:Resource/Operation 级联

**示例**: Slack 节点的 `resource` 和 `operation`

```javascript
// 选 resource 后,operation 列表会变化
{
  "resource": "message"
  // operation 选项: post, update, delete
}

{
  "resource": "channel"
  // operation 选项: create, archive, invite
}
```

**Schema 结构**:

```javascript
{
  "name": "operation",
  "displayOptions": {
    "show": {
      "resource": ["message"]
    }
  }
}
```

### 模式 3:类型特定配置

**示例**: IF 节点 conditions

```javascript
// 选 type=string 后,显示字符串操作符
{
  "type": "string"
  // 显示: equals, contains, startsWith ...
}

// 选 type=boolean 后,显示布尔操作符
{
  "type": "boolean"
  // 显示: equals, isTrue, isFalse
}
```

### 模式 4:Method 特定字段

**示例**: HTTP Request 节点的 method

```javascript
// POST 时显示 sendBody
{
  "method": "POST"
}

// GET 时不显示 sendBody
{
  "method": "GET"
}
```

---

## 查找属性依赖

### 用 get_node + search_properties mode

查找与特定查询匹配的属性:

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  mode: "search_properties",
  propertyQuery: "body"
})
// 返回: body 的显示选项
```

### 用 get_node + full detail

获取完整 schema(含所有 displayOptions 规则):

```javascript
get_node({
  nodeType: "nodes-base.httpRequest",
  detail: "full"
})
// 返回: 完整 schema,含 displayOptions
```

---

## 何时使用

**用 displayOptions 知识**:

- 理解为何字段缺失
- 预测配置变更对 UI 的影响
- 编写可工作的配置(不被显示规则阻挡)
- 调试"我看不到某字段"问题

**实际场景**:

1. **配置 HTTP Request POST**: 知道需要 `sendBody: true` 才能看到 `body`
2. **配置 IF 节点**: 知道选 `type: string` 后才能选字符串操作符
3. **配置 Slack 节点**: 知道选 `resource: message` 后 operation 列表会变

---

## 完整示例

### 示例 1:HTTP Request 完整流程

```javascript
// Step 1: 选 method
{
  "method": "POST"  // ← 触发 sendBody 显示
}

// Step 2: 现在 sendBody 出现
{
  "method": "POST",
  "sendBody": true  // ← 触发 body 显示
}

// Step 3: 现在 body 出现
{
  "method": "POST",
  "sendBody": true,
  "body": {         // ← 现在可见
    "contentType": "json"
  }
}
```

### 示例 2:IF 节点 Operator 依赖

```javascript
// Step 1: 选 type
{
  "type": "string"  // ← 触发字符串操作符显示
}

// Step 2: 选 operation
{
  "type": "string",
  "operation": "equals"  // ← 现在显示
}

// Step 3: 显示 value1 和 value2(二元操作符)
{
  "type": "string",
  "operation": "equals",
  "value1": "...",
  "value2": "..."
}
```

### 示例 3:Slack Operation 矩阵

```javascript
// 选 resource=message 后:
// - operation: [post, update, delete]
// - channel: 必填(对 post)
// - text: 必填(对 post)
// - messageId: 必填(对 update)

// 选 resource=channel 后:
// - operation: [create, archive, invite]
// - name: 必填(对 create)
// - isPrivate: 可选
```

---

## 失效的 displayOptions

### 什么是失效的 displayOptions?

**定义**: displayOptions 引用了**已不存在或已重命名**的字段

**原因**:

- 节点版本升级
- 重构节点 schema
- 复制旧配置

**现象**:

- 字段在 UI 中不可见但配置中仍存在
- 配置无法清理
- 升级后字段"消失"

### 如何处理

```javascript
// 步骤 1: 识别问题
validate_node({nodeType: "nodes-base.slack", config});
// → 警告: "Field 'old_field' is configured but not visible"

// 步骤 2: 移除失效字段
{
  type: "updateNode",
  nodeName: "Slack",
  updates: {
    oldField: null  // 移除失效字段
  }
}

// 步骤 3: 校验
validate_node({nodeType: "nodes-base.slack", config});
// → 通过
```

---

## 自动清洗与 displayOptions

### 自动清洗修复什么

1. **缺失的 IF/Switch 元数据**: 自动添加 `conditions.options`
2. **错误的 operator 结构**: 修正 singleValue
3. **过时的字段引用**: 某些情况下自动清理

### 不修复的内容

1. **完全失效的引用**: 需手动用 `null` 删除
2. **冲突的依赖**: 需手动介入
3. **自定义 displayOptions**: 自定义节点不受自动清洗

---

## 常见问题

### 问题 1:"字段 X 必填但不可见"

**症状**: 校验报字段必填,但 UI 中找不到

**原因**: displayOptions 阻止了字段显示

**修复**:

1. 检查使字段可见的条件
2. 设置其他字段的值
3. 字段出现后再填

**示例**:

```
错误: "body is required"
原因: sendBody=false 时 body 不可见
修复: 设为 sendBody=true
```

### 问题 2:"改变 operation 后字段消失"

**症状**: 切换 operation 后之前填的字段没了

**原因**: displayOptions 与新 operation 不匹配

**修复**:

1. 检查新 operation 的必填项
2. 重新填字段
3. 用 get_node 看新 operation 的要求

### 问题 3:"校验通过但字段不保存"

**症状**: 字段在配置中存在但 UI 不显示

**原因**: displayOptions 阻止显示

**修复**: 移除或用合适的值触发显示

---

## 模式

### 模式 1:条件必填带回退

```javascript
// 当 body 必填但可能不需要时
{
  "sendBody": true,
  "body": {
    "contentType": "json",
    "content": {}  // 空对象 - 优雅失败
  }
}
```

### 模式 2:互斥字段

```javascript
// 二选一
{
  "useCredential": true,
  "credentialType": "slackApi"
  // 不要同时设置 useApiKey: true
}
```

### 模式 3:渐进复杂度

```javascript
// 从最小化开始
{
  "method": "GET"
}
// 逐步添加
{
  "method": "GET",
  "sendQuery": true
}
{
  "method": "GET",
  "sendQuery": true,
  "queryParameters": {...}
}
```

---

## 最佳实践

### ✅ 应该

- 理解字段依赖
- 用 get_node + search_properties 探索
- 用 get_node + full detail 调试
- 校验时让 displayOptions 引导
- 切 operation 时看新要求
- 让自动清洗处理 operator 结构

### ❌ 不要

- 不理解就硬填字段
- 忽视字段消失的迹象
- 在不检查 displayOptions 的情况下配置
- 手动修复自动清洗能处理的问题
- 假设所有字段总是可见

---

## 小结

**核心概念**:

- `displayOptions.show` 控制字段何时显示
- 多个键是 AND,值数组是 OR
- `displayOptions.hide` 控制何时隐藏
- 用 get_node 探索依赖

**实用技巧**:

- 从最小配置开始
- 每次变更后校验
- 让 schema 引导 UI 流程
- 切 operation 时重新检查

**调试步骤**:

1. 检查 displayOptions
2. 用 search_properties 找属性
3. 校验找失效引用
4. 修复配置或 schema
