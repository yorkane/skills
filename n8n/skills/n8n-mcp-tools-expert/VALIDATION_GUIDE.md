# 配置校验工具指南

校验节点配置与 workflow 的完整指南。

---

## 校验哲学

**尽早校验,频繁校验**

校验通常是迭代的,有 validate → fix 的循环

---

## validate_node(统一校验)

`validate_node` 工具通过不同 mode 提供全部校验能力。

### 快速检查(mode="minimal")

**速度**: <50ms

**适用**: 查看哪些字段必填

```javascript
validate_node({
  nodeType: "nodes-base.slack",
  config: {},  // 传空对象查看所有必填字段
  mode: "minimal"
})
```

**返回**:

```javascript
{
  "valid": true,           // 通常为 true(多数节点无严格必填)
  "missingRequiredFields": []
}
```

**使用时机**: 规划配置,看基础要求

### 完整校验(mode="full",默认)

**速度**: <100ms

**适用**: 部署前校验实际配置

```javascript
validate_node({
  nodeType: "nodes-base.slack",
  config: {
    resource: "channel",
    operation: "create",
    channel: "general"
  },
  profile: "runtime"  // 推荐!
})
// mode="full" 是默认值
```

---

## 校验 Profile

根据阶段选择:

**minimal** —— 仅必填字段
- 最快
- 最宽松
- 适用: 编辑中的快速检查

**runtime** —— 值 + 类型(**推荐**)
- 平衡校验
- 捕获真实错误
- 适用: 部署前校验

**ai-friendly** —— 减少误报
- 适合 AI 生成的配置
- 容忍小问题
- 适用: AI 配置节点时

**strict** —— 最大校验强度
- 规则最严
- 可能有误报
- 适用: 生产部署

---

## 校验响应

```javascript
{
  "nodeType": "nodes-base.slack",
  "workflowNodeType": "n8n-nodes-base.slack",
  "displayName": "Slack",
  "valid": false,
  "errors": [
    {
      "type": "missing_required",
      "property": "name",
      "message": "Channel name is required",
      "fix": "Provide a channel name (lowercase, no spaces, 1-80 characters)"
    }
  ],
  "warnings": [
    {
      "type": "best_practice",
      "property": "errorHandling",
      "message": "Slack API can have rate limits",
      "suggestion": "Add onError: 'continueRegularOutput' with retryOnFail"
    }
  ],
  "suggestions": [],
  "summary": {
    "hasErrors": true,
    "errorCount": 1,
    "warningCount": 1,
    "suggestionCount": 0
  }
}
```

### 错误类型

- `missing_required` - 必须修复
- `invalid_value` - 必须修复
- `type_mismatch` - 必须修复
- `best_practice` - 建议修复(警告)
- `suggestion` - 可选改进

---

## validate_workflow(结构校验)

**速度**: 100-500ms

**适用**: 执行前检查完整 workflow

**语法**:

```javascript
validate_workflow({
  workflow: {
    nodes: [...],        // 节点数组
    connections: {...}   // 连接对象
  },
  options: {
    validateNodes: true,       // 默认: true
    validateConnections: true, // 默认: true
    validateExpressions: true, // 默认: true
    profile: "runtime"         // 用于节点校验
  }
})
```

**校验内容**:

- 节点配置
- 连接有效性(无断引用)
- 表达式语法(`{{ }}` 模式)
- workflow 结构(触发器、流程)
- AI 连接(8 种类型)

**返回**: 含 errors、warnings、suggestions 的综合校验报告

### 按 Workflow ID 校验

```javascript
// 校验 n8n 中已存在的 workflow
n8n_validate_workflow({
  id: "workflow-id",
  options: {
    validateNodes: true,
    validateConnections: true,
    validateExpressions: true,
    profile: "runtime"
  }
})
```

---

## 校验循环模式

**典型周期**: 思考 23s,修复 58s

```
1. 配置节点
   ↓
2. validate_node(思考错误 23s)
   ↓
3. 修复错误
   ↓
4. 再次 validate_node(修复 58s)
   ↓
5. 重复直到通过
```

**示例**:

```javascript
// 第 1 轮
let config = {
  resource: "channel",
  operation: "create"
};

const result1 = validate_node({
  nodeType: "nodes-base.slack",
  config,
  profile: "runtime"
});
// → 错误: 缺少 "name"

// 第 2 轮(约 58s 后)
config.name = "general";

const result2 = validate_node({
  nodeType: "nodes-base.slack",
  config,
  profile: "runtime"
});
// → 通过!
```

---

## 自动清洗系统

**运行时机**: 在任何 workflow 更新时(create 或 update_partial)

**自动修复内容**(在所有节点上):

1. 二元运算符(equals、contains、greaterThan)→ 移除 `singleValue`
2. 一元运算符(isEmpty、isNotEmpty、true、false)→ 添加 `singleValue: true`
3. 无效的 operator 结构 → 纠正为正确格式
4. IF v2.2+ 节点 → 添加完整的 `conditions.options` 元数据
5. Switch v3.2+ 节点 → 为所有规则添加完整的 `conditions.options`

**无法修复的内容**:

- 断开的连接(引用了不存在的节点)
- 分支数不匹配(3 个 Switch 规则但只有 2 个输出)
- 矛盾的损坏状态(API 返回损坏,拒绝更新)

