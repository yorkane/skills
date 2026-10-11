#!/usr/bin/env python3
"""DASH (MPD) 下载器：解析静态 MPD，并发下载视频/音频轨，ffmpeg -c copy 合并。"""

import argparse
import math
import os
import re
import shutil
import sys
import threading
import time
import traceback
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from . import common
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from vsniff_lib import common

MEDIA_EXTS = {".mp4", ".m4v", ".mkv", ".m4a", ".mp3", ".mov", ".webm", ".ts"}
MKV_VIDEO = {"hevc", "h265", "vp9", "av1", "theora", "mpeg2video", "mpeg4", "prores"}
MKV_AUDIO = {"opus", "vorbis", "flac", "pcm_s16le", "pcm_s24le", "pcm_f32le", "pcm_s32le"}

_ISO_RE = re.compile(
    r"^P?(?:(?P<y>\d+)Y)?(?:(?P<mo>\d+)M)?(?:(?P<d>\d+)D)?"
    r"T?(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<mi>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<s>\d+(?:\.\d+)?)S)?$"
)


def parse_iso_duration(s, default=0.0):
    if not s:
        return default
    m = _ISO_RE.match(s.strip())
    if not m:
        return default
    g = m.groupdict()
    return (
        float(g.get("y") or 0) * 31557600
        + float(g.get("mo") or 0) * 2629800
        + float(g.get("d") or 0) * 86400
        + float(g.get("h") or 0) * 3600
        + float(g.get("mi") or 0) * 60
        + float(g.get("s") or 0)
    )


def local(tag):
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def strip_ns(root):
    for el in root.iter():
        el.tag = local(el.tag)


def first_segment_el(el):
    for ch in el:
        t = local(ch.tag)
        if t in ("SegmentTemplate", "SegmentList", "SegmentBase"):
            return t, ch
    return None, None


def child_base(parent_base, el):
    b = parent_base
    for ch in el:
        if local(ch.tag) == "BaseURL":
            t = (ch.text or "").strip()
            if t:
                b = common.resolve_url(b, t)
            break
    return b


def parse_byte_range(spec, kind):
    if not spec:
        return None
    a, b = spec.split("-", 1)
    a, b = int(a.strip()), int(b.strip())
    if kind == "index":
        return "bytes=%d-%d" % (a - 1, b)
    return "bytes=%d-%d" % (a - 1, a + b - 2)


def check_drm(root):
    for el in root.iter():
        if local(el.tag) == "ContentProtection":
            for ch in el:
                if local(ch.tag) in ("pssh", "pro"):
                    raise RuntimeError("检测到 DRM 加密内容(ContentProtection)，不支持下载")


class Track:
    def __init__(self, kind, codec=None, bandwidth=0, width=None, height=None, lang=None):
        self.kind = kind
        self.codec = codec
        self.bandwidth = bandwidth
        self.width = width
        self.height = height
        self.lang = lang
        self.init_url = None
        self.items = []
        self.single_url = None
        self.single_range = None
        self.segment_count = 0

    @property
    def is_single(self):
        return self.single_url is not None


def is_video_as(as_el):
    mt = (as_el.get("mimeType") or "").lower()
    if mt:
        return mt.startswith("video/")
    ct = (as_el.get("contentType") or "").lower()
    if ct:
        return ct == "video"
    if as_el.get("maxWidth") or as_el.get("maxHeight"):
        return True
    for rep in as_el.findall("Representation"):
        if rep.get("width") and rep.get("height"):
            return True
    return False


def is_audio_as(as_el):
    mt = (as_el.get("mimeType") or "").lower()
    if mt:
        return mt.startswith("audio/")
    ct = (as_el.get("contentType") or "").lower()
    if ct:
        return ct == "audio"
    if as_el.get("audioSamplingRate"):
        return True
    for rep in as_el.findall("Representation"):
        if rep.get("audioSamplingRate"):
            return True
    return False


