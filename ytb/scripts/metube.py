#!/usr/bin/env python3
"""MeTube (yt-dlp) 下载服务 CLI 助手。

服务: http://localhost:8099 (容器: metube, /data/app/metube)

用法:
  metube.py health                          # 服务状态
  metube.py add <url> [选项]                 # 单次下载
  metube.py subscribe <url> [选项]           # 订阅频道/播放列表(监控)
  metube.py subs                            # 列出订阅
  metube.py completed [--since-sec N]       # 已完成下载(增量发现)
  metube.py queue                           # 队列状态

add/subscribe 选项:
  --audio            只下载音频 (mp3)
  --folder DIR       下载子目录 (相对 downloads/; 默认按 uploader/ 自动分目录)
  --quality Q        画质: best(默认,配合format_sort优先1080P) / 1080(严格≤1080P) / 720 等
  --interval MIN     订阅检查间隔分钟 (默认 60)
  --regex RE         订阅标题过滤正则

环境变量:
  METUBE_URL    服务地址 (默认 http://localhost:8099)
  METUBE_STATE  state 目录 (默认 /data/app/metube/state)
"""
import argparse, json, os, sys, urllib.request, urllib.error

BASE = os.environ.get('METUBE_URL', 'http://localhost:8099')
STATE_DIR = os.environ.get('METUBE_STATE', '/data/app/metube/state')
DL_DIR = os.environ.get('METUBE_DOWNLOADS', '/data/app/metube/downloads')

def api(path, body=None):
    req = urllib.request.Request(BASE + path)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, data=data, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.URLError as e:
        print(f'[error] 无法连接 {BASE}: {e}', file=sys.stderr)
        sys.exit(2)

def build_opts(args, url):
    o = {'url': url, 'auto_start': True}
    q = getattr(args, 'quality', None) or 'best'
    if args.audio:
        o.update(download_type='audio', format='mp3', quality=q)
    else:
        o.update(download_type='video', format='any', quality=q)
    if args.folder:
        o['folder'] = args.folder
    return o

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['health','add','subscribe','subs','completed','queue'])
    ap.add_argument('url', nargs='?')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--folder')
    ap.add_argument('--quality', default='best')
    ap.add_argument('--interval', type=int, default=60)
    ap.add_argument('--regex', default='')
    ap.add_argument('--since-sec', type=int, default=0, help='只列出最近 N 秒完成的')
    args = ap.parse_args()

    if args.cmd == 'health':
        try:
            info = api('/presets')
            print(json.dumps({'base': BASE, 'ok': True, 'presets': info.get('presets')}, ensure_ascii=False))
        except SystemExit:
            print(json.dumps({'base': BASE, 'ok': False}, ensure_ascii=False))
    elif args.cmd == 'add':
        if not args.url: sys.exit('需要 URL')
        print(json.dumps(api('/add', build_opts(args, args.url)), ensure_ascii=False))
    elif args.cmd == 'subscribe':
        if not args.url: sys.exit('需要频道/播放列表 URL')
        o = build_opts(args, args.url)
        o['check_interval_minutes'] = args.interval
        if args.regex: o['title_regex'] = args.regex
        print(json.dumps(api('/subscribe', o), ensure_ascii=False))
    elif args.cmd == 'subs':
        subs = json.load(open(f'{STATE_DIR}/subscriptions.json')).get('items', [])
        for s in subs:
            print(f"{s['id'][:8]}  每{s['check_interval_minutes']}min  folder={s.get('folder') or '-'}  seen={s.get('seen_count')}  err={s.get('error')}  {s['name']}")
    elif args.cmd == 'completed':
        import time
        done = json.load(open(f'{STATE_DIR}/completed.json'))
        now = time.time()
        for it in done.get('items', []):
            info = it.get('info', {})
            ts = info.get('timestamp', 0) / 1e9
            if args.since_sec and now - ts > args.since_sec: continue
            fn = info.get('filename', '?')
            folder = info.get('folder') or ''
            print(f"{info.get('id','?')}	{info.get('status')}	{os.path.join(DL_DIR, folder, fn)}")
    elif args.cmd == 'queue':
        q = json.load(open(f'{STATE_DIR}/queue.json'))
        items = q.get('items', []) if isinstance(q, dict) else q
        print(f'{len(items)} 项在队列')
        for it in items[:20]:
            info = it.get('info', {})
            print(f"  {info.get('status','?'):10s} {info.get('title','?')[:60]}")

if __name__ == '__main__':
    main()
