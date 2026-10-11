#!/usr/bin/env python3
'''嗅探适配层：把 playwright-cli 会话已产生的网络请求，转成标准嗅探报告。

用途：视频在 playwright-cli 驱动的浏览器里播放时（而不是由 sniff.mjs 自己起浏览器），
读取该会话的请求列表，生成与 sniff.mjs 一致的报告，可直接交给 vsdl --report 下载。

用法：
  python3 sniff_pw.py --session NAME [--url PAGE] [--out REPORT.json] [--top 20] [--json]

提示：requests 命令只能列出已发生的请求；请先在会话里打开页面并让视频开始播放，再运行本工具。
'''

import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vsniff_lib import common  # noqa: E402

PLAYWRIGHT_CLI = os.environ.get('PLAYWRIGHT_CLI', 'playwright-cli')

# 媒体判定集合（与 sniff.mjs 保持一致，来源 cat-catch/js/init.js）
MEDIA_EXTS = {
    'flv', 'hlv', 'f4v', 'mp4', 'mp3', 'wma', 'wav', 'm4a', 'ts', 'webm', 'ogg', 'ogv',
    'acc', 'mov', 'mkv', 'm4s', 'mpeg', 'avi', 'wmv', 'asf', 'movie', 'divx', 'mpeg4',
    'vid', 'aac', 'weba', 'opus', 'm3u8', 'm3u', 'mpd',
}
MEDIA_TYPES = (
    'audio/', 'video/',
    'application/ogg', 'application/vnd.apple.mpegurl', 'application/x-mpegurl',
    'application/mpegurl', 'application/octet-stream-m3u8',
    'application/dash+xml', 'application/m4s',
)
SEGMENT_EXTS = {'ts', 'm4s', 'acc'}
AUDIO_EXTS = {'mp3', 'm4a', 'aac', 'opus', 'weba', 'wma', 'wav'}
AD_PATTERN = re.compile(r'doubleclick|googlesyndication|analytics|beacon|tracker|adsrvr|flashb|/ad/', re.I)

META_JS = (
    '() => JSON.stringify({t: document.title, u: location.href, '
    "v: (document.querySelector('video')||{}).duration||null, "
    "metas: [].slice.call(document.querySelectorAll('meta')).slice(0, 80).map("
    "function(m){return [m.getAttribute('property')||m.getAttribute('name'), m.content];})})"
)


def run_cli(args, timeout=90):
    '''调用 playwright-cli，合并 stderr 返回文本。'''
    proc = subprocess.run([PLAYWRIGHT_CLI] + args, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)
    return proc.stdout.decode('utf-8', 'replace')


def parse_requests(text):
    '''解析 requests 列表：形如 "44. [GET] url => [206]"。'''
    rows = []
    for line in text.splitlines():
        m = re.match(r'(\d+)\.\s*\[([A-Z]+)\]\s*(\S+)\s*=>\s*(.*)$', line)
        if not m:
            continue
        rows.append({
            'index': int(m.group(1)),
            'method': m.group(2),
            'url': m.group(3),
            'statusText': m.group(4).strip(),
        })
    return rows


def parse_detail(text):
    '''解析 request <n> 详情：mimeType / referer / status。'''
    out = {}
    m = re.search(r'mimeType:\s*(\S+)', text, re.M)
    if m:
        out['contentType'] = m.group(1)
    m = re.search(r'referer:\s*(\S+)', text, re.M)
    if m:
        out['referer'] = m.group(1)
    m = re.search(r'status:\s*\[(\d+)\]', text)
    if m:
        out['status'] = int(m.group(1))
    return out


def ext_of(url):
    path = url.split('?', 1)[0].split('#', 1)[0]
    m = re.search(r'\.([A-Za-z0-9]{2,5})$', path)
    return m.group(1).lower() if m else ''


def classify(url, content_type):
    '''返回 hls / dash / file / None。'''
    ct = (content_type or '').lower()
    low = url.lower()
    if '.m3u8' in low or '.m3u' in low or 'mpegurl' in ct:
        return 'hls'
    if '.mpd' in low or 'dash+xml' in ct:
        return 'dash'
    for t in MEDIA_TYPES:
        if t in ct:
            return 'file'
    if ext_of(url) in MEDIA_EXTS:
        return 'file'
    return None


def score_of(kind, url, content_type, content_length):
    '''打分（与 sniff.mjs 规则一致的精简版）。'''
    score = 100 if kind == 'hls' else (70 if kind == 'dash' else 50)
    ext = ext_of(url)
    if ext in AUDIO_EXTS:
        score -= 40
    if kind == 'file' and ext in SEGMENT_EXTS:
        score -= 30
    if content_length:
        if content_length > 50 * 1024 * 1024:
            score += 10
        elif content_length > 10 * 1024 * 1024:
            score += 5
        elif content_length < 100 * 1024:
            score -= 30
    if AD_PATTERN.search(url):
        score -= 50
    return score