def pick_rep(as_el, quality=None):
    reps = as_el.findall("Representation")
    if not reps:
        return None
    bw = lambda r: int(r.get("bandwidth") or 0)
    ht = lambda r: int(r.get("height") or 0)
    if not quality or quality == "best":
        return max(reps, key=lambda r: (bw(r), ht(r)))
    try:
        h = int(quality)
    except ValueError:
        return max(reps, key=bw)
    pool = [r for r in reps if 0 < ht(r) <= h] or reps
    return max(pool, key=lambda r: (ht(r), bw(r)))


def pick_audio_as(as_list, lang_hint="zh"):
    """多个音频 AdaptationSet 时的选择：语言优先(zh > 指定语言 > default > 第一个)。"""
    def score(item):
        as_el = item[0] if isinstance(item, tuple) else item
        lang = (as_el.get("lang") or "").lower()
        if lang.startswith(lang_hint):
            return 0
        if lang in ("", "und", "qaa", "mul"):
            return 1
        if lang.startswith("en"):
            return 2
        return 3
    return min(as_list, key=score)


def fill_pattern(pattern, mapping, base):
    for k, v in mapping.items():
        pattern = pattern.replace("$%s$" % k, str(v))
    return common.resolve_url(base, pattern)


def first_found(*els):
    """在候选 Element 中返回第一个非 None 的（Element 空元素 bool 为 False，
    不能用 or 链判断）。"""
    for e in els:
        if e is not None:
            return e
    return None


def effective_template(rep_el, as_el, period_el):
    return first_found(
        rep_el.find("SegmentTemplate") if rep_el is not None else None,
        as_el.find("SegmentTemplate") if as_el is not None else None,
        period_el.find("SegmentTemplate") if period_el is not None else None,
    )


def build_track(rep_el, as_el, period_el, mpd_url, base, kind, duration_hint):
    rep_base = child_base(base, rep_el)
    track = Track(
        kind,
        codec=rep_el.get("codecs") or as_el.get("codecs"),
        bandwidth=int(rep_el.get("bandwidth") or 0),
        width=(int(rep_el.get("width")) if rep_el.get("width") else None),
        height=(int(rep_el.get("height")) if rep_el.get("height") else None),
        lang=as_el.get("lang"),
    )
    tname, tel = first_segment_el(rep_el)
    if tname is None:
        # 注意：空 Element 的 bool 为 False，必须用 is not None 判断
        for tag in ("SegmentTemplate", "SegmentList", "SegmentBase"):
            tel = first_found(
                as_el.find(tag),
                period_el.find(tag) if period_el is not None else None,
            )
            if tel is not None:
                break
        tname = local(tel.tag) if tel is not None else None
    elif tname != "SegmentTemplate":
        if tel is not None and tel.find("SegmentURL") is None and tname == "SegmentList":
            pass
        if tel is None and tname == "SegmentBase":
            tel = (
                period_el.find("SegmentBase")
                if period_el is not None
                else None
            )

    if tname == "SegmentTemplate" and tel is not None:
        _build_from_template(rep_el, tel, track, mpd_url, rep_base, duration_hint)
    elif tname == "SegmentList" and tel is not None:
        _build_from_list(tel, track, mpd_url, rep_base)
    elif tname == "SegmentBase" and tel is not None:
        track.single_range = parse_byte_range(tel.get("indexRange"), "index")
        track.single_url = rep_base
    else:
        # 无分段结构：Representation 的 BaseURL 即完整文件
        track.single_url = common.resolve_url(mpd_url, rep_base) if rep_base else None
    return track


