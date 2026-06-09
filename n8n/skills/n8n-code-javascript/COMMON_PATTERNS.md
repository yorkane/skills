# 常见模式 - JavaScript Code 节点

10 个生产验证的 Code 节点模式集合。

---

## 概览

从真实生产 workflow 中提取的可复用模式:

1. 多源数据聚合
2. 正则过滤与模式匹配
3. Markdown 解析与结构化数据提取
4. JSON 对比与校验
5. CRM 数据转换
6. 发布信息处理
7. 带上下文的数组转换
8. Slack Block Kit 格式化
9. Top N 过滤与排名
10. 字符串聚合与报告

---

## 模式 1:多源数据聚合

**场景**: 合并来自多个 API、webhook 或节点的数据

```javascript
const allItems = $input.all();
const results = [];

for (const item of allItems) {
  const sourceName = item.json.name || 'Unknown';
  const data = item.json;

  // 解析源特定结构
  if (sourceName === 'API1' && data.results) {
    results.push({
      json: {
        title: data.results[0].title,
        source: 'API1',
        url: data.results[0].url
      }
    });
  } else if (sourceName === 'API2' && data.items) {
    results.push({
      json: {
        title: data.items[0].name,
        source: 'API2',
        url: data.items[0].link
      }
    });
  }
}

return results;
```

---

## 模式 2:正则过滤 & 模式匹配

**场景**: 从文本中提取模式、提及、关键字

```javascript
const allItems = $input.all();
const matches = {};

for (const item of allItems) {
  const text = item.json.text || '';
  const found = text.match(/\b([A-Z]{2,5})\b/g);

  if (found) {
    found.forEach(match => {
      matches[match] = (matches[match] || 0) + 1;
    });
  }
}

return [{
  json: {
    tickerSymbols: matches,
    uniqueCount: Object.keys(matches).length
  }
}];
```

### 提取 URL

```javascript
const allItems = $input.all();
const urls = [];

const urlPattern = /https?:\/\/[^\s]+/g;

for (const item of allItems) {
  const text = item.json.text || '';
  const found = text.match(urlPattern);
  if (found) {
    urls.push(...found);
  }
}

return [{
  json: {
    urls: [...new Set(urls)],
    totalUrls: urls.length
  }
}];
```

### 提取邮箱

```javascript
const emailPattern = /[\w.-]+@[\w.-]+\.\w+/g;
const text = $input.first().json.body.text;
const emails = text.match(emailPattern) || [];

return [{
  json: { emails }
}];
```

---

## 模式 3:Markdown 解析与结构化数据提取

**场景**: 解析 markdown 文本提取结构化信息

```javascript
const markdown = $input.first().json.body;

const result = {
  title: null,
  sections: [],
  links: [],
  codeBlocks: []
};

// 提取标题(第一个 # 标题)
const titleMatch = markdown.match(/^#\s+(.+)$/m);
if (titleMatch) result.title = titleMatch[1];

// 提取章节(## 标题)
const sectionMatches = markdown.matchAll(/^##\s+(.+)$/gm);
for (const match of sectionMatches) {
  result.sections.push(match[1]);
}

// 提取链接
const linkMatches = markdown.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g);
for (const match of linkMatches) {
  result.links.push({
    text: match[1],
    url: match[2]
  });
}

// 提取代码块
const codeMatches = markdown.matchAll(/```(\w+)?\n([\s\S]*?)```/g);
for (const match of codeMatches) {
  result.codeBlocks.push({
    language: match[1] || 'plain',
    code: match[2].trim()
  });
}

return [{ json: result }];
```

---

## 模式 4:JSON 对比与校验

**场景**: 对比两个 JSON 结构找出差异

