# 内置函数 - JavaScript Code 节点

n8n Code 节点可用内置函数的完整参考。

---

## 概览

| 函数 | 类别 | 用途 |
|------|------|------|
| `$helpers.httpRequest()` | HTTP | 发 HTTP 请求(无认证) |
| `DateTime` (Luxon) | 日期 | 日期与时间操作 |
| `$jmespath()` | 数据 | JMESPath JSON 查询 |
| `$getWorkflowStaticData()` | 状态 | 跨执行持久化数据 |
| `console.log()` | 调试 | 输出到执行日志 |
| 标准 JS 全局 | JS | Math、JSON、String 等 |
| Node.js 模块 | 系统 | 部分允许 |

---

## 0.沙箱限制(关键)

**n8n Code 节点在安全沙箱中运行**,有重要限制:

### 不可用函数

```javascript
// ❌ 出于安全考虑被阻止
$helpers.httpRequestWithAuthentication  // 用 $helpers.httpRequest() + 手动认证代替
$credentials  // 在 Code 节点中不可用

// ❌ require 大多数模块
require('axios')   // 改用 $helpers.httpRequest()
require('lodash')  // 改用原生 JS

// ❌ 文件系统
require('fs')
```

### 可用模块(白名单)

```javascript
// ✅ 可用
require('crypto')    // 加密
require('zlib')      // 压缩
require('url')       // URL 解析
require('querystring') // 查询字符串
require('util')      // 工具函数
```

### 环境变量访问

```javascript
// ✅ 取决于 N8N_BLOCK_ENV_ACCESS_IN_NODE 设置
// 若 false(默认): $env 可用
const apiKey = $env.API_KEY;

// 若 true: 用替代方案(见错误模式文档)
```

---

## 1. `$helpers.httpRequest()` - HTTP 请求

**无认证的 HTTP 请求**

### 基础 GET

```javascript
const response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/data'
});

return [{ json: response }];
```

### GET 带 Headers

```javascript
const response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/data',
  headers: {
    'Authorization': 'Bearer ' + $env.API_KEY,
    'Accept': 'application/json',
    'X-Custom-Header': 'value'
  },
  returnKey: 'json'  // 返回 json 字段
});
```

### POST JSON

```javascript
const response = await $helpers.httpRequest({
  method: 'POST',
  url: 'https://api.example.com/create',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + $env.API_KEY
  },
  body: {
    name: $json.name,
    email: $json.email
  },
  json: true  // 自动 JSON 序列化
});

return [{ json: response }];
```

### POST 表单

```javascript
const response = await $helpers.httpRequest({
  method: 'POST',
  url: 'https://api.example.com/form',
  form: {
    field1: 'value1',
    field2: 'value2'
  }
});
```

### 带超时

```javascript
const response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/slow',
  timeout: 30000  // 30 秒
});
```

### 处理错误

```javascript
try {
  const response = await $helpers.httpRequest({
    method: 'GET',
    url: 'https://api.example.com/data'
  });
  return [{ json: { success: true, data: response } }];
} catch (error) {
  return [{
    json: {
      success: false,
      error: error.message,
      code: error.code || 'UNKNOWN'
    }
  }];
}
```

### 处理多个请求

```javascript
// 顺序请求
const userData = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/user/1'
});

const userPosts = await $helpers.httpRequest({
  method: 'GET',
  url: `https://api.example.com/user/${userData.id}/posts`
});

return [{
  json: {
    user: userData,
    posts: userPosts
  }
}];
```

---

## 2. `DateTime` (Luxon) - 日期时间操作

**Luxon 是 JavaScript 强大的日期库**

### 当前时间

```javascript
const now = DateTime.now();
const nowIso = now.toISO();
const nowMillis = now.toMillis();
```

### 从字符串解析

```javascript
const date = DateTime.fromISO('2025-10-20T14:30:00Z');
const fromFormat = DateTime.fromFormat('20-10-2025', 'dd-MM-yyyy');
const fromHttp = DateTime.fromHTTP('Wed, 21 Oct 2025 07:28:00 GMT');
const fromMillis = DateTime.fromMillis(1697831400000);
const fromSql = DateTime.fromSQL('2025-10-20');
```

### 格式化

```javascript
const now = DateTime.now();

