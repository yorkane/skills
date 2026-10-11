#!/usr/bin/env python3
"""HLS(m3u8) 下载器：解析 master/media 播放列表，并发下载分片，AES-128 解密，
ffmpeg -c copy 合并音视频，最终输出一行 JSON 结果。

用法（skill-spec.md 第 2 节）：
  python3 -m vsniff_lib.hls --url <m3u8> --out <dir-or-file>
      [--referer R] [--cookie C] [--user-agent UA] [--header 'K: V' ...]
      [--quality best|1080|720|<height>] [--concurrency 16] [--keep-ts]
      [--name 文件名不带扩展] [--timeout 20] [--json]

约定（skill-spec.md 第 5 节）：
- stdout 只输出一行 JSON（成功或失败），所有诊断日志走 stderr；
- 复用 common.py 的 HttpClient / headers_from_args / resolve_url / log /
  media_summary / tmp_subdir / run_cmd；
- 分片失败重试 3 次（退避 0.5/1/2s + 随机抖动）；403/404 属防盗链/签名过期，
  快速失败并明确报错，不做长退避卡住；
- 不静默失败：SAMPLE-AES 等不支持的加密方法显式报错，不产出坏文件。
"""

import argparse
import json
import os
import random
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from Crypto.Cipher import AES

# 允许 python3 hls.py 直接运行：把脚本目录加进 sys.path 后复用 common
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from common import (  # noqa: E402
    HttpClient,
    headers_from_args,
    log,
    media_summary,
    resolve_url,
    run_cmd,
    tmp_subdir,
    emit,
)

# naming 提供 unique_path（重名自动加 -2/-3）；兼容 -m vsniff_lib.hls 与直接运行两种导入方式
try:
    from vsniff_lib.naming import unique_path
except ImportError:
    from naming import unique_path

# ----------------------------- 常量 -----------------------------

RETRY_BASE = (0.5, 1.0, 2.0)      # 分片重试退避（秒），实际再乘随机抖动
ZH_LANGS = {"zh", "zho", "cmn", "yue", "zh-cn", "zh-tw", "zh-hk",
            "zh-hans", "zh-hant", "cmn-hans", "yue-hans"}


class HlsError(Exception):
    """HLS 下载过程中的可预期错误（转成 JSON error 输出）。"""


# ----------------------------- 播放列表解析 -----------------------------

def _split_attr(text):
    """解析 'K=V,K2="V 2"' 形式的标签属性串，值去掉外层引号。"""
    attrs = {}
    for m in re.finditer(r'([A-Za-z0-9-]+)\s*=\s*("[^"]*"|[^,]*)', text):
        key = m.group(1).upper()
        val = m.group(2).strip()
        if val[:1] == '"' and val[-1:] == '"':
            val = val[1:-1]
        attrs[key] = val
    return attrs


def parse_iv(value):
    """解析 EXT-X-KEY 的 IV：支持 0x 前缀 16 字节十六进制。

    缺省返回 None，由 Key.iv_for 按 media sequence 大端 16 字节派生。
    显式 IV 永远优先于 seq 推导（真实站点存在全部分片共用一个写死 IV 的情况）。
    """
    if not value:
        return None
    v = value.strip()
    if v.lower().startswith("0x"):
        v = v[2:]
    try:
        b = bytes.fromhex(v)
    except ValueError:
        raise HlsError("非法 IV（需要 16 字节十六进制）: %s" % value)
    if len(b) != 16:
        raise HlsError("非法 IV（需要 16 字节十六进制）: %s" % value)
    return b


class Segment(object):
    """单个分片：media sequence 编号 sn、时长、最终 URL、字节范围、所属密钥、init 段。"""

    __slots__ = ("sn", "duration", "url", "byte_range", "key", "init")

    def __init__(self, sn, duration, url, byte_range=None, key=None, init=None):
        self.sn = sn
        self.duration = duration
        self.url = url
        self.byte_range = byte_range      # (length, offset) 或 None
        self.key = key                    # Key 或 None
        self.init = init                  # (url, byte_range) 或 None


class Key(object):
    """EXT-X-KEY 状态：method / key URL（已做相对解析）/ 显式 IV（None 表示按 sn 派生）。"""

    __slots__ = ("method", "url", "iv")

    def __init__(self, method, url, iv=None):
        self.method = method
        self.url = url
        self.iv = iv

    def iv_for(self, sn):
        """返回该分片的 IV：显式 IV 优先；AES-128 无显式 IV 时按
        media sequence 编号（HLS 规范：大端 16 字节）派生。"""
        if self.iv is not None:
            return self.iv
        if self.method == "AES-128":
            return sn.to_bytes(16, "big")
        raise HlsError("加密方法 %s 未提供 IV" % self.method)


