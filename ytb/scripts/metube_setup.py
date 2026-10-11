#!/usr/bin/env python3
"""MeTube 标准环境部署器（本地 / 远程）。

生成符合分析下载标准的 metube 部署包并启动：
  - 优先 1080P（format_sort + quality=1080）
  - 按 %(uploader,channel)s/ 分目录，文件名为 "<title> [<id>].<ext>"
  - writeinfojson + writethumbnail + 中英文字幕（含自动字幕）
  - windowsfilenames 防止特殊标题导致文件/HTTP 访问问题
  - download_archive 防重复下载
  - cookies 热加载支持

用法:
  metube_setup.py local [--dir /data/app/metube] [--port 8099] [--no-start]
  metube_setup.py remote --host user@ip [--dir /data/app/metube] [--port 8099]
  metube_setup.py bundle --out /tmp/metube-bundle   # 只生成部署包
"""
import argparse, json, os, socket, subprocess, sys, textwrap

STANDARD_YTDL_OPTIONS = {
    # --- 画质：优先 1080P + 强制优先 HEVC/VP9（兼容性优于 AV1）---
    # vcodec 命中组把 h265/hevc/vp9 抬到候选最前；AV1/H264 落入未命中档按码率决胜，
    # 同分辨率 H264 码率高于 AV1，故实际偏好顺序为 HEVC/VP9 > H264 > AV1。
    # 无 HEVC/VP9 时自动回落 H264，不报错。切勿在此放全局 "format"，
    # 否则会覆盖 MeTube 按 codec/quality 拼出的选择器并打断 --audio 音频下载。
    "format_sort": ["res:1080", "vcodec:hev|hevc|h265|vp0?9", "ext:mp4:m4a"],
    "merge_output_format": "mp4",
    "final_ext": "mp4",
    "keepvideo": False,
    # --- 元数据 ---
    "writeinfojson": True,
    "clean_infojson": True,
    "writethumbnail": True,
    "updatetime": False,
    # --- 字幕：默认中英文（人工 + 自动），排除弹幕 ---
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitlesformat": "srt/vtt/ass/best",
    "subtitleslangs": ["zh-Hans", "zh-Hant", "en", "-live_chat"],
    # --- 文件名：保留中文，替换非法字符，防乱码/防HTTP失效 ---
    "windowsfilenames": True,
    "restrictfilenames": False,
    # --- 性能与健壮性 ---
    "concurrent_fragment_downloads": 10,
    "retries": 5,
    "fragment_retries": 5,
    "download_archive": "/archive/downloaded.txt",
    "playlist_items": "1-50",
    # --- 后处理：嵌入字幕/章节，统一权限 ---
    "postprocessors": [
        {"key": "Exec", "exec_cmd": "chmod 0664", "when": "after_move"},
        {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False},
        {"key": "FFmpegMetadata", "add_chapters": True},
    ],
}

# 命名标准：按上传者分目录；标题保留可读性，尾部带稳定视频ID
UPLOADER_TMPL = "%(uploader,channel|NA)s/%(title)s [%(id)s].%(ext)s"

COMPOSE_TEMPLATE = textwrap.dedent("""    services:
      metube:
        image: ghcr.io/alexta69/metube
        container_name: metube
        restart: unless-stopped
        ports:
          - "{port}:8081"
        environment:
          - PUID=1000
          - PGID=1000
          - DOWNLOAD_DIR=/downloads
          - STATE_DIR=/state
          - TEMP_DIR=/tmp/metube-tmp
          - YTDL_OPTIONS_FILE=/config/ytdl_options.json
          - MAX_CONCURRENT_DOWNLOADS=2
          - DELETE_FILE_ON_TRASHCAN=false
          - CUSTOM_DIRS=true
          - CREATE_CUSTOM_DIRS=true
          - CORS_ALLOWED_ORIGINS=*
          - LOGLEVEL=INFO
          - OUTPUT_TEMPLATE={tmpl}
          - OUTPUT_TEMPLATE_PLAYLIST={tmpl}
          - OUTPUT_TEMPLATE_CHANNEL={tmpl}
        volumes:
          - ./downloads:/downloads
          - ./state:/state
          - ./config:/config:ro
          - ./archive:/archive
    """)