now.toFormat('yyyy-MM-dd');              // '2025-10-20'
now.toFormat('HH:mm:ss');                // '14:30:45'
now.toFormat('yyyy-MM-dd HH:mm');        // '2025-10-20 14:30'
now.toFormat('MMMM dd, yyyy');           // 'October 20, 2025'
now.toISO();                             // '2025-10-20T14:30:45.000Z'
now.toISODate();                        // '2025-10-20'
now.toLocaleString();                    // 取决于 locale
now.toUTC().toISO();                    // UTC
```

### 日期运算

```javascript
const now = DateTime.now();

const tomorrow = now.plus({ days: 1 });
const nextWeek = now.plus({ weeks: 1 });
const nextMonth = now.plus({ months: 1 });
const inHours = now.plus({ hours: 5 });
const future = now.plus({ years: 2, months: 3, days: 7 });

const yesterday = now.minus({ days: 1 });
const lastWeek = now.minus({ weeks: 1 });
const past = now.minus({ hours: 24, minutes: 30 });
```

### 日期比较

```javascript
const date1 = DateTime.fromISO('2025-01-01');
const date2 = DateTime.fromISO('2025-12-31');

date1 < date2;                    // true
date1.diff(date2, 'days').days;   // -364
date2.diff(date1, 'months').months; // 11
date1.hasSame(date2, 'year');     // true
```

### 提取组件

```javascript
const date = DateTime.now();

date.year;         // 2025
date.month;        // 10
date.day;          // 20
date.hour;         // 14
date.minute;       // 30
date.second;       // 45
date.weekday;      // 1 (Monday)
date.weekNumber;   // 42
date.quarter;      // 4
```

### 时区

```javascript
const now = DateTime.now();

now.setZone('America/New_York');
now.setZone('Europe/London');
now.setZone('Asia/Tokyo');
now.setZone('UTC');
now.setZone('local');  // 系统本地

// 跨时区格式化
const tokyoTime = now.setZone('Asia/Tokyo').toFormat('HH:mm');
```

### 日期差

```javascript
const start = DateTime.fromISO('2025-01-01');
const end = DateTime.fromISO('2025-12-31');

const diff = end.diff(start, ['days', 'months', 'years']);
// diff.days, diff.months, diff.years

const days = end.diff(start, 'days').days;       // 364
const hours = end.diff(start, 'hours').hours;   // 8736
```

### 实用函数

```javascript
// 本月第一天
const firstOfMonth = DateTime.now().startOf('month');
// 本月最后一天
const lastOfMonth = DateTime.now().endOf('month');

// 本周第一天(周一)
const startOfWeek = DateTime.now().startOf('week');

// 今天午夜
const midnight = DateTime.now().startOf('day');

// 时间戳
const timestamp = DateTime.now().toMillis();      // 1697831400000
const unix = Math.floor(DateTime.now().toSeconds()); // 1697831400
```

---

## 3. `$jmespath()` - JSON 查询

**JMESPath 是 JSON 的查询语言**

### 基础查询

```javascript
const data = $input.first().json;

// 简单字段访问
const name = $jmespath(data, 'name');
const email = $jmespath(data, 'user.email');
```

### 数组操作

```javascript
const data = $input.first().json;

// 过滤数组
const adults = $jmespath(data, 'users[?age >= `18`]');

// 提取字段
const names = $jmespath(data, 'users[*].name');
const emails = $jmespath(data, 'users[*].email');

// 第一个/最后一个
const firstUser = $jmespath(data, 'users[0]');
const lastUser = $jmespath(data, 'users[-1]');

// 长度
const count = $jmespath(data, 'length(users)');
```

### 复杂查询

```javascript
const data = $input.first().json;

// 排序
const sorted = $jmespath(data, 'sort_by(items, &price)');

// 选择特定字段
const projected = $jmespath(data, 'users[*].{name: name, email: email}');

