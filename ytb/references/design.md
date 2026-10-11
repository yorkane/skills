# 视频下载与监控方案设计（MeTube + yt-dlp）

## 1. 系统定位

一个本地视频下载与监控服务，作为视频分析的**数据供给层**：
持续监控 YouTube / Bilibili 等平台的指定频道与视频，
下载后产出分析所需的三要素——**视频、音频、字幕**，供本地分析管线消费。

## 2. 架构

```
平台 (YouTube / Bilibili / …)
        │  yt-dlp 提取器
        ▼
MeTube (yt-dlp 的 Web 服务, :8099)
  ├─ 单次下载  POST /add
  ├─ 订阅监控  POST /subscribe   ← 周期性轮询频道/播放列表
  └─ 状态查询  state/*.json + Socket.IO 推送
        │
        ▼ 落盘
/data/app/metube/downloads/
  └─ <video_id> - <title>.{mp4,info.json,jpg,...}
        │
        ▼ 分析侧增量发现 (轮询 completed.json / 监听目录)
本地分析管线 (ASR → 字幕, 抽帧, 理解)
```

## 3. 关键设计决策

### 3.1 稳定命名：以视频 ID 打头
`OUTPUT_TEMPLATE=%(id)s - %(title)s.%(ext)s`。
平台标题可变、可含特殊字符，但 `id`（如 `BV1uv411q7Mv`）全局稳定，
便于跨次下载去重、跨天关联、与分析结果建立稳定映射。

### 3.2 下载归档防重：download_archive
`YTDL_OPTIONS.download_archive = /archive/downloaded.txt`。
yt-dlp 把已下载条目写入此文件，重复提交同一视频自动跳过，
**订阅高频轮询也不会重复下载**。这是订阅监控的核心保障。

### 3.3 元数据全量落盘
`writeinfojson + writethumbnail + embed_metadata`。
`info.json` 携带 `uploader_id / channel / duration / 描述 / 标签` 等，
是分析侧建立"视频档案"的权威来源，无需再回源抓取。

### 3.4 目录分区（按用途）
通过 `folder` 参数（MeTube 的 `CUSTOM_DIRS`）把下载分流：

- 订阅监控 → `sub_watch/`（频道自动更新）
- 单次分析 → 按任务命名
- 仅音频 → `audio_only/`（`download_type=audio`）

### 3.5 字幕策略（重要）
**不能依赖平台字幕。** 实测 B 站即使 `subtitle_mode=prefer_manual, subtitle_language=all`
也拿不到字幕文件（多数平台字幕需登录或非公开）。因此字幕以**本地生成**为准：

1. 优先抽取平台字幕（若存在则直接用，免费且带时间轴）；
2. 否则本地生成：音频 → ASR（如 Qwen3-ASR）→ 带时间轴字幕；
3. 烧录在画面里的硬字幕 → 抽帧 + OCR 识别。

详见 storage.md 的三要素落盘约定。

### 3.6 反爬与登录态（cookies）
YouTube 对未登录请求限制严格，B 站大会员/高清也需登录态。
yt-dlp 支持 `"cookiefile": "/config/cookies.txt"`（Netscape 格式，挂载进容器）。
需要访问受限内容时，导出浏览器 cookies 放到 `/data/app/metube/config/cookies.txt`
并在 `ytdl_options.json` 加 `cookiefile` 字段。

## 4. MeTube API 速查

| 端点 | 方法 | 说明 |
|---|---|---|
| /add | POST | 单次下载；`{url, download_type(video/audio), format, quality, folder, subtitle_language, subtitle_mode, auto_start}` |
| /subscribe | POST | 订阅；额外 `check_interval_minutes`, `title_regex`, `skip_subscriber_only` |
| /presets | GET | 列出命名预设 |
| /retry | POST | 重试失败项 `{id}` |
| download/, audio_download/ | GET | 静态服务下载目录 |
| Socket.IO | — | `added/updated/completed/canceled` 实时推送 |

状态文件（`/data/app/metube/state/`）：
`queue.json`（进行中）、`completed.json`（已完成+失败）、`subscriptions.json`（订阅列表，`{schema_version, items:[...]}`）。