class Playlist(object):
    """一条播放列表的解析结果。

    is_master=True 时 variants/audio_groups 有值；否则 segments 有值。
    """

    def __init__(self, url, is_master, variants=None, audio_groups=None,
                 segments=None, total_duration=0.0, encrypted=False):
        self.url = url
        self.is_master = is_master
        self.variants = variants or []         # [dict: bandwidth/width/height/codecs/uri/audio/name]
        self.audio_groups = audio_groups or {} # group_id -> [dict: name/language/uri/is_default/...]
        self.segments = segments or []         # [Segment]
        self.total_duration = total_duration
        self.encrypted = encrypted


def _parse_byte_range(spec):
    """'N' 或 'N@O' -> (N, O)；O 缺省由调用方按上一分片结束位置顺延。"""
    if not spec:
        return None
    if "@" in spec:
        n, o = spec.split("@", 1)
        return (int(n), int(o))
    return (int(spec), None)


def parse_attr_line(line):
    """把一行 '#EXT-X-XXX:ATTR' 拆成 (TAG, attrs)。"""
    tag, _, rest = line.partition(":")
    return tag.upper(), _split_attr(rest)


def parse_playlist(text, base_url):
    """解析 m3u8 文本，返回 Playlist。

    覆盖：EXT-X-STREAM-INF / EXT-X-MEDIA / EXT-X-KEY / EXT-X-BYTERANGE /
    EXT-X-MAP / EXT-X-MEDIA-SEQUENCE / EXT-X-DISCONTINUITY / EXTINF，
    分片与 key 的相对 URL 一律按 base_url 解析。
    """
    raw = [ln.rstrip("\r\n") for ln in text.splitlines()]
    is_master = any(ln.startswith("#EXT-X-STREAM-INF") for ln in raw)

    if is_master:
        variants = []
        audio_groups = {}
        pending = None
        for ln in raw:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#EXT-X-STREAM-INF"):
                _, attrs = parse_attr_line(s)
                res = (attrs.get("RESOLUTION") or "").split("x")
                pending = {
                    "bandwidth": int(attrs.get("BANDWIDTH") or 0),
                    "width": int(res[0]) if len(res) == 2 and res[0].isdigit() else None,
                    "height": int(res[1]) if len(res) == 2 and res[1].isdigit() else None,
                    "codecs": attrs.get("CODECS") or "",
                    "frame_rate": attrs.get("FRAME-RATE") or "",
                    "audio": attrs.get("AUDIO"),
                    "name": attrs.get("NAME") or "",
                    "uri": None,
                }
            elif s.startswith("#EXT-X-MEDIA"):
                _, attrs = parse_attr_line(s)
                if (attrs.get("TYPE") == "AUDIO" and attrs.get("GROUP-ID")
                        and attrs.get("URI")):
                    audio_groups.setdefault(attrs["GROUP-ID"], []).append({
                        "name": attrs.get("NAME") or "",
                        "language": (attrs.get("LANGUAGE") or "").lower(),
                        "uri": resolve_url(base_url, attrs["URI"]),
                        "is_default": attrs.get("DEFAULT") == "YES",
                        "autoselect": attrs.get("AUTOSELECT") == "YES",
                        "channels": attrs.get("CHANNELS") or "",
                    })
            elif not s.startswith("#") and pending is not None:
                pending["uri"] = resolve_url(base_url, s)
                variants.append(pending)
                pending = None
        return Playlist(base_url, True, variants=variants,
                        audio_groups=audio_groups)

    # ---- media playlist ----
    segments = []
    seq = 0
    target = 10.0
    cur_key = None
    cur_init = None
    # 上一个「带字节范围的分片（含 EXT-X-MAP init 段）」的结束位置；
    # 供无 offset 的 EXT-X-BYTERANGE 按规范顺延（None = 没有可顺延的基准）
    last_br_end = None
    pending_duration = None
    pending_range = None
    for ln in raw:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            tag, attrs = parse_attr_line(s)
            if tag == "#EXT-X-MEDIA-SEQUENCE":
                # 值是裸数字（#EXT-X-MEDIA-SEQUENCE:5），不是 KEY=VALUE 形式，
                # _split_attr 解不出来，必须直接取冒号后的原文；
                # 这个值决定无 IV 时 AES-128 的 IV 派生，错一个字节全部分片首块解密错
                seq = int(s.split(":", 1)[1].strip() or 0)
            elif tag == "#EXT-X-TARGETDURATION":
                try:
                    target = float(s.split(":", 1)[1].strip() or 10)
                except ValueError:
                    pass
            elif tag == "#EXT-X-KEY":
                method = (attrs.get("METHOD") or "NONE").upper()
                if method == "AES-128":
                    uri = attrs.get("URI")
                    if not uri:
                        raise HlsError("EXT-X-KEY METHOD=AES-128 缺少 URI: %s" % s)
                    # key URI 同样做相对路径解析；IV 显式写死则优先
                    cur_key = Key(method, resolve_url(base_url, uri),
                                  parse_iv(attrs.get("IV")))
                elif method == "NONE":
                    cur_key = None
                else:
                    # SAMPLE-AES 等：先记下，落到分片时明确报错（不静默）
                    cur_key = Key(method,
                                  resolve_url(base_url, attrs["URI"]) if attrs.get("URI") else None,
                                  None)
            elif tag == "#EXT-X-MAP":
                uri = attrs.get("URI")
                if uri:
                    br = _parse_byte_range(attrs.get("BYTERANGE"))
                    cur_init = (resolve_url(base_url, uri), br)
                    if br is not None and br[1] is not None:
                        # init 段本身也是分片：它的字节范围同样是后续
                        # 无 offset BYTERANGE 的顺延基准（HLS 规范 10.5.2）
                        last_br_end = br[1] + br[0]
            elif tag == "#EXT-X-BYTERANGE":
                # 该标签的值没有 '='（形如 #EXT-X-BYTERANGE:2267397@720），
                # _split_attr 解析不出任何属性，必须直接取冒号后的原文
                spec = s.split(":", 1)[1].strip()
                pending_range = _parse_byte_range(spec)
                if pending_range is not None and pending_range[1] is None:
                    # 省略 offset：紧接上一个带字节范围的分片（或 init 段）
                    # 的结束位置；前面没有可顺延的则从 0 开始
                    off = last_br_end if last_br_end is not None else 0
                    pending_range = (pending_range[0], off)
            elif tag == "#EXTINF":
                try:
                    pending_duration = float(s.split(":", 1)[1].split(",")[0])
                except (IndexError, ValueError):
                    pending_duration = target
            elif tag in ("#EXT-X-DISCONTINUITY", "#EXT-X-ENDLIST",
                         "#EXT-X-PLAYLIST-TYPE", "#EXT-X-INDEPENDENT-SEGMENTS",
                         "#EXT-X-VERSION", "#EXT-X-PROGRAM-DATE-TIME"):
                # 记录性标签：DISCONTINUITY 处的编码切换交给 ffmpeg 拼接处理
                pass
            else:
                pending_duration = None
            continue
        # 非标签行 = 分片 URL
        seg = Segment(
            sn=seq,
            duration=pending_duration if pending_duration is not None else target,
            url=resolve_url(base_url, s),
            byte_range=pending_range,
            key=cur_key,
            init=cur_init,
        )
        segments.append(seg)
        seq += 1
        if seg.byte_range is not None:
            n, off = seg.byte_range
            last_br_end = off + n
        else:
            # 整文件分片：不能拿它当顺延基准
            last_br_end = None
        pending_duration = None
        pending_range = None

    total = sum(sg.duration for sg in segments)
    encrypted = any(sg.key is not None and sg.key.method != "NONE" for sg in segments)
    return Playlist(base_url, False, segments=segments,
                    total_duration=total, encrypted=encrypted)