// 嵌套过滤
const activeAdults = $jmespath(data, 'users[?age >= `18` && status == `active`]');

// 求和
const total = $jmespath(data, 'sum(items[*].price)');
const avg = $jmespath(data, 'avg(items[*].price)');
const max = $jmespath(data, 'max(items[*].price)');
```

### 实战示例

```javascript
// 从 webhook 数据提取关键字段
const webhookData = $input.first().json.body;

const result = {
  userEmail: $jmespath(webhookData, 'user.email'),
  orderTotal: $jmespath(webhookData, 'cart.total'),
  itemCount: $jmespath(webhookData, 'length(items)'),
  topItem: $jmespath(webhookData, 'max(items[*].price)')
};

return [{ json: result }];
```

---

## 4. `$getWorkflowStaticData()` - 持久化存储

**跨工作流执行的持久存储**

### 基础用法

```javascript
const staticData = $getWorkflowStaticData('global');

// 读取
const counter = staticData.counter || 0;

// 写入
staticData.counter = counter + 1;

return [{
  json: {
    counter: staticData.counter
  }
}];
```

### 跨迭代数据累积(SplitInBatches)

```javascript
// 在循环外(开始前):重置累加器
const staticData = $getWorkflowStaticData('global');
staticData.accumulated = [];
return $input.all();

// 在循环内:累积
const staticData = $getWorkflowStaticData('global');
const current = $input.first().json;

staticData.accumulated.push({
  id: current.id,
  processedAt: new Date().toISOString()
});

return [{ json: current }];

// 在循环外(结束后):读取累积数据
const staticData = $getWorkflowStaticData('global');
const allAccumulated = staticData.accumulated || [];
const finalResult = processAll(allAccumulated);
```

### 节点级 vs 全局级

```javascript
// 全局(整个 workflow 共享)
const globalData = $getWorkflowStaticData('global');

// 节点级(仅该节点)
const nodeData = $getWorkflowStaticData('node');
```

### 存储任意数据

```javascript
const data = $getWorkflowStaticData('global');

data.lastSync = new Date().toISOString();
data.apiCache = { value: 'cached', expires: Date.now() + 3600000 };
data.processedIds = [1, 2, 3, 4, 5];

return [{ json: { synced: true } }];
```

---

## 5. 标准 JavaScript 全局

### `Math`

```javascript
Math.max(1, 2, 3);        // 3
Math.min(1, 2, 3);        // 1
Math.round(3.14);         // 3
Math.floor(3.99);         // 3
Math.ceil(3.01);          // 4
Math.abs(-5);             // 5
Math.random();            // 0-1
Math.pow(2, 8);           // 256
Math.sqrt(16);            // 4
```

### `JSON`

```javascript
// 序列化
const str = JSON.stringify({ name: 'John', age: 30 });

// 解析
const obj = JSON.parse('{"name":"John"}');

// 美化输出
const pretty = JSON.stringify(data, null, 2);
```

### `String` 方法

```javascript
const str = 'Hello World';

str.toLowerCase();        // 'hello world'
str.toUpperCase();        // 'HELLO WORLD'
str.trim();               // 去除首尾空白
str.replace('World', 'JS'); // 'Hello JS'
str.split(' ');           // ['Hello', 'World']
str.includes('Hello');    // true
str.startsWith('Hello');  // true
str.endsWith('World');    // true
str.substring(0, 5);      // 'Hello'
str.length;               // 11
str.indexOf('o');         // 4
str.slice(0, 5);          // 'Hello'
str.repeat(3);            // 'Hello WorldHello WorldHello World'
```

### `Array` 方法

```javascript
const arr = [1, 2, 3, 4, 5];

