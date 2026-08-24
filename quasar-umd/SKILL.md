---
name: quasar-umd
description: 开发和维护 Vue 3 + Quasar UMD 的轻量级前端，适用于现有项目改造或从零创建静态管理页面；默认不引入 Node、Vite 或 Router，除非用户明确指定。
---

# Quasar UMD

用于 Vue 3 Browser Global + Quasar UMD 项目的前端开发。优先保持静态文件、低依赖、前后端分离和容易维护。

## 工作方式

先检查项目已有的文件结构、Vue/Quasar 版本、资源引用方式和构建配置。

- 现有项目优先遵循原有技术栈和目录结构，不主动迁移或重写。
- 新项目或用户未指定技术栈时，默认使用 Vue 3 Browser Global、Quasar UMD、原生 `fetch()` 和普通 CSS。
- 用户明确要求 Node、Vite、Vue Router 或其他技术时，遵循用户要求并调整实现。
- 优先使用 Quasar 组件和项目已有写法，采用最小范围修改。
- 普通 API 请求集中在 `api.js`。主入口页面的状态和交互集中在 `app.js`；通过右侧 iframe 加载的独立应用页必须把本页 Vue 初始化、状态和交互脚本内联在对应 HTML 底部，不再创建页面级外置 JS。业务样式仍集中在共享或页面 CSS 中。
- 默认提供简体中文 (`zh-CN`) 与英文 (`en-US`) i18n 切换。业务词典集中在共享 `i18n.js`，语言偏好持久化，并在管理壳、菜单 iframe 和右侧应用 iframe 间全局同步；标题、表格列、按钮、Tooltip、Dialog、Notify、校验与空状态都不得硬编码为单一语言。
- 网络操作必须有 Loading 和可见错误反馈；删除、覆盖等危险操作必须确认。
- 不主动增加状态管理、组件库、事件总线或复杂抽象。

## 新项目

从零创建时，默认使用：

```text
index.html
app.js
api.js
i18n.js
app.css
vendor/
```

使用脚本创建基础文件：

```bash
python3 /home/aigc/.codex/skills/quasar-umd/scripts/scaffold.py .
```

项目名称默认取目标目录名。脚本只创建缺失文件；覆盖已有文件必须显式使用 `--overwrite`。

同步并合并 Vue、Quasar UMD、MDI v7 图标字体和中英文语言包：

```bash
python3 /home/aigc/.codex/skills/quasar-umd/scripts/update_vendor.py .
```

该脚本默认解析最新稳定版，将 Vue、Quasar、语言包和 MDI v7 图标集合并为 `vendor/quasar-umd.js`，将 Roboto、MDI 和 Quasar CSS 合并为 `vendor/quasar-umd.css`，并把字体放入 `vendor/fonts/`。精确版本、资源来源和 SHA-256 写入 `vendor/manifest.json`。资源下载完成并校验通过后才提交到项目；可用 `--source` 指定 npm registry 镜像、`--font-source` 指定字体 CSS，或用版本参数锁定版本。生产页面只引用这一个框架 JS 和 CSS，不依赖运行时 CDN。

## 详细规则

使用 Quasar UMD 组件、模板、API、CSS、静态部署和验证规则时，读取 [references/quasar-umd.md](references/quasar-umd.md)。

## 完成前检查

- 所有资源路径存在且版本清单准确。
- 所有 `q-*` 标签在普通 HTML 模板中显式闭合。
- 没有把普通 API 请求散落到模板或页面事件中。
- 右侧 iframe 应用页的页面级 JavaScript 已内联在对应 HTML，未额外引用同名页面 JS 文件。
- 简体中文与英文切换可全局影响主壳和所有 iframe 页面，业务文案无遗漏的单语言硬编码。
- Loading、错误提示和危险操作确认均可见且可用。
- 没有无用户要求地增加 Node 依赖、构建步骤或新的 UI 框架。
- 页面可由普通静态 HTTP Server 直接提供。
