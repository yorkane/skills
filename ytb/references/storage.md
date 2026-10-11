# 分析素材存储规范：视频 / 声音 / 字幕

目标：让每一个被下载的视频，都能被分析管线无歧义地找到三要素，
且各要素之间能通过**视频 ID + 时间轴**对齐。

## 1. 目录布局

```
/data/app/metube/downloads/
└── <folder>/
    ├── <id> - <title>.mp4          # 视频（原始素材）
    ├── <id> - <title>.info.json    # 元数据（yt-dlp 权威来源）
    ├── <id> - <title>.jpg          # 缩略图
    ├── <id> - <title>.m4a          # 音频（仅 audio 模式）
    └── <id> - <title>.srt / .vtt   # 平台字幕（若有）
```

分析侧处理产物建议写到**独立目录**（不要混在 downloads/ 里，
避免被 MeTube UI 的"清理已完成"误删）：

```
/data/app/metube/analysis/<video_id>/
├── audio.wav          # 16kHz mono，ASR 输入（从视频抽取）
├── asr.json           # ASR 带时间轴段落 [{start, end, text, spk?}]
├── subs.srt           # 最终字幕（平台字幕优先，否则 ASR/OCR 生成）
├── frames/            # 抽帧（scene 检测或固定间隔）
├── ocr.json           # 硬字幕 OCR 结果（可选）
└── script.json        # 分析管线最终产物（结构化剧本/摘要）
```

## 2. 三要素获取方式

### 视频
- 下载格式建议 `quality=best + format=any`（保留最佳画质，后续可转码）。
- 磁盘敏感时可用 `format=mp4` 限制容器。
- 不要开 `DELETE_FILE_ON_TRASHCAN`（当前已设 false）——UI 清理不删文件。

### 声音
两种来源，按场景选：
1. **分析时需要原始音轨**：视频模式下载后本地 `ffmpeg -i v.mp4 -vn -ac 1 -ar 16000 audio.wav`；
2. **只要音频**（播客/纯听）：`download_type=audio`（mp3/opus 等）。
   注意 MeTube 的队列按 URL 去重——同一视频先下 video 再下 audio 会被判 "Already in queue"，
   需要两种产物时用方案 1 或从 video 提取。

ASR 参考（本机已验证）：Qwen3-ASR-1.7B @ 127.0.0.1:17003
（`/v1/audio/transcriptions`，multipart，key `devideo2026asrkey`，
输出 `verbose_json` 带 segments）。CPU FunASR 亦可（RTF 0.054）。

### 字幕（优先级）
1. **平台字幕**：下载时 `subtitle_language=all, subtitle_mode=prefer_manual`；
   得到 `.srt/.vtt/.json3` 则直接用（免费、准时间轴）。
2. **ASR 字幕**：音频 → Qwen3-ASR/FunASR → `asr.json` → 转 srt。
   ASR 抓画外音与无字幕对白。
3. **OCR 字幕**：1fps 抽帧 → RapidOCR → 底部区域过滤（y>0.55~0.6 相对高度）→ 去重。
   抓烧录硬字幕、双语、方言配音场景。
4. **融合**：ASR + OCR 按时间轴并集，实测比单源提升约 30%（误杀2：0.526→0.684）。

## 3. 增量发现（分析侧如何知道"有新视频"）

推荐轮询 `state/completed.json`（schema: `{schema_version, items:[{key, info}]}`）：
- `info.status == "finished"` 且 `info.filename` 存在 → 新素材就绪；
- 用 `info.id` 做幂等键，记录已处理集合避免重复分析；
- 失败项 `status == "error"`，可读 `error` 字段排障后 `POST /retry`。

也可用 Socket.IO 监听 `completed` 事件做到实时触发。

## 4. 与 devideo 分析管线的对接（预留）

devideo 的感知层（抽帧/ASR/OCR/Vision）全部带**内容指纹缓存**
（`video_fingerprint = 头部64KB MD5 + 大小 + 时长`），同一视频只算一次。
对接方式：把 `downloads/<folder>/<id> - <title>.mp4` 作为输入喂给
`scripts/process_video.py <video_path> [out_dir]` 即可，
输出结构化剧本到 `out_dir/script.json`。本服务不侵入 devideo，
只负责把素材按上述目录规范备齐。