**示例**:

```javascript
// 自动清洗前
{
  "type": "boolean",
  "operation": "equals",
  "singleValue": true  // 二元运算符不应有
}

// 自动清洗后(自动!)
{
  "type": "boolean",
  "operation": "equals"
  // singleValue 已自动移除
}
```

**恢复工具**:

- `cleanStaleConnections` 操作 —— 移除断开的连接
- `n8n_autofix_workflow({id})` —— 预览/应用修复

---

## n8n_autofix_workflow(自动修复工具)

**适用**: 校验错误需要自动修复

```javascript
// 预览修复(默认 - 不应用)
n8n_autofix_workflow({
  id: "workflow-id",
  applyFixes: false,  // 预览模式
  confidenceThreshold: "medium"  // high、medium、low
})

// 应用修复
n8n_autofix_workflow({
  id: "workflow-id",
  applyFixes: true
})
```

**修复类型**:

- `expression-format` - 修复表达式遗漏的 `=` 前缀
- `typeversion-correction` - 降级不支持的 typeVersions
- `error-output-config` - 移除冲突的 onError 设置
- `node-type-correction` - 通过相似度匹配修复未知节点类型(90%+ 置信度)
- `webhook-missing-path` - 为缺 path 的 webhook 节点生成 UUID
- `typeversion-upgrade` - 智能升级到最新版节点,自动迁移
- `version-migration` - 复杂破坏性变更的迁移指导(手动步骤)

**置信度阈值**: `high`(90%+)、`medium`(70-89%,默认)、`low`(任意)

**更新后指引**: 查看响应中的 `postUpdateGuidance` 字段,获取版本升级的迁移步骤。

---

## 二元 vs 一元运算符

**二元运算符**(比较两个值):
- equals、notEquals、contains、notContains
- greaterThan、lessThan、startsWith、endsWith
- **不能有** `singleValue: true`

**一元运算符**(检查单个值):
- isEmpty、isNotEmpty、true、false
- **必须有** `singleValue: true`

**自动清洗会自动修复这些!**

---

## 处理校验错误

### 流程

```
1. 仔细阅读错误信息
2. 判断是否为已知误报
3. 修复真实错误
4. 再次校验
5. 迭代直到通过
```

### 常见错误

**"Required field missing"**
→ 添加字段并填入合适值

**"Invalid value"**
→ 在 get_node 输出中检查允许值

**"Type mismatch"**
→ 转换为正确类型(字符串/数字/布尔)

**"Cannot have singleValue"**
→ 下次更新时自动清洗会修复

**"Missing operator metadata"**
→ 下次更新时自动清洗会修复

### 误报

部分校验警告可以接受:
- 可选最佳实践
- 节点特定边界情况
- 依赖于 profile 的问题

用 **ai-friendly** profile 减少误报。

---

## 最佳实践

### 应该

- 部署前用 **runtime** profile
- 每次配置变更后校验
- 立即修复错误(平均 58s)
- 迭代校验循环
- 信任自动清洗处理 operator 问题
- 用 `mode: "minimal"` 做快速检查
- 用 `n8n_autofix_workflow` 做批量修复
- 就绪后通过 API 激活 workflow(`activateWorkflow` operation)

### 不应

- 部署前跳过校验
- 忽视错误信息
- 开发期间用 strict profile(警告太多)
- 假设校验通过(检查结果)
- 试图手动修复自动清洗问题

---

## 示例:完整校验工作流

```javascript
// Step 1: 获取节点要求(快速检查)
validate_node({
  nodeType: "nodes-base.slack",
  config: {},
  mode: "minimal"
});
// → 知道必填项

// Step 2: 配置节点
const config = {
  resource: "message",
  operation: "post",
  channel: "#general",
  text: "Hello!"
};

// Step 3: 校验配置(完整校验)
const result = validate_node({
  nodeType: "nodes-base.slack",
  config,
  profile: "runtime"
});

// Step 4: 检查结果
if (result.valid) {
  console.log("配置有效!");
} else {
  console.log("错误:", result.errors);
  // 修复并再次校验
}

// Step 5: 在 workflow 上下文中校验
validate_workflow({
  workflow: {
    nodes: [{...config as node...}],
    connections: {...}
  }
});

// Step 6: 如需要,应用自动修复
n8n_autofix_workflow({
  id: "workflow-id",
  applyFixes: true
});
```

---

## 小结

**要点**:

1. 使用 **runtime** profile(平衡校验)
2. 校验循环: validate → fix(58s) → 再次 validate
3. 自动清洗自动修复 operator 结构
4. 二元运算符 ≠ singleValue,一元运算符 = singleValue: true
5. 迭代到校验通过
6. 用 `n8n_autofix_workflow` 做自动修复

**工具选择**:

- **validate_node({mode: "minimal"})**: 快速必填字段检查
- **validate_node({profile: "runtime"})**: 完整配置校验(**用这个!**)
- **validate_workflow**: 完整 workflow 检查
- **n8n_validate_workflow({id})**: 校验已存在的 workflow
- **n8n_autofix_workflow({id})**: 自动修复常见问题

**相关**:
- [SEARCH_GUIDE.md](SEARCH_GUIDE.md) - 查找节点
- [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) - 构建 workflow
