# Vue 3 + Quasar UMD 实现规则

## 默认目录与职责

新项目默认保持以下结构：

```text
/
├── index.html
├── app.js
├── api.js
├── i18n.js
├── app.css
└── vendor/
    ├── quasar-umd.js
    ├── quasar-umd.css
    ├── fonts/
    └── manifest.json
```

- `index.html`：页面模板、Quasar 组件、导航、表格、表单、Dialog 和静态资源引用。
- `app.js`：主入口或管理壳的 Vue 初始化、状态、事件和业务交互。
- `api.js`：API 地址、`fetch()`、请求方法、JSON 解析和 HTTP 错误处理。
- `i18n.js`：简体中文/英文业务词典、当前语言、持久化与跨 iframe 同步。
- `app.css`：页面布局、业务间距、技术字段样式和少量 Quasar 覆盖。
- `vendor/`：由 `scripts/update_vendor.py` 管理的本地静态资源。框架 JS 和 CSS 分别合并为一个文件，语言包和 MDI v7 图标集包含在 JS bundle 中，MDI 字体包含在 CSS bundle 引用的本地字体目录中。

管理壳通过右侧 iframe 加载独立应用 HTML 时，每个应用的 Vue 初始化、状态、表单、Loading、事件和 Notify/Dialog 逻辑直接放在该 HTML 底部的内联 `<script>` 中，不为应用页创建 `users.js`、`settings.js` 等同名外置脚本。`vendor/quasar-umd.js` 与共享 `api.js` 继续外部引用，避免复制框架和请求封装。

资源同步默认使用以下来源：

- Vue 和 Quasar：npm registry 的最新稳定版本。
- Quasar 中文、英文语言包：Quasar 包内的 UMD 资源。
- Quasar 图标集：Quasar 包内的 `mdi-v7.umd.prod.js`。
- MDI 字体：`@mdi/font` 的最新稳定 7.x 版本，匹配官方推荐的 `^7.0.0`。
- Roboto：官方 Google Fonts CSS URL。

使用 `scripts/update_vendor.py --source` 指定 npm registry 镜像，使用 `--font-source` 指定字体 CSS 来源。生产部署不直接引用 CDN，所有 CSS、JavaScript 和字体都放在项目内。

## UMD 初始化

浏览器脚本通过全局变量使用 Vue 和 Quasar，不使用构建工具导入：

```js
const { createApp, ref, reactive, computed, onMounted } = Vue

const app = createApp({
  setup () {
    return {}
  }
})

app.use(Quasar)
Quasar.Lang.set(Quasar.Lang.zhCN)
Quasar.IconSet.set(Quasar.IconSet.mdiV7)
app.mount('#q-app')
```

普通 HTML 模板中的所有 `q-*` 标签都显式闭合，不使用自闭合写法。

## 组件与页面

优先使用 Quasar 已有组件：

```text
布局       QLayout / QHeader / QDrawer / QPageContainer / QPage
数据列表   QTable / QList / QItem
输入       QInput / QSelect / QCheckbox / QToggle
操作       QBtn / QForm
弹层       QDialog / QMenu / QTooltip
状态       QBadge / QChip
反馈       Notify / Dialog / Loading / QInnerLoading / QLinearProgress
分页       QTable pagination / QPagination
```

默认管理页面使用紧凑、低装饰、高信息密度的视觉风格，优先 `dense`、`outlined`、`flat`、`bordered`。不要为普通 CRUD 页面增加自定义组件库、复杂动画、无必要图表或另一套 UI 框架。

简单多页面状态优先使用 `ref()` 控制 `currentPage`，不要主动引入 Vue Router。状态优先使用 `ref()`、`reactive()` 和 `computed()`，不要主动引入 Pinia。

## i18n

默认同时支持 `zh-CN` 和 `en-US`。Quasar `Lang` 负责组件内置文本，共享 `i18n.js` 负责业务文本，两者切换时保持一致。语言偏好使用 `localStorage` 持久化；存在管理壳和 iframe 时，由管理壳广播语言变化，已打开及之后加载的所有 iframe 都读取并响应同一语言。

所有用户可见业务文本都进入词典，包括页面标题、导航、表格列、字段标签、占位符、按钮、Tooltip、Dialog、Notify、校验错误、Loading 和空状态。不要只切换菜单或只调用 `Quasar.Lang.set()`，也不要在模板和页面脚本中遗留单一语言硬编码。

## API 与反馈

普通请求集中在 `api.js`，优先使用相对路径 `/api/*`，不要写死环境域名。请求封装应检查 `response.ok`，处理 `204`，并将有意义的错误交给页面展示。

```js
const API_BASE = '/api'

async function request (path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  return response.status === 204 ? null : response.json()
}
```

网络操作要绑定 Loading 状态并显示失败原因；成功操作使用 Quasar Notify。删除、覆盖和其他不可逆操作使用 Quasar Dialog 确认。前端负责显示和交互，后端负责权限、业务规则、校验和持久化。

## 表格、表单与 CSS

- 普通数据列表优先使用 `QTable`，常用默认属性为 `dense`、`flat`、`bordered`。
- 数据量较大时优先后端分页和筛选，不将全部数据无条件加载到浏览器。
- 新增和编辑优先使用 `QDialog + QForm`。
- 优先使用 Quasar 自带样式能力，只在必要时修改 `app.css`。
- 不重新实现按钮、输入框、弹窗、表格、菜单、Tooltip 或 Loading 的通用样式。

## 静态部署与修改边界

页面应能由普通 HTTP Server 直接部署，常见代理关系为静态文件服务和 `/api/` 反向代理。不要为了开发页面创建 `package.json`、Node 运行进程或构建流程，除非用户明确要求。

修改前先阅读相关文件和已有写法；先改 API，再补状态和交互，最后补模板和必要 CSS。不要进行无关重构、大规模重命名或技术栈迁移。