# ----------------------------- 下载 -----------------------------

class SegmentDownloader(object):
    """线程池并发下载分片：重试（退避+抖动）、进度写 stderr、可中断。

    每个分片下载后按自身 EXT-X-KEY 解密（AES-128）；fMP4 场景（EXT-X-MAP）
    把 init 段前置到「轨内首个使用该 init 的分片」文件里（dedupe_init 保证）。
    """

    def __init__(self, client, segments, out_path, concurrency=16,
                 progress_cb=None, log_every=25):
        self.client = client
        self.segments = segments
        self.out_path = out_path
        self.concurrency = max(1, min(concurrency, max(1, len(segments))))
        self.progress_cb = progress_cb
        self.log_every = log_every
        self._stop = threading.Event()
        self._done = 0
        self._lock = threading.Lock()
        self._key_cache = {}          # key.url -> 16 字节密钥
        self._key_lock = threading.Lock()
        self._init_cache = {}         # (url, br) -> bytes

    def request_stop(self):
        """请求中断（可被外部信号处理调用）。"""
        self._stop.set()

    @property
    def stopped(self):
        return self._stop.is_set()

    def _fetch_key(self, key):
        """下载并缓存 AES 密钥；key 请求带与分片完全相同的防盗链头
        （Referer/Cookie/UA，很多站点 key 走同样的签名校验）。"""
        with self._key_lock:
            if key.url in self._key_cache:
                return self._key_cache[key.url]
        data = self.client.get_bytes(key.url)   # 复用 client 全局 headers
        if len(data) != 16:
            raise HlsError("密钥长度非法（期望 16 字节，实际 %d）: %s"
                           % (len(data), key.url[:160]))
        with self._key_lock:
            self._key_cache[key.url] = data
        return data

    def _decrypt(self, seg, data):
        """AES-128-CBC 解密：显式 IV 优先，无 IV 用 media sequence 大端 16 字节派生。

        不支持的加密方法（SAMPLE-AES 等）显式报错，绝不静默产出坏文件。
        """
        key = seg.key
        if key.method != "AES-128":
            raise HlsError(
                "不支持的加密方法 EXT-X-KEY:METHOD=%s（仅支持 AES-128/NONE；"
                "SAMPLE-AES 等需要 fMP4 内部解密，本实现不处理）" % key.method)
        raw_key = self._fetch_key(key)
        iv = key.iv_for(seg.sn)
        cipher = AES.new(raw_key, AES.MODE_CBC, iv)
        plain = cipher.decrypt(data)
        # 去 PKCS7 填充（填充非法时按整块返回，ts 分片一般有合法填充）
        pad = plain[-1] if plain else 0
        if 1 <= pad <= 16 and plain.endswith(bytes([pad]) * pad):
            plain = plain[:-pad]
        return plain

    def _download_one(self, seg):
        """下载单个分片：最多 3 次重试（退避 0.5/1/2s + 随机抖动）。

        403/404 视为防盗链拒绝/签名过期：重试无意义，第 2 次仍 403/404 就
        快速失败并明确报「签名可能已过期」，不做 3 次长退避卡住。
        """
        delays = RETRY_BASE + (0,)
        last_err = None
        seen_403_404 = False
        for attempt in range(len(delays)):
            if self._stop.is_set():
                raise HlsError("已中断")
            try:
                headers = {}
                if seg.byte_range:
                    n, off = seg.byte_range
                    headers["Range"] = "bytes=%d-%d" % (off, off + n - 1)
                data = self.client.get_bytes(seg.url, headers=headers or None)
                if seg.key is not None and seg.key.method != "NONE":
                    data = self._decrypt(seg, data)
                return data
            except Exception as exc:  # noqa: BLE001 统一在此重试
                last_err = exc
                if self._stop.is_set():
                    break
                status = None
                resp = getattr(exc, "response", None)
                if resp is not None:
                    status = resp.status_code
                if status in (403, 404):
                    seen_403_404 = True
                    if attempt >= 1:      # 给 1 次机会（网络偶发），然后快速失败
                        break
                    time.sleep(0.3)
                    continue
                if attempt + 1 < len(delays):
                    base = RETRY_BASE[min(attempt, len(RETRY_BASE) - 1)]
                    time.sleep(base * random.uniform(0.8, 1.3))
        if seen_403_404:
            status = getattr(getattr(last_err, "response", None), "status_code", "?")
            raise HlsError(
                "分片请求被拒绝（HTTP %s，疑似 auth_key 签名过期或防盗链，"
                "重试无意义；请重新嗅探获取新地址）: %s"
                % (status, seg.url[:160]))
        raise HlsError("分片下载失败（已重试 3 次）: %s -> %s"
                       % (seg.url[:160], last_err))

    def _load_init(self, init):
        """下载并缓存 init 段（EXT-X-MAP，可带 BYTERANGE）。"""
        url, br = init
        key = (url, br)
        if key not in self._init_cache:
            headers = {}
            if br:
                n, off = br
                headers["Range"] = "bytes=%d-%d" % (off, off + n - 1)
            self._init_cache[key] = self.client.get_bytes(url, headers=headers or None)
            log("[hls] init 段 %s (%d 字节)" % (url[:120], len(self._init_cache[key])))
        return self._init_cache[key]

    def run(self):
        """并发下载全部分片并顺序写盘。返回 (耗时秒, 分片数)。"""
        total = len(self.segments)
        if total == 0:
            raise HlsError("播放列表没有可下载的分片")
        results = [None] * total
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=self.concurrency,
                                thread_name_prefix="hls") as pool:
            futs = {pool.submit(self._download_one, seg): i
                    for i, seg in enumerate(self.segments)}
            for fut in futs:
                data = fut.result()
                i = futs[fut]
                results[i] = data
                with self._lock:
                    self._done += 1
                    n = self._done
                if self.progress_cb and (n % self.log_every == 0 or n == total):
                    self.progress_cb(n, total, time.time() - t0)
                if self._stop.is_set():
                    raise HlsError("下载被中断（已完成 %d/%d 分片）" % (n, total))
        # 顺序写盘（fMP4：使用 init 的分片前置 init 段；dedupe_init 已去重）
        with open(self.out_path, "wb") as fh:
            for data, seg in zip(results, self.segments):
                if seg.init is not None:
                    fh.write(self._load_init(seg.init))
                fh.write(data)
        return time.time() - t0, total