def _build_from_template(rep_el, tel, track, mpd_url, base, duration_hint):
    id_v = rep_el.get("id", "")
    bw_v = rep_el.get("bandwidth", "0")
    ts = int(tel.get("timescale") or 1000)
    seg_dur = int(tel.get("duration") or 0)
    start_num = int(tel.get("startNumber") or 1)
    pto = int(tel.get("presentationTimeOffset") or 0)

    init_pat = tel.get("initialization")
    if init_pat:
        track.init_url = fill_pattern(
            init_pat, {"RepresentationID": id_v, "Bandwidth": bw_v}, mpd_url
        )

    media_pat = tel.get("media") or ""
    timeline = tel.find("SegmentTimeline")
    if timeline is not None:
        rows, num = [], start_num
        for s in timeline.findall("S"):
            t = int(s.get("t") or 0)
            d = int(s.get("d") or 0)
            r = int(s.get("r") or 0)
            for _ in range(r + 1):
                rows.append((t, d, num))
                t += d
                num += 1
        for t, d, num in rows:
            url = fill_pattern(
                media_pat,
                {
                    "RepresentationID": id_v,
                    "Bandwidth": bw_v,
                    "Time": t,
                    "Number": num,
                    "SubNumber": 0,
                },
                mpd_url,
            )
            track.items.append((url, None, d / ts))
    elif seg_dur and media_pat:
        n = 1
        if duration_hint and ts and seg_dur:
            n = max(1, int(math.ceil(duration_hint / (seg_dur / ts))))
        for i in range(n):
            url = fill_pattern(
                media_pat,
                {
                    "RepresentationID": id_v,
                    "Bandwidth": bw_v,
                    "Number": start_num + i,
                    "Time": pto + i * seg_dur,
                    "SubNumber": 0,
                },
                mpd_url,
            )
            track.items.append((url, None, seg_dur / ts))
    else:
        raise RuntimeError("SegmentTemplate 缺少 duration 或 SegmentTimeline，无法枚举分段")

    track.segment_count = len(track.items)


def _build_from_list(tel, track, mpd_url, rep_base):
    init_pat = tel.get("initialization")
    if init_pat:
        track.init_url = common.resolve_url(mpd_url, init_pat)
    segs = tel.findall("SegmentURL")
    if segs:
        items = []
        for su in segs:
            media = su.get("media")
            if not media:
                continue
            url = common.resolve_url(mpd_url, media)
            rng = parse_byte_range(su.get("byteRange"), "offset")
            items.append((url, rng, int(su.get("duration") or 0) / 1000.0))
        track.items = items
        track.segment_count = len(items)
        return
    track.single_url = rep_base
    track.single_range = parse_byte_range(tel.get("indexRange"), "index")


def parse_mpd(text, mpd_url, quality=None, max_seconds=None):
    """解析 MPD，返回 (video_track|None, audio_track|None, mpd_duration)。"""
    root = ET.fromstring(text)
    strip_ns(root)
    check_drm(root)
    duration = parse_iso_duration(root.get("mediaPresentationDuration"))
    mpd_base = mpd_url
    for ch in root:
        if local(ch.tag) == "BaseURL":
            t = (ch.text or "").strip()
            if t:
                mpd_base = common.resolve_url(mpd_url, t)
            break

    periods = root.findall("Period")
    if not periods:
        raise RuntimeError("MPD 中没有 Period")
    video_as_list = []
    audio_as_list = []
    period_duration = duration / len(periods) if duration else 0
    for p in periods:
        p_base = child_base(mpd_base, p)
        p_dur = parse_iso_duration(p.get("duration"), period_duration)
        for as_el in p.findall("AdaptationSet"):
            if is_video_as(as_el):
                video_as_list.append((as_el, p, p_base, p_dur))
            elif is_audio_as(as_el):
                audio_as_list.append((as_el, p, p_base, p_dur))

    video = audio = None
    if video_as_list:
        as_el, p, base, p_dur = max(video_as_list, key=lambda x: max(
            (int(r.get("bandwidth") or 0) for r in x[0].findall("Representation")),
            default=0,
        ))
        rep = pick_rep(as_el, quality)
        if rep is not None:
            hint = p_dur if len(periods) > 1 else duration
            video = build_track(rep, as_el, p, mpd_url, base, "video", hint or None)
    if audio_as_list:
        # audio_as_list 元素是 (as_el, p, p_base, p_dur) 元组，先取码率最高的
        as_el, p, base, p_dur = max(audio_as_list, key=lambda x: max(
            (int(r.get("bandwidth") or 0) for r in x[0].findall("Representation")),
            default=0,
        ))
        rep = pick_rep(as_el)
        if rep is not None:
            hint = p_dur if len(periods) > 1 else duration
            audio = build_track(rep, as_el, p, mpd_url, base, "audio", hint or None)

    # 截断：只保留前 max_seconds 秒（内部调试/测试用）
    if max_seconds:
        for trk in (video, audio):
            if trk is None or trk.is_single:
                continue
            keep, acc = [], 0.0
            for url, rng, d in trk.items:
                if acc >= max_seconds:
                    break
                keep.append((url, rng, d))
                acc += (d or 0)
            trk.items = keep
            trk.segment_count = len(keep)
    return video, audio, duration


