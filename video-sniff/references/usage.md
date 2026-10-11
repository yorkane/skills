# video-sniff 使用手册

**默认方案：Playwright 驱动浏览器。** 用户没指定方案时一律走这条 —— 打开页面、真实渲染、监听网络，
不要绕过浏览器去直接抓取页面或凭猜测给地址（视频源常依赖 JS/MSE、动态签名、登录态，猜不出来）。

| 场景 | 用什么 |
|---|---|
| **未指定方案（默认）** | `vsdl --page <页面URL>`，或 `sniff.mjs --url <页面URL>` |
| 用户明确要求 CDP / 复用登录浏览器 | `sniff.mjs --cdp http://127.0.0.1:9222` + `cdp-chrome.sh` |
| 已经在用 playwright-cli 操作页面 | `sniff_pw.py --session 会话名` |
| 用户已给出完整媒体地址 | `vsdl --url` 直连 |

组件：sniff.mjs（嗅探）、sniff_pw.py（playwright-cli 会话适配）、vsdl（下载入口）、vsniff_lib/*.py（下载引擎）。

## 一、嗅探 sniff.mjs

```bash
node /home/aigc/.codex/skills/video-sniff/scripts/sniff.mjs \
  --url <页面URL> [--cdp http://127.0.0.1:9222] \
  [--headed] [--mobile] [--seconds 25] [--click-play] \
  [--user-data-dir DIR] [--out 报告.json]
```

- **未指定方案时默认用 Playwright 自起 headless chromium**（`--launch` 是同一默认值的显式写法）。
- 只有显式传 `--cdp` 才会附着调试端口的 Chrome；不再默认探测 9222，避免误附着到无关浏览器。
- `--seconds`：监听时长，默认 25 秒。视频源是懒加载或点播才拉流的站点，可加大到 40。
- 报告默认写到 `$VSNIFF_REPORT_DIR` 或 `/data/tmp/vsniff/<slug>-<ts>.json`。

报告关键字段：`pageTitle` / `ogTitle` / `ogDescription`（文件名来源）、`candidates[]`（每条含 `id` `kind` `url` `contentType` `contentLength` `referer` `score` `recommended` `hls{...}`）。

## 二、下载 vsdl

```bash
SKILL=/home/aigc/.codex/skills/video-sniff

# 从嗅探报告下载推荐项（或 --id c2 指定某条）
$SKILL/scripts/vsdl --report /data/tmp/vsniff/xxx.json

# 已知媒体地址直接下载
$SKILL/scripts/vsdl --url 'https://cdn/master.m3u8' [--kind hls|dash|file] \
  [--referer R] [--cookie C] [--user-agent UA] [--header 'K: V'] \
  [--title 标题] [--name 文件名] [--outdir /data/download/video] \
  [--quality best|1080|720|<height>] [--format original|mp4|mkv] [--json]

# 一步到位：嗅探 + 下载
$SKILL/scripts/vsdl --page 'https://站点/video/117/' [--launch | --cdp URL] \
  [--seconds 25] [--quality 1080] [--outdir DIR] [--json]
```

参数默认值：目录 `/data/download/video/`（`$VSNIFF_DOWNLOAD_DIR` 可覆盖）、清晰度 `best`、容器 `original`（保持原始编码，仅做必要封装：H.264+AAC→mp4，其它→mkv；音视频分离轨自动 `ffmpeg -c copy` 合并）。

输出（stdout 一行 JSON）：

```json
{"ok":true,"kind":"hls","title":"《高三爱情故事》第1集 AI成人短剧",
 "file":"/data/download/video/xxx.mp4","size":324564200,"duration":820.57,
 "resolution":"1280x720","vcodec":"h264","acodec":"aac",
 "encrypted":true,"segments":165,"elapsed":4.0,"mediaFormat":"mp4"}
```

失败时 `{"ok":false,"error":"..."}`，退出码非 0。

## 三、底层模块（需要精细控制时直接用）

```bash
cd $SKILL/scripts
# HLS：清晰度、并发、保留中间文件、限量分段（调试用）
python3 -m vsniff_lib.hls --url U --out DIR --name N [--quality 1080] [--concurrency 16] \
  [--referer R] [--cookie C] [--header 'K: V'] [--keep-ts] [--max-segments N] [--json]
# DASH
python3 -m vsniff_lib.dash --url U --out DIR [--quality best] [--keep-temp] [--json]
```

## 四、实测配方（huangguoai.com 这类短剧站）

```bash
$SKILL/scripts/vsdl --page 'https://huangguoai.com/video/117/' --launch --seconds 12 --json
```

该站要点：

- 播放器是 xgplayer + hls.js（`<video>` 是 blob: src），只能靠网络嗅探 + 页面内联 JSON 兜底；嗅探器两条路都走。
- m3u8/ts/key 的鉴权在 URL 的 `auth_key` 签名里，**有效期约 10 分钟**。所以「先嗅探、很久以后再下载」会 403；过期就重新跑一次 `--page`（会拿新签名）。
- 是 AES-128 且 **IV 显式写死**（全部分片共用一个 IV），不能用 media sequence 推导；hls.py 已按「显式 IV 优先」处理。
- 页面同时存在**预览片**（约 287 秒）与**正片**（820 秒）两条 m3u8；嗅探器用「播放列表总时长 vs 页面 video.duration」打分，正片排前。
- 音视频复用同一 ts（h264+aac），不需要合并。

参考：页面 HTML 的 JSON-LD `VideoObject.contentUrl` 与 `id="videoInitialData"` 的内联 JSON 里就含 m3u8（`&` 被转义成 `\u0026`），嗅探器会解析并反转义。

### 免浏览器批量下载（推荐，本会话实测）

该站的播放接口可直接用 curl 调，不需要浏览器：

```
GET https://huangguoai.com/api/videos/{id}/play?ep={N}
# data.video_url = m3u8（auth_key 约 10 分钟有效）
# data.duration / data.title / page_title = 校验与命名来源
# 集号不连续时该接口返回 msg=该集不存在或已下架；用二分探最大集号
```

批量：对每个 ep 调一次 play 拿新鲜 m3u8，紧接着交给 `vsdl --url ... --kind hls --referer 页面URL`，单集全程约 5 秒。

并发陷阱：多个 vsdl 并发时 `hls-<秒级时间戳>` 临时目录会撞车，产生串集/残缺产物。批量要么串行，要么完成后逐集 ffprobe 时长与 play 接口的 `duration` 比对（误差 <3s 才算过）。

校验例外：play 接口的 `duration` 偶尔与源站 playlist 不一致（站点元数据错误，实测 huangguoai /video/12/ ep7 标 279s、playlist 实际 241.5s 且以 ENDLIST 正常收尾）。重下一遍仍一样时，以 playlist 的分片总时长与 `#EXT-X-ENDLIST` 为准判定下载完整。

整站下载一条命令：`python3 $SKILL/scripts/hgsniff.py <video_id> [max_ep]`（自动取剧名、二分探最新集、串行下载、逐集时长校验，已存在的集自动跳过）。


## 五、playwright-cli 会话（已经在用 playwright-cli 时）

playwright-cli 与 sniff.mjs 是两个独立的浏览器进程，不能互相附着。如果页面已经在 playwright-cli 里打开，
用 `sniff_pw.py` 读取该会话已经产生的网络请求，生成同样的报告，再交给 `vsdl` 下载：

```bash
SKILL=/home/aigc/.codex/skills/video-sniff

# 1) 在会话里打开页面，并让视频真的开始播放（否则只有 HTML，没有媒体请求）
playwright-cli -s=mysess open 'https://站点/video/117/'
playwright-cli -s=mysess eval "() => { var v=document.querySelector('video'); if(v){v.muted=true; v.play();} return !!v; }"

# 2) 等几秒让分片请求产生，然后生成嗅探报告
sleep 8
python3 $SKILL/scripts/sniff_pw.py --session mysess --out /tmp/s.json

# 3) 下载（报告里已含 title/og/description 与推荐候选）
$SKILL/scripts/vsdl --report /tmp/s.json
$SKILL/scripts/vsdl --report /tmp/s.json --id c2      # 需要换一条候选时
```

要点与限制：

- `requests` 只能列出**已经发生**的请求：页面必须已经在播放（或点击过播放按钮），否则会报「未发现媒体候选」。
- 有播放列表（m3u8/mpd）时会自动丢弃 .ts/.m4s 分片候选，避免选中单个分片。
- 会话里的登录态天然被复用（同一浏览器），适合会员/需登录站点。
- 报告 `mode` 字段为 `playwright-cli:<会话名>`，便于区分来源。

实测（huangguoai.com/video/117/）：

```
[sniff_pw] 会话 hw：共解析 42 条请求
[sniff_pw] 页面: 《高三爱情故事》第1集 AI成人短剧 | 黄果短剧
  [c1] hls   score=100  https://yd-hls.tktjpm.cn/videos5/914fe6e9.../914fe6e9....m3u8?auth_key=...
[sniff_pw] 推荐: c1 ...
→ vsdl --report 产出 324564200 字节 / 820.57s / 1280x720 / h264+aac
```

## 六、CDP 附着已有浏览器

```bash
$SKILL/scripts/cdp-chrome.sh start [--port 9222] [--profile DIR] [--headed] [--url URL]
$SKILL/scripts/cdp-chrome.sh status
$SKILL/scripts/cdp-chrome.sh stop
node $SKILL/scripts/sniff.mjs --cdp http://127.0.0.1:9222 --url 'https://站点/页' --out /tmp/s.json
```

手动登录后（`--headed` 模式下人工操作一次）再嗅探，可复用登录态下载会员内容。playwright-cli 的 daemon 不是 CDP，若已有 playwright-cli 会话，嗅探器会自起 chromium（互不影响）。

## 七、排错

| 现象 | 处理 |
|---|---|
| candidates 为空 | `--seconds 40`；确认页面真的在播放（`--headed` 观察）；用 `--cdp` 附着到人工打开的浏览器 |
| 推荐项选到了预览片/广告 | 用 `--report` 查看候选 `score`/`note`，用 `--id c2` 指定 |
| 下载报 403/404 | 签名过期或防盗链：重跑嗅探拿新地址；或补 `--referer`/`--cookie` |
| 报「SAMPLE-AES 不支持」 | 该流用 SAMPLE-AES 加密，需 DRM 授权，不支持 |
| 产物无声 | 看日志是否有「检测到独立音频轨」；若站点音轨独立且时长对不上，换 `--quality` 或手动指定音轨（HLS 模块日志会打印所选音轨 NAME/LANGUAGE/时长） |
| 分片下载异常慢或体积异常 | 检查 playlist 是否用 `EXT-X-BYTERANGE`（同一 URL + 字节区间）；当前实现已支持 |

## 八、限制

- DRM（Widevine/PlayReady/FairPlay）与 SAMPLE-AES 加密不支持。
- 直播（无 `#EXT-X-ENDLIST` 且持续增长）只下载当前可见分段，不是完整回放。
- DASH 只支持 static MPD（多 Period 只取第一个有内容的 Period）。
- 依赖浏览器能加载页面；纯 API 返回的媒体（无页面）用 `--url` 直连模式。