def dedupe_init(segments):
    """fMP4 去重：同一轨道 MAP 不变时只让「首个使用某 init 的分片」携带 init，
    后续相同 init 置空（与 cat-catch 逻辑一致：每个分片都拼 MAP 会坏）。

    若后续分片换了 MAP（init URL/BYTERANGE 变化），新 init 仍会前置。
    就地修改并返回 segments。
    """
    seen = set()
    for seg in segments:
        if seg.init is None:
            continue
        if seg.init in seen:
            seg.init = None
        else:
            seen.add(seg.init)
    return segments


# ----------------------------- 选轨 -----------------------------

def pick_variant(variants, quality="best"):
    """按 --quality 选视频变体。

    best -> 带宽最高的变体；
    数字 -> 高度 <= 该值的变体里带宽最高；无满足项时退回全体取带宽最高。
    """
    if not variants:
        raise HlsError("master 里没有可解析的 EXT-X-STREAM-INF 变体")
    if quality == "best":
        return max(variants, key=lambda v: (v["bandwidth"], v["height"] or 0))
    try:
        limit = int(quality)
    except ValueError:
        raise HlsError("--quality 需要 best 或高度数字，收到 %r" % quality)
    eligible = [v for v in variants if (v["height"] or 0) > 0 and v["height"] <= limit]
    if not eligible:
        eligible = variants
    return max(eligible, key=lambda v: (v["bandwidth"], v["height"] or 0))