def concat_bytes(parts, dest):
    """fMP4 字节级拼接：init 段 + 各 m4s 段按序 cat 成合法 MP4 文件。"""
    with open(dest, "wb") as fdst:
        for part in parts:
            with open(part, "rb") as fsrc:
                while True:
                    buf = fsrc.read(4 * 1024 * 1024)
                    if not buf:
                        break
                    fdst.write(buf)
    return dest


def _fetch_one(client, url, rng, dest, retries=3, timeout=None):
    headers = {}
    if rng:
        headers["Range"] = rng
    last = None
    for attempt in range(retries):
        try:
            resp = client.get(url, headers=headers or None, stream=True, timeout=timeout)
            if resp.status_code in (200, 206):
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        if chunk:
                            fh.write(chunk)
                resp.close()
                return os.path.getsize(dest)
            last = "HTTP %d for %s" % (resp.status_code, url)
            resp.close()
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
        if attempt + 1 < retries:
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("下载失败(重试%d次): %s" % (retries, last))


def download_track(client, track, workdir, label, concurrency, timeout=None, max_bytes=None):
    """下载一条轨道，返回文件路径列表（init + 分段）。"""
    out = []
    done = {"n": 0}
    lock = threading.Lock()
    total = len(track.items) + (1 if track.init_url else 0)

    def report():
        with lock:
            done["n"] += 1
            if done["n"] % 5 == 0 or done["n"] == total:
                common.log(
                    "  [%s] %d/%d 段 %s"
                    % (label, done["n"], total, time.strftime("%H:%M:%S"))
                )

    def job(i, url, rng, name):
        dest = os.path.join(workdir, name)
        size = _fetch_one(client, url, rng, dest, timeout=timeout)
        if max_bytes and size > max_bytes and not rng:
            with open(dest, "rb") as f:
                head = f.read(max_bytes)
            with open(dest, "wb") as f:
                f.write(head)
        report()
        return dest

    jobs = []
    if track.init_url:
        jobs.append((0, track.init_url, None, "0000_init_%s" % label))
    for i, (url, rng, _d) in enumerate(track.items):
        jobs.append((i + 1, url, rng, "%s_%05d" % (label, i)))

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(job, *j) for j in jobs]
        for fu in as_completed(futs):
            out.append(fu.result())
    # 按顺序排列（init 在前，分段按序号）
    init_name = "init_%s" % label
    out.sort(key=lambda p: (not p.endswith(init_name), p))
    return out


def _probe_codec(path, kind):
    info = common.ffprobe_json(path)
    for st in info.get("streams") or []:
        if st.get("codec_type") == kind:
            return st.get("codec_name")
    return None