def main():
    ap = argparse.ArgumentParser(description='从 playwright-cli 会话生成嗅探报告')
    ap.add_argument('--session', required=True, help='playwright-cli 会话名（对应 -s=NAME）')
    ap.add_argument('--url', default=None, help='页面 URL（缺省从会话读取）')
    ap.add_argument('--out', default=None, help='报告输出路径')
    ap.add_argument('--top', type=int, default=20, help='最多补查多少条请求详情')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    sess = ['-s=' + args.session]
    common.ensure_dir(common.TMP_DIR)

    # 1) 页面元数据
    meta = {}
    meta_path = os.path.join(common.TMP_DIR, 'pw-meta-%d.json' % int(time.time()))
    try:
        run_cli(sess + ['eval', META_JS, '--filename', meta_path], timeout=60)
        with open(meta_path, 'r', encoding='utf-8') as fh:
            meta = json.loads(json.loads(fh.read()))
    except Exception as exc:  # noqa: BLE001
        common.log('[sniff_pw] 读取页面元数据失败（继续）: %s' % exc)

    page_url = args.url or meta.get('u') or ''
    if not page_url:
        common.log('[sniff_pw] 无法确定页面 URL，请显式传 --url')
        return 2

    # 2) 请求列表
    listing = run_cli(sess + ['requests'])
    rows = parse_requests(listing)
    common.log('[sniff_pw] 会话 %s：共解析 %d 条请求' % (args.session, len(rows)))

    seen = {}
    for row in rows:
        url = row['url']
        if url.startswith('data:') or url.startswith('blob:'):
            continue
        if not classify(url, None):
            continue
        if url in seen:
            continue
        seen[url] = dict(row)

    items = list(seen.values())
    for it in items[: args.top]:
        try:
            detail = parse_detail(run_cli(sess + ['request', str(it['index'])], timeout=45))
            for k, v in detail.items():
                if v is not None:
                    it[k] = v
            kind2 = classify(it['url'], it.get('contentType'))
            if kind2:
                it['kind'] = kind2
        except Exception as exc:  # noqa: BLE001
            common.log('[sniff_pw] 请求 #%s 详情读取失败: %s' % (it['index'], exc))

    # 3) 有播放列表时丢弃分片候选
    for it in items:
        it['kind'] = it.get('kind') or classify(it['url'], it.get('contentType'))
    if any(i['kind'] in ('hls', 'dash') for i in items):
        items = [i for i in items if not (i['kind'] == 'file' and ext_of(i['url']) in SEGMENT_EXTS)]

    cands = []
    for it in items:
        cands.append({
            'kind': it['kind'],
            'url': it['url'],
            'contentType': it.get('contentType'),
            'contentLength': it.get('contentLength'),
            'ext': ext_of(it['url']) or None,
            'referer': it.get('referer') or page_url,
            'score': score_of(it['kind'], it['url'], it.get('contentType'), it.get('contentLength')),
            'note': '来自 playwright-cli 会话 #%s' % it['index'],
        })
    cands.sort(key=lambda c: (-c['score'], c['url']))
    for i, c in enumerate(cands, 1):
        c['id'] = 'c%d' % i
        c['recommended'] = (i == 1 and c['score'] > 0)

    dur = meta.get('v')
    try:
        dur = float(dur) if dur else None
    except (TypeError, ValueError):
        dur = None

    # 4) 从 meta 标签里补充 og / description
    og_title = None
    desc = None
    for name, content in (meta.get('metas') or []):
        if not content:
            continue
        low = (name or '').lower()
        if low in ('og:title', 'twitter:title') and not og_title:
            og_title = content
        if low in ('description', 'og:description') and not desc:
            desc = content

    report_dir = os.environ.get('VSNIFF_REPORT_DIR', common.TMP_DIR)
    slug = re.sub(r'[^\w.-]+', '_', page_url)[:60]
    report_path = args.out or os.path.join(report_dir, 'pw-%s-%d.json' % (slug, int(time.time())))
    report = {
        'pageUrl': page_url,
        'finalUrl': page_url,
        'pageTitle': meta.get('t'),
        'ogTitle': og_title,
        'ogDescription': desc,
        'description': desc,
        'durationHint': dur,
        'cookies': None,
        'userAgent': None,
        'reportPath': report_path,
        'mode': 'playwright-cli:' + args.session,
        'elapsedSec': 0,
        'candidates': cands,
    }
    common.ensure_dir(os.path.dirname(report_path))
    with open(report_path, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    common.log('[sniff_pw] 页面: %s' % (meta.get('t') or page_url))
    for c in cands[:8]:
        common.log('  [%s] %-5s score=%-4s %s' % (c['id'], c['kind'], c['score'], c['url'][:100]))
    if cands:
        common.log('[sniff_pw] 推荐: %s %s' % (cands[0]['id'], cands[0]['url'][:120]))
    else:
        common.log('[sniff_pw] 未发现媒体候选：请先在会话里让视频开始播放，再重跑本工具')
    common.log('[sniff_pw] 报告: %s' % report_path)
    common.emit(report)
    return 0 if cands else 1


if __name__ == '__main__':
    sys.exit(main())

