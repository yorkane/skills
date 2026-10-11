#!/usr/bin/env python3
"""文件名规范化：clean_title / pick_title / unique_path。

约定（见 doc/skill-spec.md 第 4 节）：
- 禁止空名；去除反斜杠、正斜杠、冒号、星号、双引号、尖括号、竖线
  与所有不可见/控制字符（含零宽字符、BOM）；
- 保留全角可显示字符（中文、，。《》 等全角标点）；
- 压缩连续空白（含全角空格）为单个空格；
- 去掉首尾的点（含全角点）与空格；长度上限 120 字符，截断后再清理首尾；
- 标题回退：pageTitle（去站点名后缀）→ ogTitle → 描述首句（≤60 字）
  → URL 末段（finalUrl 优先，去扩展名与纯 ID 数字段）→ "video"；
- 重名自动加 -2、-3 后缀。

只依赖标准库，可被 cli.py 直接 import vsniff_lib.naming 使用。
"""

import os
import re
import unicodedata
import urllib.parse

MAX_LEN = 120        # 标题长度上限（按字符数）
DESC_MAX = 60        # 描述首句长度上限（字）
SUFFIX_MAX = 12      # 可去除的「站点名后缀」最大字符数

_BAD_CHARS = frozenset('\\/:*?"<>|')
_WS = re.compile(r"\s+")
# 首尾要剥掉的点（含全角点）与空格
_EDGE_CHARS = " .。．…·•"
# 描述首句：截到第一个句号/问号/感叹号/换行（含中文标点）
_SENT_SPLIT = re.compile(r"[。？！?!\n]")
# 「正文 - 站点名」的后缀分隔符（取最后一次出现，站点名在末尾）
_SEP = re.compile(r"[-_|｜–—]")
_PURE_DIGITS = re.compile(r"^\d+$")
# 后缀里出现这些媒体相关词时，认为不是站点名，不去后缀
_MEDIA_WORDS = (
    "视频", "影视", "影院", "在线播放", "在线观看", "高清", "超清", "蓝光", "下载",
    "m3u8", "mp4", "电影", "剧集", "预告片", "电视剧", "综艺", "纪录片",
)


def clean_title(text):
    """安全化标题：去非法/不可见字符、压缩空白、去首尾点与空格、截断 120；空返回 ''。

    - 去除反斜杠/正斜杠/冒号/星号/引号/尖括号/竖线，以及所有 Unicode
      C 类字符（Cc/Cf/Cs/Co/Cn，含控制字符、零宽字符、BOM、私用区、
      未分配码位）；
    - 保留全角可显示字符（中文、，。《》 等）；
    - 连续空白（含全角空格 U+3000）压缩为单个空格；
    - 去掉首尾的点（含全角点）与空格；
    - 超过 120 字符截断后，再清理一次首尾点/空格。
    """
    if text is None:
        return ""
    t = str(text)
    out = []
    for ch in t:
        if ch in _BAD_CHARS:
            continue
        if unicodedata.category(ch)[0] == "C":
            continue
        out.append(ch)
    t = "".join(out)
    t = _WS.sub(" ", t)
    t = t.strip(_EDGE_CHARS).strip()
    if len(t) > MAX_LEN:
        t = t[:MAX_LEN].rstrip(_EDGE_CHARS).rstrip()
    return t


def _host_label(url):
    """从 URL 取域名第一个有效 label（去 www/m/wap/mobile），取不到返回 None。"""
    if not url:
        return None
    try:
        host = urllib.parse.urlsplit(str(url)).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower().strip(".")
    labels = [l for l in host.split(".") if l and l not in ("www", "m", "wap", "mobile")]
    return labels[0] if labels else None


def _host_ok(suffix, url):
    """后缀与 host 的域名片段匹配校验。

    拿不到 host、后缀含中文（拼音/关键词匹配不可靠）或后缀无可比对 ASCII
    片段时，退化为仅用「≤12 字且无媒体词」条件；仅当后缀是纯 ASCII 且
    host 可用时才要求包含关系。
    """
    if not suffix:
        return True
    if any("\u4e00" <= c <= "\u9fff" for c in suffix):
        return True
    label = _host_label(url)
    if not label:
        return True
    ascii_part = re.sub(r"[^a-z0-9]", "", suffix.lower())
    if not ascii_part:
        return True
    return label in ascii_part or ascii_part in label