def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def metube_owns_port(port):
    """端口是否已被(即将被我们替换的)同名 metube 容器占用"""
    r = subprocess.run(
        f"docker ps --filter publish={port} --format '{{{{.Names}}}}'",
        shell=True, capture_output=True, text=True)
    names = r.stdout.split()
    return 'metube' in names

def gen_bundle(base_dir, port):
    os.makedirs(base_dir, exist_ok=True)
    for sub in ('downloads', 'state', 'archive'):
        os.makedirs(os.path.join(base_dir, sub), exist_ok=True)
    cfg_dir = os.path.join(base_dir, 'config')
    os.makedirs(cfg_dir, exist_ok=True)

    opts_path = os.path.join(cfg_dir, 'ytdl_options.json')
    existing = {}
    if os.path.exists(opts_path):
        try:
            existing = json.load(open(opts_path))
        except Exception:
            existing = {}
    merged = dict(STANDARD_YTDL_OPTIONS)
    # 保留用户自定义项（如 cookiefile / proxy）
    for k, v in existing.items():
        if k not in merged or k in ('cookiefile', 'proxy', 'username', 'password'):
            merged[k] = v
    json.dump(merged, open(opts_path, 'w'), ensure_ascii=False, indent=2)
    print(f'[ok] {opts_path} ({len(merged)} 项)')

    compose_path = os.path.join(base_dir, 'docker-compose.yml')
    open(compose_path, 'w').write(COMPOSE_TEMPLATE.format(port=port, tmpl=UPLOADER_TMPL))
    print(f'[ok] {compose_path} (端口 {port})')

    # cookies 占位说明（真正文件由 metube_cookies.py 写入）
    readme = os.path.join(cfg_dir, 'README.txt')
    if not os.path.exists(readme):
        open(readme, 'w').write('cookies.txt 由 ytb skill 的 metube_cookies.py 管理，勿手工编辑。\n')
    return base_dir

def sh(cmd, check=True):
    print(f'$ {cmd}')
    r = subprocess.run(cmd, shell=True)
    if check and r.returncode != 0:
        sys.exit(f'命令失败: {cmd}')

def local(args):
    base = args.dir
    port = args.port
    if not port_free(port) and not metube_owns_port(port):
        print(f'端口 {port} 被占用，自动探测...')
        for p in range(8090, 8200):
            if port_free(p):
                port = p
                print(f'使用端口 {p}')
                break
        else:
            sys.exit('无可用端口')
    gen_bundle(base, port)
    if args.no_start:
        print('--no-start: 跳过启动')
        return
    sh(f'cd {base} && docker compose pull')
    sh(f'cd {base} && docker compose up -d')
    sh(f'sleep 5 && curl -s -o /dev/null -w "健康检查: %{{http_code}}\n" http://localhost:{port}/')
    print(f'\n完成。UI: http://localhost:{port}/  下载目录: {base}/downloads/')

def remote(args):
    if not args.host:
        sys.exit('remote 模式需要 --host user@ip')
    base = args.dir
    port = args.port
    gen_bundle('/tmp/metube-setup-bundle', port)
    sh(f'ssh {args.host} "mkdir -p {base}"')
    sh(f'scp -r /tmp/metube-setup-bundle/docker-compose.yml /tmp/metube-setup-bundle/config {args.host}:{base}/')
    sh(f'ssh {args.host} "mkdir -p {base}/downloads {base}/state {base}/archive && cd {base} && docker compose pull && docker compose up -d"')
    print(f'\n远程部署完成（需宿主机间免密 ssh）。UI: http://{args.host}:{port}/')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='mode', required=True)
    for name in ('local', 'remote', 'bundle'):
        p = sub.add_parser(name)
        p.add_argument('--dir', default='/data/app/metube')
        p.add_argument('--port', type=int, default=8099)
        p.add_argument('--host', help='remote 模式: user@ip')
        p.add_argument('--out', default='/tmp/metube-bundle', help='bundle 输出目录')
        p.add_argument('--no-start', action='store_true')
    args = ap.parse_args()
    if args.mode == 'local':
        local(args)
    elif args.mode == 'remote':
        remote(args)
    else:
        gen_bundle(args.out, args.port)
        print(f'部署包已生成: {args.out}')

if __name__ == '__main__':
    main()
