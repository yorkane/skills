# n8n 表达式常见错误

含说明与修复方案的表达式错误完整目录。

---

## 1. 漏写花括号

**问题**: 表达式未被识别,显示为纯文本

❌ **错误**:

```
$json.email
```

✅ **正确**:

```
{{$json.email}}
```

**原因**: n8n 把没有 {{ }} 的文本当作字面量字符串。必须用花括号包裹表达式才会被求值。

**如何识别**: 字段显示 "$json.email" 原文本而非实际值。

---

## 2. Webhook Body 访问

**问题**: 访问 webhook 数据时返回 undefined

❌ **错误**:

```
{{$json.name}}
{{$json.email}}
{{$json.message}}
```

✅ **正确**:

```
{{$json.body.name}}
{{$json.body.email}}
{{$json.body.message}}
```

**原因**: Webhook 节点把传入数据放在 `.body` 属性下。根 `$json` 含 headers、params、query、body。

**Webhook 结构**:

```javascript
{
  "headers": {...},
  "params": {...},
  "query": {...},
  "body": {         // 用户数据在这里!
    "name": "John",
    "email": "john@example.com"
  }
}
```

**如何识别**: Webhook workflow 对确实在传输的字段显示 "undefined"。

---

## 3. 字段名含空格

**问题**: 语法错误或 undefined

❌ **错误**:

```
{{$json.first name}}
{{$json.user data.email}}
```

✅ **正确**:

```
{{$json['first name']}}
{{$json['user data'].email}}
```

**原因**: 空格会破坏点号语法。JavaScript 会把空格解释为属性名的结束。

**如何识别**: 错误提示 unexpected token,或字段存在却返回 undefined。

---

## 4. 节点名含空格

**问题**: 无法访问其他节点的数据

❌ **错误**:

```
{{$node.HTTP Request.json.data}}
{{$node.Respond to Webhook.json}}
```

✅ **正确**:

```
{{$node["HTTP Request"].json.data}}
{{$node["Respond to Webhook"].json}}
```

**原因**: 节点名被视为对象属性名,含空格时需要引号。

**如何识别**: 报错 "Cannot read property 'Request' of undefined"

---

## 5. 节点引用大小写错误

**问题**: 返回 undefined 或错误数据

❌ **错误**:

```
{{$node["http request"].json.data}}  // 全小写
{{$node["Http Request"].json.data}}  // 大小写错误
```

✅ **正确**:

```
{{$node["HTTP Request"].json.data}}  // 精确匹配
```

**原因**: 节点名**区分大小写**。必须与 workflow 中显示的完全一致。

**如何识别**: 即便节点存在且有数据,仍返回 undefined。

---

## 6. 双重包裹

**问题**: 输出中出现字面量 {{ }}

❌ **错误**:

```
{{{$json.field}}}
```

✅ **正确**:

```
{{$json.field}}
```

**原因**: 只需要一层 {{ }}。多余的花括号被当作字面字符。

**如何识别**: 输出显示 "{{value}}" 而非 "value"。

---

## 7. 数组访问用了点号

**问题**: 语法错误或 undefined

❌ **错误**:

```
{{$json.items.0.name}}
{{$json.users.1.email}}
```

✅ **正确**:

```
{{$json.items[0].name}}
{{$json.users[1].email}}
```

**原因**: 数组下标需要用中括号,不是点号。点号后的数字在 JavaScript 中无效。

**如何识别**: 语法错误或 "Cannot read property '0' of undefined"

---

## 8. 在 Code 节点中使用表达式

**问题**: 字面量字符串代替值,或报错

❌ **错误**(在 Code 节点中):

```javascript
const email = '{{$json.email}}';
const name = '={{$json.body.name}}';
```

✅ **正确**(在 Code 节点中):

```javascript
const email = $json.email;
const name = $json.body.name;

// 或用 Code 节点 API
const email = $input.item.json.email;
const allItems = $input.all();
```

**原因**: Code 节点**直接访问**数据。`{{ }}` 语法用于其他节点的表达式字段,不是 JavaScript 代码。

**如何识别**: Code 节点输出中出现字面字符串 "{{$json.email}}" 而非实际值。

---

## 9. `$node` 引用中漏引号

**问题**: 语法错误

❌ **错误**:

```
{{$node[HTTP Request].json.data}}
```

✅ **正确**:

```
{{$node["HTTP Request"].json.data}}
```

**原因**: 节点名在中括号内必须是带引号的字符串。

**如何识别**: 语法错误 "Unexpected identifier"

---

## 10. 属性路径错误

**问题**: undefined

❌ **错误**:

```
{{$json.data.items.name}}       // items 是数组
{{$json.user.email}}            // user 不存在,实际是 userData
```