def _strip_site_suffix(title, url):
    """pageTitle 去站点名后缀：「正文 - 站名」/「正文_站名」/「正文 | 站名」。

    条件：后缀 ≤12 字、不含媒体相关词、且通过 host 校验；
    不满足任一条时原样返回（正文为空时同样不去）。
    """
    if not title:
        return title
    m = None
    for m in _SEP.finditer(title):
        pass  # 取最后一次出现的分隔符：站点名在标题末尾
    if m is None:
        return title
    body = title[:m.start()].strip(" \t\u00a0\u3000")
    suffix = title[m.end():].strip(" \t\u00a0\u3000")
    if not body or not suffix or len(suffix) > SUFFIX_MAX:
        return title
    low = suffix.lower()
    if any(w in low for w in _MEDIA_WORDS):
        return title
    if not _host_ok(suffix, url):
        return title
    return body


def _first_sentence(desc):
    """描述首句：截到第一个句号/问号/感叹号/换行（含中文标点），上限 60 字。"""
    if not desc:
        return ""
    s = str(desc)
    m = _SENT_SPLIT.search(s)
    if m and m.start() > 0:
        s = s[:m.start()]
    s = s.strip()
    if len(s) > DESC_MAX:
        s = s[:DESC_MAX]
    return s


def _url_stem(url):
    """URL 末段：去扩展名、去纯 ID 数字段；取不到返回 ''。"""
    if not url:
        return ""
    try:
        path = urllib.parse.urlsplit(str(url)).path
    except ValueError:
        return ""
    base = os.path.basename(path)
    stem, _ext = os.path.splitext(base)
    stem = stem.strip()
    if not stem or _PURE_DIGITS.match(stem):
        return ""
    return stem


def pick_title(meta):
    """从嗅探报告 meta 里挑标题（未做重名处理的纯标题串）。

    回退顺序：pageTitle（去站点名后缀）→ ogTitle → 描述首句
    （ogDescription → description）→ URL 末段（finalUrl → pageUrl）→ "video"。
    每一步候选先过 clean_title，为空则回退下一步。
    """
    meta = meta or {}
    url = meta.get("finalUrl") or meta.get("pageUrl")
    pt = meta.get("pageTitle")
    if pt:
        t = clean_title(_strip_site_suffix(str(pt), url))
        if not t:
            t = clean_title(pt)
        if t:
            return t
    t = clean_title(meta.get("ogTitle"))
    if t:
        return t
    for key in ("ogDescription", "description"):
        t = clean_title(_first_sentence(meta.get(key)))
        if t:
            return t
    for key in ("finalUrl", "pageUrl"):
        t = clean_title(_url_stem(meta.get(key)))
        if t:
            return t
    return "video"


def unique_path(directory, stem, ext):
    """返回目录下不与已有文件冲突的完整路径（含扩展名），冲突时加 -2/-3。

    - ext 形如 ".mp4"，调用方可能传 ""；
    - directory 不存在时自动创建；
    - 空 stem 兜底为 "video"（禁止空名）。
    """
    if directory:
        os.makedirs(directory, exist_ok=True)
    stem = (stem or "").strip() or "video"
    ext = (ext or "").strip()
    if ext and not ext.startswith("."):
        ext = "." + ext
    cand = os.path.join(directory, stem + ext)
    n = 2
    while os.path.exists(cand):
        cand = os.path.join(directory, "%s-%d%s" % (stem, n, ext))
        n += 1
    return cand


if __name__ == "__main__":
    # 自测入口：打印几个典型用例结果
    import tempfile

    demos = [
        "电影《某某》在线播放 - XX影视",
        "某部剧 第5集 - 小站名",
        'a/b:c*d?"<>|e',
        " 带制表符 与全角空格的标题..",
        "零宽\u200b与BOM\ufeff标题",
        "长" * 150,
        "",
        None,
    ]
    for d in demos:
        print("clean_title: %r -> %r" % (d, clean_title(d)))

    meta = {
        "pageTitle": "电影《某某》在线播放 - XX影视",
        "finalUrl": "https://www.ymovie.com/v/98765",
    }
    print("pick_title(后缀含媒体词影视,不去):", pick_title(meta))
    meta2 = {
        "pageTitle": "某部剧 第5集 - 小站名",
        "finalUrl": "https://www.xiaozhan.com/v/123",
    }
    print("pick_title(去站点后缀):", pick_title(meta2))
    print("pick_title(空 meta):", pick_title({}))
    print("pick_title(纯 ID URL):", pick_title({"pageUrl": "https://x.com/v/12345/"}))

    d = tempfile.mkdtemp(prefix="vsniff-naming-")
    p1 = unique_path(d, "测试", ".mp4")
    open(p1, "w").close()
    p2 = unique_path(d, "测试", ".mp4")
    print("unique_path 首次:", p1)
    print("unique_path 重名:", p2)

