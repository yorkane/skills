#!/usr/bin/env python3
"""vsdl 统一下载入口：--report / --url / --page 三种模式。

stdout 只输出一行 JSON（ok 结果）；所有诊断走 stderr。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

import requests

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from vsniff_lib import common, naming  # noqa: E402

NODE = "/home/aigc/.nvm/versions/node/v24.20.0/bin/node"
SNIFF_MJS = os.path.join(SCRIPT_DIR, "sniff.mjs")
MEDIA_EXTS = {".mp4", ".m4v", ".mkv", ".webm", ".mov", ".flv", ".ts", ".avi", ".mpeg",
              ".m4a", ".mp3", ".aac", ".ogg", ".ogv", ".wav"}
CT2EXT = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov",
          "video/x-flv": "flv", "video/mpeg": "mpeg", "video/mp2t": "ts",
          "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/aac": "aac",
          "video/matroska": "mkv", "audio/ogg": "ogg"}


def log(*a):
    common.log("[vsdl]", *a)


def fail(error, extra=None):
    payload = {"ok": False, "error": str(error)}
    if extra:
        payload.update({k: v for k, v in extra.items() if v is not None})
    log("失败:", str(error))
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(1)


def parse_json_line(stdout):
    for line in reversed([l for l in (stdout or "").splitlines() if l.strip()]):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def guess_kind(url):
    u = (url or "").lower()
    if ".m3u8" in u:
        return "hls"
    if ".mpd" in u:
        return "dash"
    return "file"


def path_ext(url):
    return os.path.splitext(urllib.parse.urlsplit(url or "").path)[1].lower()


def hls_has_audio_track(url, referer, cookie, ua):
    """快速拉播放列表判断是否有独立音频轨。"""
    if path_ext(url) != ".m3u8":
        return False
    try:
        client = common.HttpClient(
            headers=common.default_headers(referer=referer, cookie=cookie, ua=ua), timeout=10)
        resp = client.get(url)
        text = resp.text
        resp.close()
        return bool(re.search(r"EXT-X-MEDIA:[^\n]*TYPE=AUDIO", text))
    except Exception as exc:
        log("音频轨探测失败(忽略): %s" % exc)
        return False


def dash_has_audio_track(url, referer, cookie, ua):
    if path_ext(url) != ".mpd":
        return False
    try:
        client = common.HttpClient(
            headers=common.default_headers(referer=referer, cookie=cookie, ua=ua), timeout=10)
        text, _ = client.get_text(url)
        return "audio" in text.lower()
    except Exception as exc:
        log("MPD 音频探测失败(忽略): %s" % exc)
        return False


def run_module(name, url, outdir, stem, quality, referer, cookie, ua, headers):
    mod = os.path.join(SCRIPT_DIR, "vsniff_lib", name + ".py")
    if not os.path.exists(mod):
        fail("vsniff_lib/%s.py 尚未就绪（并行开发中）: %s" % (name, mod))
    # 探测模块是否接受 --name（dash.py 等模块命名规则由 MPD 决定）
    probe = subprocess.run([sys.executable, "-m", "vsniff_lib." + name, "--help"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           cwd=SCRIPT_DIR, env=dict(os.environ,
                           PYTHONPATH=SCRIPT_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")))
    help_out = (probe.stdout or b"").decode("utf-8", "replace")
    has_name = "--name" in help_out
    cmd = [sys.executable, "-m", "vsniff_lib." + name,
           "--url", url, "--out", outdir, "--json"]
    if has_name:
        cmd += ["--name", stem]
    if quality:
        cmd += ["--quality", str(quality)]
    if referer:
        cmd += ["--referer", referer]
    if cookie:
        cmd += ["--cookie", cookie]
    if ua:
        cmd += ["--user-agent", ua]
    for h in headers or []:
        cmd += ["--header", h]
    env = dict(os.environ)
    env["PYTHONPATH"] = SCRIPT_DIR + os.pathsep + env.get("PYTHONPATH", "")
    log("调用 %s 模块: %s" % (name, url))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=SCRIPT_DIR, env=env)
    err = proc.stderr.decode("utf-8", "replace")
    if err.strip():
        common.log(err.rstrip()[-8000:])
    result = parse_json_line(proc.stdout.decode("utf-8", "replace"))
    if result is None:
        fail("%s 模块未返回 JSON（退出码 %d）" % (name, proc.returncode))
    if not result.get("ok"):
        fail(result.get("error") or ("%s 下载失败" % name))
    # 模块不支持 --name 时，把产物改名为统一标题
    if not has_name and result.get("file") and stem:
        import shutil
        want = naming.unique_path(outdir, stem, os.path.splitext(result["file"])[1])
        if os.path.abspath(want) != os.path.abspath(result["file"]):
            shutil.move(result["file"], want)
            log("已改名: %s -> %s" % (result["file"], want))
            result["file"] = want
    return result


def guess_ext(url, referer, cookie, ua):
    ext = path_ext(url)
    if ext in MEDIA_EXTS:
        return ext.lstrip(".")
    try:
        h = common.default_headers(referer=referer, cookie=cookie, ua=ua)
        h["Range"] = "bytes=0-0"
        resp = requests.get(url, headers=h, timeout=10, stream=True, allow_redirects=True)
        ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        resp.close()
    except Exception as exc:
        log("Content-Type 探测失败(回退 mp4): %s" % exc)
        ct = ""
    return CT2EXT.get(ct, "mp4")


def cleanup(path):
    for p in (path, path + ".aria2"):
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def maybe_remux(path, fmt):
    if fmt not in ("mp4", "mkv"):
        return path
    cur = os.path.splitext(path)[1].lstrip(".")
    if cur == fmt:
        return path
    if not common.have_cmd("ffmpeg"):
        log("想要 .%s 但缺少 ffmpeg，保持原容器" % fmt)
        return path
    dst = os.path.splitext(path)[0] + "." + fmt
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", path, "-c", "copy"]
    if fmt == "mp4":
        cmd += ["-movflags", "+faststart"]
    cmd.append(dst)
    code, _, err = common.run_cmd(cmd, check=False)
    if code != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
        log("remux 到 .%s 失败，保持原容器: %s" % (fmt, err.strip()[-500:]))
        return path
    os.remove(path)
    log("已转封装为 .%s" % fmt)
    return dst


def download_file(url, outdir, stem, referer, cookie, ua, headers, fmt):
    ext = guess_ext(url, referer, cookie, ua)
    target = naming.unique_path(outdir, stem, ext)
    log("直链下载:", url, "->", target)
    cmd = ["aria2c", "-x16", "-s16", "-k1M", "--continue=true",
           "--max-tries=3", "--retry-wait=1",
           "--console-log-level=warn", "--summary-interval=0",
           "--user-agent=" + (ua or common.DEFAULT_UA),
           "-d", outdir, "-o", os.path.basename(target), url]
    if referer:
        cmd += ["--referer", referer]
    if cookie:
        cmd += ["--header", "Cookie: " + cookie]
    for h in headers or []:
        if h.split(":", 1)[0].strip().lower() != "cookie":
            cmd += ["--header", h]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    err = proc.stderr.decode("utf-8", "replace")
    if err.strip():
        common.log(err.rstrip()[-4000:])
    if proc.returncode != 0 or not os.path.exists(target) or os.path.getsize(target) == 0:
        cleanup(target)
        fail("aria2c 下载失败（退出码 %d）" % proc.returncode)
    info = common.media_summary(target)
    if not info.get("hasVideo") and not info.get("hasAudio"):
        cleanup(target)
        fail("ffprobe 无法解析该文件，不是可读媒体")
    target = maybe_remux(target, fmt)
    info = common.media_summary(target)
    return {"file": target, "size": info.get("size"), "duration": info.get("duration"),
            "resolution": info.get("resolution"), "vcodec": info.get("vcodec"),
            "acodec": info.get("acodec")}


def resolve_title(args, meta, url):
    if args.name:
        return naming.clean_title(args.name) or "video"
    if args.title:
        return naming.clean_title(args.title) or "video"
    if meta:
        return naming.pick_title(meta)
    stem = os.path.splitext(os.path.basename(urllib.parse.urlsplit(url).path))[0]
    return naming.clean_title(stem) or "video"


def download_candidate(cand, meta, args, outdir):
    started = time.time()
    kind = cand.get("kind") or guess_kind(cand.get("url"))
    url = cand.get("url")
    if not url:
        fail("候选缺少 url")
    if kind == "file" and path_ext(url) == ".m3u8":
        kind = "hls"
    referer = args.referer or cand.get("referer") or (meta or {}).get("pageUrl")
    cookie = args.cookie or (meta or {}).get("cookies")
    ua = args.user_agent or (meta or {}).get("userAgent")
    title = resolve_title(args, meta, url)
    stem = naming.clean_title(args.name) if args.name else title
    common.ensure_dir(outdir)

    if kind == "hls":
        h = cand.get("hls") or {}
        if h.get("audioGroup") or hls_has_audio_track(url, referer, cookie, ua):
            log("检测到独立音频轨，将自动合并")
        res = run_module("hls", url, outdir, stem, args.quality, referer, cookie, ua, args.header)
    elif kind == "dash":
        if dash_has_audio_track(url, referer, cookie, ua):
            log("检测到独立音频轨，将自动合并")
        res = run_module("dash", url, outdir, stem, args.quality, referer, cookie, ua, args.header)
    else:
        res = download_file(url, outdir, stem, referer, cookie, ua, args.header, args.format)

    final = {"ok": True, "kind": kind, "title": title}
    for k, v in res.items():
        if k != "ok" and k not in final:
            final[k] = v
    if final.get("file"):
        final["file"] = os.path.abspath(final["file"])
        if args.format in ("mp4", "mkv") and kind in ("hls", "dash"):
            newpath = maybe_remux(final["file"], args.format)
            if newpath != final["file"]:
                info = common.media_summary(newpath)
                final["file"] = newpath
                for k in ("size", "duration", "resolution", "vcodec", "acodec"):
                    if info.get(k) is not None:
                        final[k] = info[k]
    final["elapsed"] = round(time.time() - started, 1)
    print(json.dumps(final, ensure_ascii=False))
    log("完成:", final.get("file"), common.human_size(final.get("size")))
    return final


def pick_candidate(report, args):
    cands = report.get("candidates") or []
    if not cands:
        fail("报告中没有候选")
    if args.id:
        cand = next((c for c in cands if c.get("id") == args.id), None)
        if cand is None:
            fail("找不到候选 %s（可选: %s）" % (args.id, ", ".join(str(c.get("id", "?")) for c in cands)))
    else:
        cand = next((c for c in cands if c.get("recommended")), cands[-1])
    log("选用候选:", cand.get("id"), cand.get("kind"), cand.get("url"))
    return cand


def cmd_report(args, outdir):
    try:
        with open(args.report, encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, ValueError) as exc:
        fail("读取嗅探报告失败: %s" % exc)
    cand = pick_candidate(report, args)
    return download_candidate(cand, report, args, outdir)


def run_sniff(args, page):
    if not os.path.exists(SNIFF_MJS):
        fail("sniff.mjs 尚未就绪（并行开发中）: %s" % SNIFF_MJS)
    if args.cdp and args.launch:
        fail("--cdp 与 --launch 互斥")
    common.ensure_dir(common.TMP_DIR)
    parts = urllib.parse.urlsplit(page)
    slug = re.sub(r"[^\w.-]+", "_", (parts.netloc + parts.path)[:60]) or "page"
    report_path = os.path.join(common.TMP_DIR, "%s-%d.json" % (slug, int(time.time())))
    cmd = [NODE, SNIFF_MJS, "--url", page, "--out", report_path]
    if args.cdp:
        cmd += ["--cdp", args.cdp]
    if args.launch:
        cmd += ["--launch"]
    if args.seconds:
        cmd += ["--seconds", str(args.seconds)]
    log("启动嗅探:", " ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    err = proc.stderr.decode("utf-8", "replace")
    if err.strip():
        common.log(err.rstrip()[-8000:])
    report = parse_json_line(proc.stdout.decode("utf-8", "replace"))
    if report is None and os.path.exists(report_path):
        try:
            with open(report_path, encoding="utf-8") as fh:
                report = json.load(fh)
        except ValueError:
            report = None
    if report is None:
        fail("sniff.mjs 未返回报告（退出码 %d）" % proc.returncode)
    log("报告:", report_path)
    return report


def main():
    ap = argparse.ArgumentParser(prog="vsdl", description="video-sniff 统一下载入口")
    ap.add_argument("--report", help="嗅探报告 JSON 路径")
    ap.add_argument("--url", help="媒体直链（仅在用户已给出完整媒体地址时使用；否则请用 --page 走浏览器嗅探）")
    ap.add_argument("--page", help="页面 URL（先嗅探再下载）；未指定 --cdp 时默认用 Playwright 驱动浏览器")
    ap.add_argument("--id", help="报告中的候选 id")
    ap.add_argument("--best", action="store_true", help="同默认：用 recommended 候选")
    ap.add_argument("--kind", choices=["hls", "dash", "file"])
    ap.add_argument("--referer")
    ap.add_argument("--cookie")
    ap.add_argument("--user-agent")
    ap.add_argument("--header", action="append", default=[], help="附加请求头 'K: V'，可重复")
    ap.add_argument("--title")
    ap.add_argument("--name")
    ap.add_argument("--outdir")
    ap.add_argument("--quality", help="best|1080|720|<height>")
    ap.add_argument("--format", choices=["original", "mp4", "mkv"], default="original")
    ap.add_argument("--json", action="store_true", help="stdout 只一行 JSON")
    ap.add_argument("--cdp", help="CDP endpoint（--page 用）；仅在用户明确要求附着已有浏览器时使用")
    ap.add_argument("--launch", action="store_true", help="自己拉起 headless chromium（默认行为，显式写法）")
    ap.add_argument("--seconds", type=int, help="嗅探监听秒数")
    ap.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = ap.parse_args()

    modes = sum(bool(x) for x in (args.report, args.url, args.page))
    if modes != 1:
        fail("必须且只能指定 --report / --url / --page 之一")
    outdir = args.outdir or os.environ.get("VSNIFF_DOWNLOAD_DIR") or common.DOWNLOAD_DIR
    outdir = common.ensure_dir(os.path.abspath(outdir))

    if args.report:
        cmd_report(args, outdir)
    elif args.url:
        kind = args.kind or guess_kind(args.url)
        cand = {"id": "direct", "kind": kind, "url": args.url, "referer": args.referer}
        download_candidate(cand, {}, args, outdir)
    else:
        report = run_sniff(args, args.page)
        cand = pick_candidate(report, args)
        download_candidate(cand, report, args, outdir)


if __name__ == "__main__":
    main()