def pick_audio_track(track_urls, video_duration, client):
    """从多条音频 rendition 中选出要下载的那条。

    规则：优先时长最接近视频轨（误差 <10s 视为并列）；并列时按
    LANGUAGE（zh/zho/cmn/yue 优先）> DEFAULT=YES > 第一个。
    返回 (选中信息 dict, 人类可读原因, 选中的 Playlist)。
    """
    cands = []
    for idx, url in enumerate(track_urls):
        try:
            text, _ = client.get_text(url)
            pl = parse_playlist(text, url)
            dur = pl.total_duration
            if dur <= 0:
                continue
            cands.append({"idx": idx, "url": url, "duration": dur,
                          "segments": len(pl.segments), "playlist": pl})
        except Exception as exc:  # noqa: BLE001 单条音轨解析失败不致命
            log("[hls] 音频轨 %s 解析失败，跳过: %s" % (url[:120], exc))
    if not cands:
        raise HlsError("没有可解析的音频 rendition")

    def dur_rank(c):
        return abs(c["duration"] - video_duration)

    best_diff = min(dur_rank(c) for c in cands)
    close = [c for c in cands if dur_rank(c) <= max(10.0, best_diff)]

    def sort_key(c):
        lang = (c.get("language") or "").lower()
        zh = 0 if lang in ZH_LANGS else 2
        dflt = 0 if c.get("is_default") else 1
        return (dur_rank(c), zh, dflt, c["idx"])

    close.sort(key=sort_key)
    chosen = close[0]
    info = {
        "url": chosen["url"],
        "duration": round(chosen["duration"], 2),
        "language": chosen.get("language") or "-",
        "name": chosen.get("name") or "-",
    }
    reason = "时长最接近视频轨（视频 %.1fs / 该轨 %.1fs，差 %.1fs）" % (
        video_duration, chosen["duration"], dur_rank(chosen))
    if len(close) > 1:
        reason += "；并列 %d 条，按 语言(zh 优先)>DEFAULT>顺序 选出 %r（lang=%s default=%s）" % (
            len(close), info["name"], info["language"], chosen.get("is_default"))
    return info, reason, chosen["playlist"]


# ----------------------------- 合并 / 容器判定 -----------------------------