arr.map(x => x * 2);        // [2, 4, 6, 8, 10]
arr.filter(x => x > 2);     // [3, 4, 5]
arr.reduce((sum, x) => sum + x, 0); // 15
arr.find(x => x > 3);       // 4
arr.some(x => x > 4);       // true
arr.every(x => x > 0);      // true
arr.includes(3);            // true
arr.indexOf(3);             // 2
arr.slice(0, 3);            // [1, 2, 3]
arr.concat([6, 7]);         // [1, 2, 3, 4, 5, 6, 7]
arr.reverse();              // [5, 4, 3, 2, 1]
arr.sort((a, b) => b - a);  // 降序
arr.flatMap(x => [x, x*2]); // [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
arr.length;                 // 5
```

### `Object` 方法

```javascript
const obj = { name: 'John', age: 30 };

Object.keys(obj);            // ['name', 'age']
Object.values(obj);          // ['John', 30]
Object.entries(obj);         // [['name', 'John'], ['age', 30]]
Object.assign({}, obj, { city: 'NYC' });
Object.freeze(obj);          // 不可变
Object.hasOwn(obj, 'name');  // true
```

---

## 6. 可用 Node.js 模块

### `crypto` - 加密

```javascript
const crypto = require('crypto');

// 哈希
const hash = crypto.createHash('sha256').update('data').digest('hex');

// HMAC
const hmac = crypto.createHmac('sha256', 'secret').update('data').digest('hex');

// 随机字节
const random = crypto.randomBytes(16).toString('hex');

// UUID
const uuid = crypto.randomUUID();
```

### `zlib` - 压缩

```javascript
const zlib = require('zlib');

// 压缩
const compressed = zlib.gzipSync(Buffer.from('data'));

// 解压
const decompressed = zlib.gunzipSync(compressed).toString();
```

### `url` - URL 解析

```javascript
const url = require('url');

const parsed = url.parse('https://api.example.com/path?query=1');
// parsed.protocol, parsed.host, parsed.pathname, parsed.query
```

### `querystring` - 查询字符串

```javascript
const qs = require('querystring');

const query = qs.stringify({ name: 'John', age: 30 });
// 'name=John&age=30'

const parsed = qs.parse('name=John&age=30');
// { name: 'John', age: 30 }
```

### `util` - 工具

```javascript
const util = require('util');

// promisify
const fs = require('fs');
const readFile = util.promisify(fs.readFile);
```

---

## 什么不可用

### ❌ 阻止的函数

```javascript
// ❌ Auth helpers(出于安全)
$helpers.httpRequestWithAuthentication
$credentials

// ❌ 大多数 require
require('axios')
require('lodash')
require('moment')  // 用 Luxon
require('axios')
require('node-fetch')

// ❌ 文件系统
require('fs')
require('path')

// ❌ 子进程
require('child_process')

// ❌ 网络(直接)
require('net')
require('http')  // 用 $helpers.httpRequest()
require('https') // 用 $helpers.httpRequest()
```

### ❌ 全局变量

```javascript
// ❌ 不可用
process          // 受限
global           // 受限
__dirname        // 不可用
__filename       // 不可用
```

### ❌ 浏览器 API

```javascript
// ❌ 不可用(非浏览器环境)
window
document
localStorage
sessionStorage
```

---

## 小结

**常用函数**:
- `$helpers.httpRequest()` - HTTP 请求
- `DateTime` (Luxon) - 日期时间
- `$jmespath()` - JSON 查询
- `$getWorkflowStaticData()` - 持久化

**最佳实践**:
- 用 `$helpers.httpRequest()` 而不是 `http` 模块
- 用 Luxon 而不是原生 Date
- 用 `$jmespath()` 处理复杂 JSON
- 用 `$getWorkflowStaticData()` 跨迭代持久化

**安全**:
- 不暴露凭据
- 用 `$helpers.httpRequest()` + 手动认证
- 用 Set 节点传递 secret 到 Code 节点

**性能**:
- 优先用数组方法(map/filter/reduce)
- 避免不必要的 await(并行用 Promise.all)
- 缓存昂贵计算到 staticData

**相关**:
- [DATA_ACCESS.md](DATA_ACCESS.md) - 数据访问
- [COMMON_PATTERNS.md](COMMON_PATTERNS.md) - 生产模式
- [ERROR_PATTERNS.md](ERROR_PATTERNS.md) - 错误防范
