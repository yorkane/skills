---
name: video-sniff
description: 用 Playwright/CDP 驱动浏览器时自动嗅探并下载视频（cat-catch 的本地化改造）。当需要在自动化浏览（playwright-cli、playwright-core、CDP 附着真实 Chrome）过程中把网页里播放的视频/音频/流媒体落盘，或用户给出视频页 URL 要求「下载视频 / 抓视频 / 嗅探媒体地址 / 保存播放内容」时使用。支持 HLS(m3u8, 含 AES-128 解密)、DASH(mpd)、直链 mp4/webm；音视频分离轨道自动合并；默认按页面标题命名、下载到 /data/download/video/。不适用于 yt-dlp 能直接覆盖的主流站点（那走 skill: ytb / MeTube），也不适用于纯转码剪辑。
---

# video-sniff：浏览器嗅探下载视频

来源：把 [cat-catch](https://github.com/xifangczy/cat-catch)（浏览器扩展，2.7.2）的媒体嗅探与 HLS/DASH 解析能力，改造成本机可编程调用的 skill，配合 Playwright / CDP 使用。

## 硬性约束（先读这一节）

**1. 默认方案 = Playwright 驱动浏览器。** 用户没有指定方案时，一律用 Playwright 打开页面、真实渲染、
监听网络，再决定下载哪个媒体源。命令：`vsdl --page <页面URL>`（内部即 `sniff.mjs`，默认自起 chromium），
或已在用 playwright-cli 时用 `sniff_pw.py --session <会话名>`。

**2. 禁止绕过浏览器直接取页面。** 不要用内置模型的知识、直接 HTTP 抓取、或凭空猜测去推断视频地址与
页面内容。视频源往往依赖 JS 运行、MSE/blob、动态签名（如 auth_key）、登录态，只有真实浏览器里跑过才有；
凭猜测给的地址基本是错的，也拿不到正确的页面标题（文件名会变成无意义字符串）。

**3. 只有用户明确要求时才走其它方案：**

| 用户怎么说 | 用什么 |
|---|---|
| 没指定 / 「下载这个页面的视频」 | **Playwright（默认）** |
| 「用 CDP」「附着我的 Chrome」「用我已登录的浏览器」 | `--cdp http://127.0.0.1:9222`（配 `cdp-chrome.sh`） |
| 已给出完整媒体地址（.m3u8/.mpd/.mp4 直链） | `vsdl --url` 直连下载 |
| 已经在用 playwright-cli 操作同一页面 | `sniff_pw.py --session` |

**4. 不要用嗅探器替代下载器，也不要用下载器替代嗅探。** 拿不准页面里是什么时，先嗅探出报告给人看，
再下载；不要把 `--url` 直连当成「省事」的默认路径。

**5. 下载前先确认页面真的在播放。** Playwright 路径会自动尝试播放；若候选为空，按下方「排错顺序」处理
（延长监听、触发播放、查看是否弹登录框），而不是改成直接抓取页面。

## 能力

| 能力 | 说明 |
|---|---|
| 网络嗅探 | 监听页面所有请求，按扩展名 + content-type + 播放器特征判定视频/音频/流媒体候选，打分并推荐最优项 |
| 驱动方式 | **默认：Playwright 自起浏览器**（`vsdl --page`）；另可显式 `--cdp` 附着调试端口 Chrome、或用 `sniff_pw.py --session` 读取已在用的 playwright-cli 会话 |
| HLS 下载 | master/子播放列表、清晰度选择、`EXT-X-KEY` AES-128 解密、`EXT-X-MAP`、`EXT-X-BYTERANGE`、独立音频轨自动合并 |
| DASH 下载 | MPD 解析（SegmentTemplate/SegmentList/SegmentBase + SegmentTimeline），视频/音频分离轨自动合并 |
| 直链下载 | mp4/webm/mkv 等直链，aria2c 多线程 + Referer/Cookie |
| 命名 | 默认用页面标题（优先 og:title，去掉站点名后缀），冲突自动加序号 |

## 快速使用

> 未指定方案时全部走 Playwright（下面的 1 即默认路径）。2、3 是用户明确要求时才用。

```bash
SKILL=/home/aigc/.codex/skills/video-sniff

# 1) 默认方案（Playwright 驱动浏览器）：嗅探 + 下载一步到位
$SKILL/scripts/vsdl --page 'https://example.com/video/1'

# 想分两步看候选再下：先嗅探出报告，再下载
node $SKILL/scripts/sniff.mjs --url 'https://example.com/video/1' --out /tmp/sniff.json
$SKILL/scripts/vsdl --report /tmp/sniff.json

# 2) 附着到已有 Chrome（复用登录态，CDP）
$SKILL/scripts/cdp-chrome.sh start                     # 起一个带 9222 调试端口的 Chrome（首次）
node $SKILL/scripts/sniff.mjs --cdp http://127.0.0.1:9222 --url 'https://example.com/video/1' --out /tmp/sniff.json
$SKILL/scripts/vsdl --report /tmp/sniff.json

# 3) 已知媒体地址直接下载
$SKILL/scripts/vsdl --url 'https://cdn/x/master.m3u8' --referer 'https://example.com/video/1' --title '标题'
$SKILL/scripts/vsdl --url 'https://cdn/a.mp4' --kind file --outdir /data/download/video
```

## 默认约定

- 下载目录：`/data/download/video/`（`--outdir` 或 `$VSNIFF_DOWNLOAD_DIR` 覆盖）
- 文件名：页面标题（`--title` / `--name` 覆盖）；重名自动 `-2`、`-3`
- 容器：默认保持原始编码，只做必要封装。H.264+AAC → `.mp4`，其它 → `.mkv`，纯音频保持原扩展名
- 嗅探报告：`/data/tmp/vsniff/<slug>-<ts>.json`（`$VSNIFF_REPORT_DIR` 可改）
- 临时文件：`/data/tmp/vsniff/`

## 详细用法

见 `references/usage.md`（命令行全参数、JSON 输出字段、常见站点适配与排错）。

## 排错顺序

1. 嗅探不到候选 → 用 `--seconds 40` 延长观察，用 `--click-play` 触发播放，或 `--headed` 看页面是否弹登录框；也可 `--cdp` 附着到手工打开的真浏览器。
2. 能嗅到但下载 403 → 补 `--referer` / `--cookie`（直接从嗅探报告里取）。
3. m3u8 解密失败 → 检查 `EXT-X-KEY` 的 `METHOD`（SAMPLE-AES 不支持，会明确报错）。
4. 下载产物无声 → 确认是否为分离音轨站点，日志里会有「检测到独立音频轨」提示与所选音轨信息。