✅ **正确**:

```
{{$json.data.items[0].name}}    // 访问数组元素
{{$json.userData.email}}        // 正确的属性名
```

**原因**: 数据路径错误。数组需要下标,属性名必须精确。

**如何识别**: 用表达式编辑器预览检查真实数据结构。

---

## 11. 在 JSON 之外用 `=` 前缀

**问题**: 输出中出现字面量 "="

❌ **错误**(在文本字段中):

```
Email: ={{$json.email}}
```

✅ **正确**(在文本字段中):

```
Email: {{$json.email}}
```

**注意**: `=` 前缀**仅**在 JSON 模式下需要,或当你希望把整个字段值设为表达式结果时:

```javascript
// JSON 模式(把属性设为表达式)
{
  "email": "={{$json.body.email}}"
}

// 文本模式(不需要 =)
Hello {{$json.body.name}}!
```

**原因**: 在非 JSON 上下文中,`=` 被解析为字面文本。

**如何识别**: 输出显示 "=john@example.com" 而非 "john@example.com"

---

## 12. 在 Webhook 路径中使用表达式

**问题**: 路径不更新,校验错误

❌ **错误**:

```
path: "{{$json.user_id}}/webhook"
path: "users/={{$env.TENANT_ID}}"
```

✅ **正确**:

```
path: "my-webhook"              // 只能使用静态路径
path: "user-webhook/:userId"    // 用动态 URL 参数代替
```

**原因**: Webhook 路径必须为静态。用动态 URL 参数(`:paramName`)代替表达式。

**如何识别**: Webhook 路径不变化,或校验警告路径无效。

---

## 13. 忘记 `$node` 引用中的 `.json`

**问题**: undefined 或错误数据

❌ **错误**:

```
{{$node["HTTP Request"].data}}          // 缺 .json
{{$node["Webhook"].body.email}}         // 缺 .json
```

✅ **正确**:

```
{{$node["HTTP Request"].json.data}}
{{$node["Webhook"].json.body.email}}
```

**原因**: 节点数据始终在 `.json` 属性下(或 `.binary` 对应二进制数据)。

**如何识别**: 节点确实有数据,却返回 undefined。

---

## 14. 字符串拼接混淆

**问题**: 试图用 JavaScript 模板字面量

❌ **错误**:

```
`Hello ${$json.name}!`          // 模板字面量语法
"Hello " + $json.name + "!"     // 字符串拼接
```

✅ **正确**:

```
Hello {{$json.name}}!           // n8n 表达式自动拼接
```

**原因**: n8n 表达式不用 JavaScript 模板字面量语法。相邻的文本和表达式会自动拼接。

**如何识别**: 输出中出现字面反引号或 + 符号。

---

## 15. 表达式括号为空

**问题**: 输出中出现字面量 {{}}

❌ **错误**:

```
{{}}
{{ }}
```

✅ **正确**:

```
{{$json.field}}                 // 含表达式内容
```

**原因**: 空表达式括号没有可求值的内容。

**如何识别**: 输出中出现字面 "{{ }}" 文本。

---

## 速查表

| 错误 | 现象 | 修复 |
|-------|---------|-----|
| 无 {{ }} | 字面文本 | 加 {{ }} |
| Webhook 数据 | undefined | 加 `.body` |
| 字段含空格 | 语法错误 | 用 `['field name']` |
| 节点含空格 | undefined | 用 `["Node Name"]` |
| 大小写错误 | undefined | 精确匹配大小写 |
| 双重 {{ }} | 字面花括号 | 移除多余的 {{ }} |
| .0 数组 | 语法错误 | 用 [0] |
| Code 中用 {{ }} | 字面字符串 | 移除 {{ }} |
| `$node` 无引号 | 语法错误 | 加引号 |
| 路径错误 | undefined | 检查数据结构 |
| 文本中用 = | 字面 = | 去掉 = 前缀 |
| 动态路径 | 不生效 | 用静态路径 |
| 缺 .json | undefined | 加 .json |
| 模板字面量 | 字面文本 | 用 {{ }} |
| 空 {{ }} | 字面花括号 | 加表达式内容 |

---

## 调试流程

表达式不工作时:

1. **检查花括号**: 是否用 {{ }} 包裹?
2. **检查数据源**: 是 webhook 数据?加 `.body`
3. **检查空格**: 字段或节点名含空格?用中括号
4. **检查大小写**: 节点名精确匹配?
5. **检查路径**: 属性路径是否正确?
6. **用表达式编辑器**: 预览显示真实结果
7. **检查上下文**: 是 Code 节点?移除 {{ }}

---

**相关**: 正确语法的工作示例见 [EXAMPLES.md](EXAMPLES.md)