```javascript
function deepCompare(obj1, obj2, path = '') {
  const differences = [];

  const keys = new Set([...Object.keys(obj1 || {}), ...Object.keys(obj2 || {})]);

  for (const key of keys) {
    const currentPath = path ? `${path}.${key}` : key;
    const val1 = obj1 ? obj1[key] : undefined;
    const val2 = obj2 ? obj2[key] : undefined;

    if (typeof val1 === 'object' && typeof val2 === 'object' && val1 !== null && val2 !== null) {
      differences.push(...deepCompare(val1, val2, currentPath));
    } else if (val1 !== val2) {
      differences.push({
        path: currentPath,
        old: val1,
        new: val2
      });
    }
  }

  return differences;
}

const oldData = $node["Previous"].json;
const newData = $input.first().json;

const diffs = deepCompare(oldData, newData);

return [{
  json: {
    hasChanges: diffs.length > 0,
    changeCount: diffs.length,
    differences: diffs
  }
}];
```

### 简单字段对比

```javascript
const old = $node["Previous"].json;
const current = $input.first().json;

const changes = [];
for (const key of Object.keys(current)) {
  if (old[key] !== current[key]) {
    changes.push({
      field: key,
      old: old[key],
      new: current[key]
    });
  }
}

return [{
  json: { changes }
}];
```

---

## 模式 5:CRM 数据转换

**场景**: 转换 CRM 数据格式

```javascript
const crmData = $input.first().json;

return [{
  json: {
    contact_id: crmData.id,
    full_name: `${crmData.first_name} ${crmData.last_name}`,
    primary_email: crmData.email,
    phone: crmData.phone || null,
    company: crmData.company?.name || 'Unknown',
    tags: (crmData.tags || []).map(t => t.name),
    created_at: new Date(crmData.created_at).toISOString(),
    last_activity: crmData.last_activity_at
      ? new Date(crmData.last_activity_at).toISOString()
      : null,
    lifecycle_stage: crmData.lifecycle_stage || 'lead',
    custom_fields: {
      source: crmData.utm_source,
      campaign: crmData.utm_campaign,
      score: crmData.lead_score || 0
    }
  }
}];
```

---

## 模式 6:发布信息处理

**场景**: 处理 GitHub release / 版本信息

```javascript
const release = $input.first().json;

const changes = {
  breaking: [],
  features: [],
  fixes: [],
  other: []
};

const body = release.body || '';
const lines = body.split('\n');

let currentSection = 'other';
for (const line of lines) {
  if (line.match(/^##\s+.*breaking/i)) currentSection = 'breaking';
  else if (line.match(/^##\s+.*feature/i)) currentSection = 'features';
  else if (line.match(/^##\s+.*fix/i)) currentSection = 'fixes';
  else if (line.startsWith('##')) currentSection = 'other';
  else if (line.trim().startsWith('-') || line.trim().startsWith('*')) {
    changes[currentSection].push(line.replace(/^[-*]\s+/, '').trim());
  }
}

return [{
  json: {
    tag: release.tag_name,
    name: release.name,
    publishedAt: release.published_at,
    author: release.author?.login,
    url: release.html_url,
    isPrerelease: release.prerelease,
    changes: {
      breaking: changes.breaking,
      features: changes.features,
      fixes: changes.fixes
    },
    stats: {
      breakingCount: changes.breaking.length,
      featureCount: changes.features.length,
      fixCount: changes.fixes.length
    }
  }
}];
```

---

## 模式 7:带上下文的数组转换

**场景**: 转换数组同时保留索引/上下文信息

```javascript
const allItems = $input.all();

return allItems.map((item, index) => ({
  json: {
    ...item.json,
    _meta: {
      index: index,
      total: allItems.length,
      isFirst: index === 0,
      isLast: index === allItems.length - 1,
      processedAt: new Date().toISOString()
    }
  }
}));
```

### 带 pairedItem 的转换

```javascript
const allItems = $input.all();

return allItems.map((item, index) => ({
  json: {
    id: item.json.id,
    name: item.json.name,
    transformed: true
  },
  pairedItem: { item: index }  // 保留与输入的映射
}));
```

---

## 模式 8:Slack Block Kit 格式化

**场景**: 格式化丰富的 Slack 消息

