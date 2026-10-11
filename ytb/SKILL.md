---
name: ytb
description: "通过本地 MeTube 服务（yt-dlp Web 化）下载与监控 YouTube / Bilibili 等平台的视频、音频，为本地视频分析准备素材。当用户要求下载视频、订阅/监控频道、准备视频分析素材（视频/音频/字幕）、部署视频下载服务、或询问本机视频下载服务时使用。不适用于直接的转码、剪辑等后期处理任务。"
metadata:
  short-description: MeTube/yt-dlp 视频下载与频道监控，为视频分析备料
---

# Video Monitor

本地视频下载服务 **MeTube**（yt-dlp 的 Web UI + API）。用于下载和监控
YouTube / Bilibili 等平台的视频，按统一标准产出分析素材：**视频、音频、字幕、元数据**。

## 部署标准环境

```bash
SETUP=/home/aigc/.codex/skills/ytb/scripts/metube_setup.py
python3 $SETUP local                              # 本机部署（默认 /data/app/metube:8099）
python3 $SETUP local --dir /data/app/metube --port 8099
python3 $SETUP remote --host user@ip              # 远程部署（需免密 ssh）
python3 $SETUP bundle --out /tmp/metube-bundle    # 只生成部署包
```

部署脚本生成符合下载标准的完整配置（幂等，重复运行安全）：

- 优先 **1080P + HEVC/VP9**：`format_sort: ["res:1080", "vcodec:hev|hevc|h265|vp0?9", "ext:mp4:m4a"]`，
  强制优先 **H.265/HEVC 或 VP9**（编码兼容性优于 AV1，播放器/剪辑工具支持更广）；
  AV1/H264 落入未命中档按码率决胜，实际偏好为 HEVC/VP9 > H264 > AV1；
  源无 HEVC/VP9 时自动回落 H264，不报错。提交任务时用 `quality=1080` 严格限高。
  **切勿在全局 `ytdl_options.json` 里放 `format` 键**——它会覆盖 MeTube 按
  codec/quality 拼出的格式选择器，连带打断 `--audio` 音频下载。
- 目录结构 `<uploader>/<title> [<id>].mp4`（按 UP 主/频道分目录）
- 每个视频附 `.info.json`（元数据）+ `.jpg`（缩略图）+ 字幕
- 字幕默认 **中英双语**（人工 + 自动字幕，排除弹幕 `-live_chat`）
- `windowsfilenames: true`：特殊标题字符被规范化，防止乱码与 HTTP 访问失效
- `download_archive`：重复提交自动跳过，订阅高频轮询不重复下载
- `config/ytdl_options.json` 热加载：改文件即生效，无需重启

**本机现役实例**：容器 `metube`，端口 `8099`，目录 `/data/app/metube`。

## 快速操作

CLI 助手：

```bash
MT=/home/aigc/.codex/skills/ytb/scripts/metube.py
python3 $MT health                     # 服务状态
python3 $MT add <url> [--folder DIR]   # 下载视频（1080P 标准）
python3 $MT add <url> --audio          # 仅音频 (mp3)
python3 $MT subscribe <频道或播放列表url> --interval 60 [--regex RE]
python3 $MT subs                       # 查看订阅
python3 $MT completed                  # 已完成列表
python3 $MT queue                      # 进行中队列
```

HEVC/VP9 偏好：靠全局 `format_sort` 的 `vcodec:hev|hevc|h265|vp0?9` 实现，对所有
`add`/`subscribe` 自动生效，**不需要**传 `codec` 参数。MeTube 的 `codec` 字段
只能单选（h264/h265/av1/vp9），无法表达"HEVC 或 VP9"，不要用 `--codec` 去做组合。

1080P 偏好：CLI 默认 `quality=best`，配合全局 `format_sort` 已优先 1080P；
若需严格限高，直接调 API 传 `"quality": "1080"`。

## Cookie 管理（高清/登录态内容）

**主动询问场景**：用户要 1080P 高码率/4K/大会员内容、遇到 412 风控、
下载充电/会员视频、或明确说"高清/登录/大会员/4K"。

```bash
CK=/home/aigc/.codex/skills/ytb/scripts/metube_cookies.py
python3 $CK --set "SESSDATA值"                    # 方式1: 纯 SESSDATA
python3 $CK --set "SESSDATA=xx; bili_jct=yy"     # 方式2: 完整字符串
python3 $CK --set /path/cookies.txt              # 方式3: Netscape 文件
python3 $CK --set /path/cookies.json             # 方式4: Cookie-Editor JSON
python3 $CK --status                             # 查看配置与剩余有效期
python3 $CK --check                              # 调 B 站 API 验证登录态
python3 $CK --remove                             # 移除
```

向用户索要的话术：

> 下载高清/登录态内容需要 B 站 Cookie。请提供以下任一：
> 1. 登录 bilibili.com → F12 → Application → Cookies → 复制 `SESSDATA` 的值
> 2. 完整 Cookie 字符串（同上位置全选）
> 3. 浏览器扩展 "Get cookies.txt LOCALLY" 或 "Cookie-Editor" 导出的文件

脚本自动：识别格式 → 写 `/config/cookies.txt`(Netscape) → 启用 `cookiefile` →
热加载 → 调 B 站 API 验证。检测到过期会明确提示重新获取。

## 关键事实（实测，勿重复踩坑）

- **平台字幕大多拿不到**（B 站公开视频无外挂字幕），分析用字幕靠本地 ASR/OCR 生成。
  全局配置仍开着字幕下载——有则白赚（如 YouTube 自动字幕）。
- 同一 URL 二次 `/add` 返回 "Already in queue"（URL 级去重 + download_archive 双重保护）。
- 订阅只接受频道/播放列表 URL；首次订阅把历史标记为 seen，之后只追新增。
- B 站偶发 412 风控是瞬态的，重试即过；持续出现则配置 cookies。
- `completed.json` 里 `info.id` 是幂等键；`status=error` 的项可 `POST /retry`。
- YouTube 直连在本机网络环境不通：需 `"proxy"` 或 `"cookiefile"` 配置后再测。

## 何时读参考文档

- 方案设计、API 参数、监控频率、cookies/代理原理 → [references/design.md](references/design.md)
- 三要素（视频/声音/字幕）存储规范、增量发现、与分析管线对接 → [references/storage.md](references/storage.md)

## 运维

- 管理：`cd /data/app/metube && docker compose up -d / down / logs -f`
- 健康：`curl -s -o /dev/null -w '%{http_code}' http://localhost:8099/` → 200
- 改 yt-dlp 全局选项：编辑 `/data/app/metube/config/ytdl_options.json`（热加载）
- 升级：`docker compose pull && docker compose up -d`
- 状态文件：`/data/app/metube/state/{queue,completed,subscriptions}.json`