### /add 与 /subscribe 参数要点

- `download_type`: `video` | `audio`
- `format`（video）: `any | mp4 | ios`；（audio）: `mp3 | opus | m4a | flac | wav`
- `subtitle_mode`: `auto_only | manual_only | prefer_auto | prefer_manual`
- `subtitle_language`: 如 `all`, `zh-Hans,en`
- 订阅仅接受频道/播放列表 URL，单视频不能订阅
- 同一 URL 已在队列/归档中时，`/add` 返回 "Already in queue"

## 5. 订阅监控机制

订阅 = 周期性抓取频道/播放列表最新条目 → 与已见集合(`seen_ids`)比对 →
新增项自动入队下载。相关配置：

- `SUBSCRIPTION_DEFAULT_CHECK_INTERVAL`（默认 60 min）
- `SUBSCRIPTION_SCAN_PLAYLIST_END`（每次从最新往回扫多少条，默认 50）
- `SUBSCRIPTION_MAX_SEEN_IDS`（状态上限，默认 50000）
- `title_regex`：只下载标题匹配的视频（Python 正则，前缀 `(?i)` 忽略大小写）

配合 `download_archive`，即使扫描范围大也不会重复落盘。
首次订阅会把频道历史全部标记为 seen（本例 50 条），之后只追新增。

## 6. 监控频率建议

- 高产频道：`check_interval_minutes=30`
- 一般频道：`60`
- 低频/合集：`360`

频率过高会被平台限流；配合 cookies 与合理间隔更稳。

## 7. 部署实况（本机 2026-08-28）

- 容器 `metube`（ghcr.io/alexta69/metube），宿主端口 **8099**（8081 已被占用）
- 目录 `/data/app/metube/`：
  - `docker-compose.yml` — compose 定义（OUTPUT_TEMPLATE / 挂载 / 环境变量）
  - `config/ytdl_options.json` — yt-dlp 全局选项（热加载，改文件即生效）
  - `downloads/` → 容器 `/downloads`（视频/音频/元数据）
  - `state/` → 容器 `/state`（queue/completed/subscriptions）
  - `archive/downloaded.txt` → download_archive
- 测试结论：
  - B 站单视频下载 ✅（video + info.json + 缩略图）
  - 音频下载 ✅（mp3, folder 分流）
  - 命名模板 `%(id)s - %(title)s` ✅
  - download_archive 防重 ✅（同 URL 二次提交不重复下载）
  - 订阅频道 ✅（扫描 50 条历史并标记）
  - 字幕文件 ❌（B 站无法直接拉取 → 需本地 ASR/OCR 生成）
  - 无效 BV 号 → extractor error（KeyError bvid）✅ 有错误回执
- YouTube 直连不通（本机网络环境），需要代理或 cookies 方案落地后再测；
  `ytdl_options.json` 可加 `"proxy": "http://..."` 或容器环境变量 `HTTPS_PROXY`。

## 8. 已知问题与修复记录

### 8.1 特殊标题经网关下载报 "Invalid char in url path"（2026-08-28 已修复）

现象：经 authz 网关访问 `/download/<中文目录>/<特殊标题>.mp4` 时，
metube（aiohttp）返回 400 `Invalid char in url path`。

根因：网关 `proxy_pass $变量` 转发时使用 `ngx.var.uri`（nginx 已解码的路径），
`%2F`/`%20`/`%E6%98%9F` 被解码为裸字符进入上游请求行，aiohttp 按 HTTP 规范拒绝。

修复：转发前按段重新百分号编码（`encode_upstream_path`，保留 `/`）。
- 源码：/home/aigc/ChatGPT/authz/lualib/resty/authz/gateway/proxy.lua（已打补丁）
- 运行中容器：已热补丁 + 备份（`init.lua.bak-utf8path`）+ `nginx -s reload`，实测生效
- **注意**：容器补丁在容器重建后会丢失，重建网关前需重新应用或用打过补丁的镜像构建

结论：保留可读的中文标题文件名（`%(uploader,channel|NA)s/%(title)s [%(id)s]`）
无需为规避此问题牺牲命名可读性。
