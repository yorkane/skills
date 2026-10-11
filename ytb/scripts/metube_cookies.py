#!/usr/bin/env python3
"""B 站 / YouTube cookies 配置与过期检测（MeTube/yt-dlp）。

功能:
  --set        配置 cookies（写文件 + 启用热加载）
  --status     查看配置与有效期
  --check      验证 cookies 是否有效（调 B 站 API 实测登录态）
  --remove     移除 cookie 配置

输入格式（自动识别）:
  1. 纯 SESSDATA 值:            --set "abcdef123..."
  2. 浏览器复制的字符串:         --set "SESSDATA=xxx; bili_jct=yyy; DedeUserID=zzz"
  3. Netscape cookies.txt 路径:  --set /path/to/cookies.txt
  4. JSON 导出（Cookie-Editor）: --set /path/to/cookies.json

B 站获取方法:
  登录 bilibili.com → F12 → Application → Cookies → bilibili.com
  关键值: SESSDATA (必需), bili_jct (推荐), DedeUserID (可选)
  或安装扩展 "Get cookies.txt LOCALLY" / "Cookie-Editor" 一键导出。
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

CONFIG_DIR = os.environ.get('METUBE_CONFIG_DIR', '/data/app/metube/config')
COOKIES_FILE = os.path.join(CONFIG_DIR, 'cookies.txt')
OPTIONS_FILE = os.path.join(CONFIG_DIR, 'ytdl_options.json')
NETSCAPE_HEADER = "# Netscape HTTP Cookie File\n# https://curl.se/docs/http-cookies.html\n"

# ── 格式解析 ──────────────────────────────────────────────────────

def looks_like_sessdata(s):
    return bool(s) and '=' not in s and ';' not in s and len(s) >= 10

def parse_cookie_string(s):
    pairs = []
    for part in s.split(';'):
        part = part.strip()
        if '=' in part:
            k, v = part.split('=', 1)
            if k.strip() and v.strip():
                pairs.append((k.strip(), v.strip()))
    return pairs

def parse_json_export(path):
    """Cookie-Editor 扩展导出格式: [{name, value, ...}] 或 {cookies: [...]}"""
    data = json.load(open(path))
    if isinstance(data, dict) and 'cookies' in data:
        data = data['cookies']
    pairs = []
    for c in data:
        if isinstance(c, dict) and c.get('name') and c.get('value') is not None:
            pairs.append((c['name'], c['value']))
    return pairs

def parse_netscape_file(path):
    """读取已有 Netscape 文件，归一化为 6 元组 (domain, path, secure, expires, name, value)。
    标准 curl 格式为 7 列（第 2 列是 include_subdomains），这里丢弃该列以统一内部表示。"""
    entries = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            entries.append((parts[0], parts[2], parts[3], parts[4], parts[5], parts[6]))
        elif len(parts) == 6:
            entries.append(tuple(parts))
    return entries

def write_netscape(entries):
    """entries: [(domain, path, secure, expires, name, value)]"""
    lines = [NETSCAPE_HEADER]
    for dom, path, secure, exp, name, value in entries:
        lines.append(f"{dom}\t{path}\t{secure}\t{exp}\t{name}\t{value}\n")
    with open(COOKIES_FILE, 'w') as f:
        f.writelines(lines)
    os.chmod(COOKIES_FILE, 0o600)

# ── 有效性检测 ──────────────────────────────────────────────────────

def check_bilibili_login():
    """用已配置的 cookies 调 B 站导航接口，验证登录态。"""
    if not os.path.exists(COOKIES_FILE):
        return False, '未配置 cookies'
    entries = parse_netscape_file(COOKIES_FILE)
    cookie_str = '; '.join(f'{e[4]}={e[5]}' for e in entries)
    # 文件层面检查过期
    now = time.time()
    for e in entries:
        if e[4] == 'SESSDATA' and e[3].isdigit() and int(e[3]) < now:
            return False, f"SESSDATA 已过期（到期: {time.strftime('%Y-%m-%d', time.localtime(int(e[3])))}）"
    # API 实测
    req = urllib.request.Request(
        'https://api.bilibili.com/x/web-interface/nav',
        headers={'Cookie': cookie_str, 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data.get('code') == 0 and data.get('data', {}).get('isLogin'):
            uname = data['data'].get('uname', '?')
            vip = '大会员' if data['data'].get('vipStatus') == 1 else '普通'
            return True, f'登录有效: {uname} ({vip})'
        return False, f"API 返回未登录 (code={data.get('code')})"
    except Exception as e:
        return False, f'网络错误: {e}'

# ── 配置操作 ──────────────────────────────────────────────────────

def update_options(enable):
    opts = {}
    if os.path.exists(OPTIONS_FILE):
        try:
            opts = json.load(open(OPTIONS_FILE))
        except Exception:
            pass
    if enable:
        opts['cookiefile'] = '/config/cookies.txt'
    else:
        opts.pop('cookiefile', None)
    with open(OPTIONS_FILE, 'w') as f:
        json.dump(opts, f, ensure_ascii=False, indent=2)

def do_set(value):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    entries = []
    now = time.time()
    exp = str(int(now) + 365 * 86400)

    if os.path.isfile(value):
        if value.endswith('.json'):
            pairs = parse_json_export(value)
            entries = [('.bilibili.com', '/', 'FALSE', exp, k, v) for k, v in pairs]
        else:
            raw = parse_netscape_file(value)
            if raw:
                entries = raw
            else:
                pairs = parse_cookie_string(open(value).read().strip())
                entries = [('.bilibili.com', '/', 'FALSE', exp, k, v) for k, v in pairs]
    elif looks_like_sessdata(value):
        entries = [('.bilibili.com', '/', 'FALSE', exp, 'SESSDATA', value)]
    elif '=' in value:
        pairs = parse_cookie_string(value)
        entries = [('.bilibili.com', '/', 'FALSE', exp, k, v) for k, v in pairs]
    else:
        sys.exit(f'无法识别的输入: {value[:50]}...\n支持: SESSDATA值 / "k1=v1; k2=v2" / 文件路径(.txt/.json)')

    if not entries:
        sys.exit('未解析出任何 cookie')

    write_netscape(entries)
    update_options(True)
    names = [e[4] for e in entries]
    print(f'[ok] 写入 {len(entries)} 个 cookie: {", ".join(names)}')
    print(f'[ok] ytdl_options.json 已启用 cookiefile（热加载生效）')
    ok, msg = check_bilibili_login()
    print(f'{"[ok]" if ok else "[warn]"} {msg}')
    if not ok and '过期' in msg:
        print('\n>>> Cookie 已过期，请在浏览器重新登录后获取新的 SESSDATA。')

def do_status():
    print(f'cookies 文件: {"存在" if os.path.exists(COOKIES_FILE) else "不存在"}')
    if os.path.exists(COOKIES_FILE):
        entries = parse_netscape_file(COOKIES_FILE)
        print(f'  条目: {", ".join(e[4] for e in entries)}')
        now = time.time()
        for e in entries:
            if e[4] == 'SESSDATA' and e[3].isdigit():
                remain = int(e[3]) - now
                if remain <= 0:
                    print('  SESSDATA: 已过期!')
                else:
                    print(f'  SESSDATA: 剩余 {int(remain/86400)} 天')
    opts = json.load(open(OPTIONS_FILE)) if os.path.exists(OPTIONS_FILE) else {}
    print(f'cookiefile 启用: {"是" if opts.get("cookiefile") else "否"}')

def do_check():
    ok, msg = check_bilibili_login()
    print(f'{"[ok]" if ok else "[fail]"} {msg}')
    sys.exit(0 if ok else 1)

def do_remove():
    if os.path.exists(COOKIES_FILE):
        os.remove(COOKIES_FILE)
    update_options(False)
    print('[ok] 已移除 cookie 配置')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--set', metavar='VALUE_OR_FILE')
    g.add_argument('--status', action='store_true')
    g.add_argument('--check', action='store_true')
    g.add_argument('--remove', action='store_true')
    args = ap.parse_args()
    if args.set: do_set(args.set)
    elif args.status: do_status()
    elif args.check: do_check()
    elif args.remove: do_remove()

if __name__ == '__main__':
    main()