def decide_container(vcodec, acodec, is_pure_audio, input_ext):
    """按规格第 2 节判定输出容器：

    H.264/AVC + AAC -> .mp4；其它（HEVC/AV1/opus 等）-> .mkv；
    纯音频（无视频轨）-> 保持原扩展名（.m4a/.aac/.mp3）。
    """
    if is_pure_audio:
        if input_ext in (".aac", ".mp3"):
            return input_ext
        return ".m4a"
    v = (vcodec or "").lower()
    a = (acodec or "").lower()
    if v in ("h264",) and (a in ("aac", "mp3", "ac3", "eac3") or not a):
        return ".mp4"
    return ".mkv"


def probe_codecs(path):
    """ffprobe 读取首个视频/音频流的 codec_name，返回 (vcodec, acodec)。"""
    code, out, _ = run_cmd(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        check=False)
    if code != 0:
        return None, None
    try:
        info = json.loads(out)
    except ValueError:
        return None, None
    vc = ac = None
    for st in info.get("streams") or []:
        ct = st.get("codec_type")
        if ct == "video" and vc is None:
            vc = st.get("codec_name")
        elif ct == "audio" and ac is None:
            ac = st.get("codec_name")
    return vc, ac


def merge_tracks(video_file, audio_file, out_path, ffmpeg_log, audio_is_ts):
    """ffmpeg -c copy 合并视频轨与独立音频轨。

    音频是 MPEG-TS 封装时加 -bsf:a aac_adtstoasc（AAC in ADTS -> ASC 写 mp4）。
    """
    ext = os.path.splitext(out_path)[1].lstrip(".")
    cmd = ["ffmpeg", "-y", "-v", "warning",
           "-i", video_file, "-i", audio_file]
    if audio_is_ts:
        cmd += ["-bsf:a", "aac_adtstoasc"]
    cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c", "copy"]
    if ext == "mp4":
        cmd += ["-movflags", "+faststart"]
    cmd += ["-f", ext, out_path]
    log("[hls] 合并: %s" % " ".join(cmd))
    run_cmd(cmd, log_path=ffmpeg_log)


def remux_to_container(src, dst, faststart=True):
    """把中间 ts/m4s 拼接文件 remux 到最终容器（-c copy）。"""
    ext = os.path.splitext(dst)[1].lstrip(".")
    cmd = ["ffmpeg", "-y", "-v", "warning", "-i", src, "-c", "copy"]
    if ext == "mp4" and faststart:
        cmd += ["-movflags", "+faststart"]
    cmd += ["-f", ext, dst]
    run_cmd(cmd)


# ----------------------------- 工具 -----------------------------

def _name_from_url(url):
    """从 URL 末段推断文件名（去扩展名、去签名参数、只留安全字符）。"""
    path = url.split("?", 1)[0]
    name = os.path.basename(path) or "video"
    name = os.path.splitext(name)[0]
    name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", name)[:80]
    return name or "video"


def _looks_like_file(path):
    """--out 是否像一个具体文件路径（带媒体扩展名）。

    只有常见媒体扩展名才按「完整文件路径」处理（覆盖写该路径）；
    其它情况一律按目录处理并走 unique_path 重名保护，避免误覆盖。
    """
    if not path:
        return False
    ext = os.path.splitext(path)[1].lower()
    return ext in (".mp4", ".mkv", ".ts", ".m4a", ".aac", ".mp3",
                   ".flac", ".webm")


def _move(src, dst):
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    shutil.move(src, dst)


def _guess_track_ext(playlist):
    """根据播放列表特征猜中间文件扩展名：fMP4（有 EXT-X-MAP）-> .m4s，否则 .ts。"""
    if playlist.segments and playlist.segments[0].init:
        return ".m4s"
    return ".ts"


def _is_audio_only_variant(variant):
    """根据变体 CODECS 判断是否纯音频轨（无任何视频编码前缀）。"""
    if not variant:
        return False
    codecs = (variant.get("codecs") or "").lower()
    if not codecs:
        return False
    video_prefixes = ("avc", "hvc", "hevc", "hev", "av01", "vp8", "vp9", "dva")
    return not any(c.startswith(video_prefixes) for c in codecs.split(","))


def _progress_factory(label):
    """进度回调：每 log_every 个分片写一行 stderr（不占 stdout）。"""
    def cb(done, total, elapsed):
        pct = 100.0 * done / total if total else 0.0
        spd = done / elapsed if elapsed > 0.01 else 0.0
        log("[hls][%s] %d/%d 分片 (%.1f%%, %.1f 片/s)"
            % (label, done, total, pct, spd))
    return cb


# ----------------------------- 主流程 -----------------------------