```javascript
const data = $input.first().json;

const blocks = [
  {
    type: "header",
    text: {
      type: "plain_text",
      text: `📊 ${data.title || 'Report'}`
    }
  },
  {
    type: "section",
    fields: [
      { type: "mrkdwn", text: `*Total:*\n$${data.total}` },
      { type: "mrkdwn", text: `*Count:*\n${data.count}` },
      { type: "mrkdwn", text: `*Average:*\n$${data.average}` },
      { type: "mrkdwn", text: `*Period:*\n${data.period}` }
    ]
  },
  {
    type: "divider"
  },
  {
    type: "section",
    text: {
      type: "mrkdwn",
      text: `*Top Items:*\n${data.topItems.map(i => `• ${i.name}: $${i.value}`).join('\n')}`
    }
  },
  {
    type: "actions",
    elements: [
      {
        type: "button",
        text: { type: "plain_text", text: "View Details" },
        url: data.detailsUrl,
        style: "primary"
      }
    ]
  }
];

return [{
  json: {
    text: `${data.title}: ${data.count} items`,
    blocks: blocks
  }
}];
```

---

## 模式 9:Top N 过滤与排名

**场景**: 排序并限制结果

```javascript
const allItems = $input.all();
const n = 10;  // Top 10

const topItems = allItems
  .sort((a, b) => (b.json.score || 0) - (a.json.score || 0))
  .slice(0, n);

return topItems.map((item, rank) => ({
  json: {
    rank: rank + 1,
    ...item.json
  }
}));
```

### 多键排序

```javascript
const allItems = $input.all();

const sorted = allItems.sort((a, b) => {
  // 优先按 score 降序
  const scoreDiff = (b.json.score || 0) - (a.json.score || 0);
  if (scoreDiff !== 0) return scoreDiff;

  // 然后按 name 升序
  return (a.json.name || '').localeCompare(b.json.name || '');
});

return sorted.map(item => ({ json: item.json }));
```

---

## 模式 10:字符串聚合与报告

**场景**: 聚合数据生成可读报告

```javascript
const allItems = $input.all();

// 按类别分组
const byCategory = allItems.reduce((acc, item) => {
  const cat = item.json.category || 'uncategorized';
  if (!acc[cat]) acc[cat] = [];
  acc[cat].push(item.json);
  return acc;
}, {});

// 生成报告
const report = Object.entries(byCategory).map(([category, items]) => {
  const total = items.reduce((sum, i) => sum + (i.amount || 0), 0);
  return {
    category,
    count: items.length,
    total,
    average: total / items.length,
    items: items.map(i => i.name).join(', ')
  };
});

return [{
  json: {
    summary: {
      totalCategories: report.length,
      totalItems: allItems.length,
      grandTotal: allItems.reduce((sum, i) => sum + (i.amount || 0), 0)
    },
    byCategory: report,
    generatedAt: new Date().toISOString()
  }
}];
```

---

## 选择正确的模式

| 场景 | 模式 |
|------|------|
| 合并多源数据 | 模式 1: 多源聚合 |
| 提取文本模式 | 模式 2: 正则过滤 |
| 解析 markdown | 模式 3: Markdown 解析 |
| 对比 JSON | 模式 4: JSON 对比 |
| 转换 CRM 字段 | 模式 5: CRM 转换 |
| 处理 release notes | 模式 6: 发布信息 |
| 保留数组上下文 | 模式 7: 带上下文转换 |
| 富文本 Slack 消息 | 模式 8: Block Kit |
| 排序 + 限制 | 模式 9: Top N |
| 生成报告 | 模式 10: 字符串聚合 |

---

## 小结

**核心要点**:

1. **过滤先行,转换后行** - 早过滤减少数据量
2. **始终返回正确格式** - `[{json: {...}}]`
3. **使用描述性变量** - 代码即文档
4. **处理边界情况** - 空输入、null 字段
5. **pairedItem 用于映射** - 保留输入关联

**生产经验法则**:

- 90% 的 Code 节点遵循这 10 个模式之一
- 用 ES6+ 特性(map、filter、reduce、模板字面量)
- 优先用数组方法而非循环
- 始终在 $json 包装中返回

**相关**:

- [DATA_ACCESS.md](DATA_ACCESS.md) - 数据访问基础
- [ERROR_PATTERNS.md](ERROR_PATTERNS.md) - 错误防范
- [BUILTIN_FUNCTIONS.md](BUILTIN_FUNCTIONS.md) - 辅助函数