def merge_media(video_files, audio_files, final_path, workdir):
    """ffmpeg -c copy 合并；返回 (实际输出路径, mediaFormat)。

    fMP4 拼出的文件 init 段可能超过默认 probesize(5MB)，需要加大探测参数，
    否则 ffmpeg 探测不到视频参数会静默丢轨。合并后再 ffprobe 校验双轨齐全。
    """
    inputs = []
    if video_files:
        inputs += ["-probesize", "200M", "-analyzeduration", "20M", "-i", video_files]
    if audio_files:
        inputs += ["-probesize", "200M", "-analyzeduration", "20M", "-i", audio_files]
    fmt = final_path.rsplit(".", 1)[-1].lower()
    if len(inputs) == 2:
        cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-map", "0:v:0", "-map", "1:a:0", "-c", "copy"]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-c", "copy"]
    if fmt == "mp4":
        cmd += ["-movflags", "+faststart"]
    cmd.append(final_path)
    try:
        common.run_cmd(cmd, log_path=os.path.join(workdir, "ffmpeg.log"))
    except RuntimeError:
        if not (fmt == "mp4" and video_files and audio_files):
            raise
        common.log("mp4 合并失败，回退 mkv")
        mkv_path = os.path.join(os.path.dirname(final_path), os.path.splitext(os.path.basename(final_path))[0] + ".mkv")
        cmd2 = ["ffmpeg", "-y", "-v", "error", *inputs, "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", mkv_path]
        common.run_cmd(cmd2, log_path=os.path.join(workdir, "ffmpeg.log"))
        return mkv_path, "mkv"
    # 校验：合并产物必须包含输入的所有轨
    probe = common.ffprobe_json(final_path)
    got = {s.get("codec_type") for s in probe.get("streams") or []}
    need = set()
    if video_files:
        need.add("video")
    if audio_files:
        need.add("audio")
    missing = need - got
    if missing:
        raise RuntimeError("合并后缺少 %s 轨道（ffmpeg 探测问题），请用 --keep-temp 检查中间产物" % "/".join(sorted(missing)))
    return final_path, fmt