def run_download(args):
    """hls 下载主流程，返回统一 JSON dict。

    步骤：拉 m3u8 -> master 选清晰度/音频轨 -> 下视频轨（解密）
    -> （如有）下音频轨 -> ffmpeg 合并或 remux -> ffprobe 摘要 -> JSON。
    """
    t0 = time.time()
    client = HttpClient(headers=headers_from_args(
        args, referer=args.referer, cookie=args.cookie, ua=args.user_agent),
        timeout=args.timeout, retries=1)
    # 分片级重试统一交给 SegmentDownloader；playlist/key 由 HttpClient 单次请求

    url = args.url
    text, _ = client.get_text(url)
    pl = parse_playlist(text, url)
    log("[hls] 解析 %s: %s" % (url[:120], "master" if pl.is_master else "media"))

    video_playlist = None
    audio_url = None
    audio_track_info = None
    chosen_variant = None

    if pl.is_master:
        chosen_variant = pick_variant(pl.variants, args.quality)
        log("[hls] 选中变体 %s: %sx%s %d kbps codecs=%s" % (
            chosen_variant.get("name") or (chosen_variant["uri"] or "")[:60],
            chosen_variant["width"] or "?", chosen_variant["height"] or "?",
            chosen_variant["bandwidth"] // 1000, chosen_variant["codecs"]))
        v_url = chosen_variant["uri"]
        vtext, _ = client.get_text(v_url)
        video_playlist = parse_playlist(vtext, v_url)
        log("[hls] 视频轨 %s: %d 分片 总时长 %.1fs 加密=%s" % (
            v_url[:100], len(video_playlist.segments),
            video_playlist.total_duration, video_playlist.encrypted))
        # 音频 rendition：变体声明了 AUDIO group 且组内有带 URI 的轨，
        # 就单独下载音频轨并合并（组内 1 条直接用，多条按规则选择）
        group = chosen_variant.get("audio")
        tracks = pl.audio_groups.get(group or "", [])
        if group and tracks:
            infos, reason, _chosen_pl = pick_audio_track(
                [t["uri"] for t in tracks],
                video_playlist.total_duration, client)
            for t in tracks:
                if t["uri"] == infos["url"]:
                    infos["name"] = t.get("name") or infos["name"]
                    infos["language"] = t.get("language") or infos["language"]
                    infos["channels"] = t.get("channels") or ""
                    break
            audio_url = infos["url"]
            audio_track_info = infos
            # 必须打印实际选择了哪条音频轨（NAME/LANGUAGE/时长/声道）
            log("[hls] 选中音频轨 NAME=%s LANGUAGE=%s 时长=%.1fs "
                "CHANNELS=%s（%s）" % (infos["name"], infos["language"],
                                       infos["duration"],
                                       infos.get("channels", "?"), reason))
        else:
            log("[hls] 变体未声明独立音频 rendition，使用视频轨自带音频")
    else:
        video_playlist = pl
        log("[hls] 直接 media playlist: %d 分片 总时长 %.1fs 加密=%s" % (
            len(video_playlist.segments), video_playlist.total_duration,
            video_playlist.encrypted))

    segments = video_playlist.segments
    if args.max_segments and args.max_segments > 0:
        segments = segments[:args.max_segments]
        log("[hls] --max-segments 截断到前 %d 个分片" % len(segments))
    if not segments:
        raise HlsError("没有分片可下载")

    workdir = tmp_subdir("hls")
    keep_ts = args.keep_ts
    out_is_file = _looks_like_file(args.out)
    if not out_is_file:
        os.makedirs(args.out, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    base_name = args.name or _name_from_url(url)

    # ---- 视频轨 ----
    v_ext = _guess_track_ext(video_playlist)
    v_tmp = os.path.join(workdir, "video" + v_ext)
    dedupe_init(segments)
    log("[hls] 开始下载视频轨 %d 分片 -> %s" % (len(segments), v_tmp))
    dl = SegmentDownloader(client, segments, v_tmp,
                           concurrency=args.concurrency,
                           progress_cb=_progress_factory("video"))
    dl.run()

    is_pure_audio = _is_audio_only_variant(chosen_variant)

    # ---- 音频轨（可选）----
    a_tmp = None
    if audio_url:
        atext, _ = client.get_text(audio_url)
        apl = parse_playlist(atext, audio_url)
        a_segments = apl.segments
        if args.max_segments and args.max_segments > 0:
            a_segments = a_segments[:args.max_segments]
        dedupe_init(a_segments)
        a_ext = _guess_track_ext(apl)
        a_tmp = os.path.join(workdir, "audio" + a_ext)
        log("[hls] 开始下载音频轨 %d 分片 -> %s" % (len(a_segments), a_tmp))
        adl = SegmentDownloader(client, a_segments, a_tmp,
                                concurrency=args.concurrency,
                                progress_cb=_progress_factory("audio"))
        adl.run()

    # ---- 容器判定与输出 ----
    vc, ac = probe_codecs(v_tmp)
    log("[hls] 视频轨探测: vcodec=%s acodec=%s" % (vc, ac))
    # 兜底：直接 media playlist（无 master/CODECS 信息）时靠探测结果判断纯音频
    if vc is None and ac is not None:
        is_pure_audio = True
        log("[hls] 探测到无视频流，按纯音频流处理")
    ext = decide_container(vc, ac, is_pure_audio, v_ext)
    if out_is_file:
        # --out 是完整文件路径：同样走 unique_path 避免覆盖已有产物
        # （不存在时返回原路径；存在则自动 -2/-3）
        stem = args.name or _name_from_url(url)
        out_file = unique_path(os.path.dirname(os.path.abspath(args.out)), stem, ext)
    else:
        out_file = unique_path(args.out, base_name, ext)
    tmp_out = os.path.join(workdir, "final" + ext)

    if a_tmp:
        # 音视频分离 -> ffmpeg -c copy 合并
        audio_is_ts = a_tmp.endswith(".ts")
        merge_tracks(v_tmp, a_tmp, tmp_out, os.path.join(workdir, "ffmpeg.log"),
                     audio_is_ts)
        _move(tmp_out, out_file)
    elif is_pure_audio:
        # 纯音频：ts 封装 remux 到 .aac（adts），m4s remux 到 .m4a
        if v_tmp.endswith(".ts"):
            final = os.path.join(workdir, "pure.aac")
            run_cmd(["ffmpeg", "-y", "-v", "warning", "-i", v_tmp, "-c", "copy",
                     "-f", "adts", final])
            if not out_is_file:
                out_file = unique_path(args.out, base_name, ".aac")
            _move(final, out_file)
        else:
            remux_to_container(v_tmp, tmp_out)
            _move(tmp_out, out_file)
    else:
        remux_to_container(v_tmp, tmp_out)
        _move(tmp_out, out_file)

    # ---- 清理中间文件 ----
    if not keep_ts:
        for f in os.listdir(workdir):
            p = os.path.join(workdir, f)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
    else:
        log("[hls] --keep-ts 保留中间文件目录: %s" % workdir)

    elapsed = round(time.time() - t0, 2)
    summary = media_summary(out_file)
    result = {
        "ok": True,
        "file": out_file,
        "size": summary.get("size"),
        "duration": summary.get("duration"),
        "resolution": summary.get("resolution"),
        "vcodec": summary.get("vcodec"),
        "acodec": summary.get("acodec"),
        "encrypted": video_playlist.encrypted,
        "segments": len(segments),
        "elapsed": elapsed,
        "mediaFormat": os.path.splitext(out_file)[1].lstrip("."),
    }
    if audio_track_info:
        result["audioTrack"] = audio_track_info
    return result


def build_parser():
    p = argparse.ArgumentParser(description="HLS(m3u8) 下载器（video-sniff）")
    p.add_argument("--url", required=True, help="m3u8 地址（master 或 media）")
    p.add_argument("--out", required=True, help="输出目录或文件路径")
    p.add_argument("--referer", default=None, help="Referer 头")
    p.add_argument("--cookie", default=None, help="Cookie 头")
    p.add_argument("--user-agent", default=None, help="User-Agent 头")
    p.add_argument("--header", action="append", default=[],
                   help="附加请求头 'K: V'，可多次传入")
    p.add_argument("--quality", default="best",
                   help="清晰度：best 或高度上限数字（如 1080/720）")
    p.add_argument("--concurrency", type=int, default=16, help="并发线程数（默认 16）")
    p.add_argument("--keep-ts", action="store_true", help="保留中间拼接文件")
    p.add_argument("--name", default=None, help="输出文件名（不带扩展名）")
    p.add_argument("--timeout", type=int, default=20, help="单请求超时（秒）")
    p.add_argument("--json", action="store_true", help="stdout 只输出一行 JSON")
    p.add_argument("--max-segments", type=int, default=0,
                   help="内部参数：只下载前 N 个分片（测试用）")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = None
    try:
        result = run_download(args)
    except HlsError as exc:
        log("[hls] 失败: %s" % exc)
        result = {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 兜底，保证 JSON 契约
        import traceback
        log("[hls] 未预期异常: %s\n%s" % (exc, traceback.format_exc()))
        result = {"ok": False, "error": "未预期异常: %s" % exc}
    emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
