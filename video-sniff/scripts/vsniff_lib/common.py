#!/usr/bin/env python3
"""公共工具：HTTP 客户端、请求头构造、URL 解析、日志、外部命令封装。

接口约定：本文件只提供基础设施，其它模块调用它，不要在里面塞业务逻辑。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)

DOWNLOAD_DIR = os.environ.get("VSNIFF_DOWNLOAD_DIR", "/data/download/video")
TMP_DIR = os.environ.get("VSNIFF_TMP_DIR", "/data/tmp/vsniff")


def log(*args, **kw):
    """诊断日志一律走 stderr，保证 stdout 只输出 JSON。"""
    print(*args, file=sys.stderr, flush=True, **kw)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def tmp_subdir(name):
    """在临时目录下建一个带时间戳的独立工作目录。"""
    path = os.path.join(TMP_DIR, "%s-%d" % (re.sub(r"[^\w.-]+", "_", name)[:60], int(time.time())))
    return ensure_dir(path)


def default_headers(referer=None, cookie=None, ua=None, extra=None, origin=None):
    h = {
        "User-Agent": ua or DEFAULT_UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if referer:
        h["Referer"] = referer
        if origin is None:
            p = urllib.parse.urlsplit(referer)
            if p.scheme and p.netloc:
                h["Origin"] = "%s://%s" % (p.scheme, p.netloc)
    if origin:
        h["Origin"] = origin
    if cookie:
        h["Cookie"] = cookie
    if extra:
        h.update({k: v for k, v in extra.items() if v})
    return h


def headers_from_args(args, referer=None, cookie=None, ua=None):
    """把 --header 形式的附加头合并进来（附加头优先级最高）。"""
    extra = {}
    for item in getattr(args, "header", None) or []:
        if ":" in item:
            k, v = item.split(":", 1)
            extra[k.strip()] = v.strip()
    headers = default_headers(referer=referer, cookie=cookie, ua=ua)
    headers.update(extra)
    return headers


def resolve_url(base, url):
    """按 RFC 3986 解析相对地址（m3u8/mpd 内部大量使用）。"""
    if not url:
        return url
    return urllib.parse.urljoin(base, url.strip())


class HttpClient:
    """带重试与小退避的 HTTP 客户端，供 HLS/DASH 复用。"""

    def __init__(self, headers=None, timeout=20, retries=3, verify=True):
        self.session = requests.Session()
        self.headers = headers or default_headers()
        self.timeout = timeout
        self.retries = retries
        self.verify = verify

    def get(self, url, headers=None, stream=False, allow_redirects=True, timeout=None):
        last = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(
                    url,
                    headers=headers or self.headers,
                    timeout=timeout or self.timeout,
                    stream=stream,
                    allow_redirects=allow_redirects,
                    verify=self.verify,
                )
                if resp.status_code in (403, 404, 416, 429, 500, 502, 503, 504) and attempt + 1 < self.retries:
                    last = requests.HTTPError("HTTP %d" % resp.status_code, response=resp)
                    resp.close()
                    time.sleep(0.4 * (2 ** attempt))
                    continue
                return resp
            except requests.RequestException as exc:
                last = exc
                if attempt + 1 < self.retries:
                    time.sleep(0.4 * (2 ** attempt))
                    continue
                raise
        raise last

    def get_text(self, url, headers=None):
        resp = self.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text, resp

    def get_bytes(self, url, headers=None):
        resp = self.get(url, headers=headers, stream=True)
        resp.raise_for_status()
        data = resp.content
        resp.close()
        return data


def have_cmd(name):
    return shutil.which(name) is not None


def run_cmd(cmd, log_path=None, check=True):
    """执行外部命令；失败时抛出带 stderr 摘要的异常。"""
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("$ %s\n%s\n%s\n" % (" ".join(cmd), out[-4000:], err[-8000:]))
    if check and proc.returncode != 0:
        raise RuntimeError("命令失败(%d): %s\n%s" % (proc.returncode, " ".join(cmd), err[-2000:]))
    return proc.returncode, out, err


def ffprobe_json(path):
    """用 ffprobe 读取媒体信息，失败返回 {}。"""
    if not have_cmd("ffprobe"):
        return {}
    code, out, _ = run_cmd(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        check=False,
    )
    if code != 0 or not out.strip():
        return {}
    try:
        return json.loads(out)
    except ValueError:
        return {}


def media_summary(path):
    """返回 size/duration/resolution/codec 摘要，供统一 JSON 输出。"""
    info = {"file": path}
    try:
        info["size"] = os.path.getsize(path)
    except OSError:
        info["size"] = None
    probe = ffprobe_json(path)
    fmt = probe.get("format") or {}
    streams = probe.get("streams") or []
    if fmt.get("duration"):
        try:
            info["duration"] = round(float(fmt["duration"]), 2)
        except ValueError:
            pass
    for st in streams:
        kind = st.get("codec_type")
        if kind == "video" and "resolution" not in info:
            w, h = st.get("width"), st.get("height")
            if w and h:
                info["resolution"] = "%dx%d" % (w, h)
            info["vcodec"] = st.get("codec_name")
        elif kind == "audio" and "acodec" not in info:
            info["acodec"] = st.get("codec_name")
            info["channels"] = st.get("channels")
    info["hasVideo"] = any(s.get("codec_type") == "video" for s in streams)
    info["hasAudio"] = any(s.get("codec_type") == "audio" for s in streams)
    return info


def emit(payload, as_json=True):
    """统一输出：stdout 一行 JSON。"""
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        log(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def human_size(num):
    if not num:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    val = float(num)
    while val >= 1024 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return "%.1f%s" % (val, units[idx])