def build_arg_parser():
    p = argparse.ArgumentParser(prog="vsniff_lib.dash", description="DASH(MPD) 下载器")
    p.add_argument("--url", required=True, help="MPD 地址")
    p.add_argument("--out", required=True, help="输出目录或目标文件")
    p.add_argument("--referer")
    p.add_argument("--cookie")
    p.add_argument("--user-agent")
    p.add_argument("--quality", default="best", help="best|1080|720|<height>")
    p.add_argument("--concurrency", type=int, default=12)
    p.add_argument("--keep-temp", action="store_true", help="保留临时工作目录")
    p.add_argument("--timeout", type=float, default=20)
    p.add_argument("--header", action="append", default=[], help="附加请求头 K: V，可重复")
    p.add_argument("--json", action="store_true")
    p.add_argument("--max-segments", type=int, default=0, help="内部参数：每轨最多下载段数")
    p.add_argument("--max-seconds", type=float, default=0, help="内部参数：只下载前 N 秒")
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    started = time.time()
    workdir = None
    try:
        headers = common.headers_from_args(args, referer=args.referer, cookie=args.cookie, ua=args.user_agent)
        client = common.HttpClient(headers=headers, timeout=args.timeout, retries=3)
        text, _resp = client.get_text(args.url)
        common.log("MPD 拉取成功，%d 字节" % len(text))

        video, audio, duration = parse_mpd(text, args.url, quality=args.quality, max_seconds=args.max_seconds or None)
        if args.max_segments:
            for trk in (video, audio):
                if trk is not None and not trk.is_single:
                    trk.items = trk.items[: args.max_segments]
                    trk.segment_count = len(trk.items)
        if video is None and audio is None:
            raise RuntimeError("MPD 中未找到可用的视频/音频 AdaptationSet")
        if video:
            common.log(
                "视频轨: %s %dx%d %dkbps 分段=%d 单文件=%s"
                % (
                    video.codec, video.width or 0, video.height or 0,
                    video.bandwidth // 1000, video.segment_count, video.is_single,
                )
            )
        if audio:
            common.log("音频轨: %s %dkbps 分段=%d 单文件=%s lang=%s"
                       % (audio.codec, audio.bandwidth // 1000, audio.segment_count, audio.is_single, audio.lang))

        workdir = common.tmp_subdir("dash")
        v_files, a_files = None, None
        if video:
            if video.is_single:
                common.log("视频为完整文件，直接下载")
                v_files = os.path.join(workdir, "video_full")
                _fetch_one(client, video.single_url, video.single_range, v_files)
            else:
                v_files = os.path.join(workdir, "video_track")
                os.makedirs(v_files, exist_ok=True)
                parts = download_track(client, video, v_files, "v", args.concurrency, args.timeout)
                v_files = os.path.join(workdir, "video_concat")
                v_dir = os.path.join(workdir, "video_track")
                v_files = os.path.join(workdir, "video_concat")
                v_parts = [os.path.join(v_dir, f) for f in sorted(os.listdir(v_dir))]
                concat_bytes(v_parts, v_files)
        if audio:
            if audio.is_single:
                common.log("音频为完整文件，直接下载")
                a_files = os.path.join(workdir, "audio_full")
                _fetch_one(client, audio.single_url, audio.single_range, a_files)
            else:
                a_dir = os.path.join(workdir, "audio_track")
                os.makedirs(a_dir, exist_ok=True)
                parts = download_track(client, audio, a_dir, "a", args.concurrency, args.timeout)
                a_files = os.path.join(workdir, "audio_concat")
                a_parts = [os.path.join(a_dir, f) for f in sorted(os.listdir(a_dir))]
                concat_bytes(a_parts, a_files)

        # 输出文件：--out 是指定文件则直接用；否则目录 + 时间戳
        if os.path.isdir(args.out) or args.out.endswith(os.sep) or not os.path.splitext(args.out)[1]:
            common.ensure_dir(args.out)
            base_name = "dash-%d" % int(time.time())
        else:
            common.ensure_dir(os.path.dirname(os.path.abspath(args.out)))
            base_name = os.path.splitext(os.path.basename(args.out))[0]

        # 容器选择：按轨 codec 预判
        vcodec = (video.codec or "").split(".")[0] if video else ""
        acodec = (audio.codec or "").split(".")[0] if audio else ""
        vcodec_l = vcodec.lower()
        ext = "mkv" if (vcodec_l in MKV_VIDEO or acodec.lower() in MKV_AUDIO) else "mp4"
        # 输出路径统一走 naming.unique_path：重名自动加 -2/-3，避免覆盖既有文件
        if os.path.splitext(args.out)[1] == "":
            final_dir, final_stem = args.out, base_name
        else:
            final_dir = os.path.dirname(os.path.abspath(args.out)) or "."
            final_stem = os.path.splitext(os.path.basename(args.out))[0]
        try:
            from vsniff_lib import naming as _naming
        except Exception:  # noqa: BLE001 兜底：naming 不可用时退回旧行为
            _naming = None
        final_path = (_naming.unique_path(final_dir, final_stem, ext) if _naming
                      else os.path.join(final_dir, final_stem + "." + ext))
        merge_media(v_files, a_files, final_path, workdir)

        summary = common.media_summary(final_path)
        summary.update({
            "ok": True,
            "segments": (video.segment_count if video else 0) + (audio.segment_count if audio else 0),
            "elapsed": round(time.time() - started, 2),
            "mediaFormat": os.path.splitext(final_path)[1].lstrip("."),
        })
        if not summary.get("duration") and duration:
            summary["duration"] = round(duration, 2)
        if not args.keep_temp:
            shutil.rmtree(workdir, ignore_errors=True)
        common.emit(summary)
        return 0
    except Exception as exc:  # noqa: BLE001
        common.log("错误: %s" % exc)
        common.log(traceback.format_exc().strip().splitlines()[-1])
        if workdir and not args.keep_temp:
            shutil.rmtree(workdir, ignore_errors=True)
        common.emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
