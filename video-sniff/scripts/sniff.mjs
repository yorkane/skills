#!/usr/bin/env node
// video-sniff 嗅探器：用 playwright-core 驱动浏览器，监听网络 + 页面内脚本，
// 自动发现页面里的 hls/dash/file 媒体候选并输出结构化 JSON 报告。
// 用法见 doc/skill-spec.md 第 1 节。只依赖全局 @playwright/cli 自带的 playwright-core。

import { createRequire } from 'module';
import fs from 'node:fs';
import path from 'node:path';

// 从全局 @playwright/cli 里 require playwright-core（禁止 npm install）
const req = createRequire('/home/aigc/.nvm/versions/node/v24.20.0/lib/node_modules/@playwright/cli/node_modules/');
const pw = req('playwright-core');

// ---------- 参数解析 ----------
function parseArgs(argv) {
  const a = {
    url: null, cdp: null, launch: false, out: null, seconds: 25,
    headed: false, clickPlay: true, userDataDir: null, mobile: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    switch (x) {
      case '--url': a.url = argv[++i]; break;
      case '--cdp': a.cdp = argv[++i]; break;
      case '--launch': a.launch = true; break;
      case '--out': a.out = argv[++i]; break;
      case '--seconds': a.seconds = Number(argv[++i]) || 25; break;
      case '--headed': a.headed = true; break;
      case '--click-play': a.clickPlay = true; break;
      case '--no-click-play': a.clickPlay = false; break;
      case '--user-data-dir': a.userDataDir = argv[++i]; break;
      case '--mobile': a.mobile = true; break;
      default:
        process.stderr.write(`[sniff] 未知参数: ${x}\n`);
    }
  }
  if (!a.url) {
    process.stderr.write('用法: node sniff.mjs --url <page> [--cdp <endpoint>] [--out <json>] [--seconds 25] [--headed] [--mobile] [--user-data-dir <dir>]\n'
      + '  （未指定方案时默认用 Playwright 启动浏览器；--launch 为同一默认值的显式写法）\n');
    process.exit(2);
  }
  return a;
}

const args = parseArgs(process.argv.slice(2));
const DEFAULT_CDP = 'http://127.0.0.1:9222';

// ---------- 媒体判定集合（照抄 cat-catch/js/init.js 的 Ext 与 Type 列表） ----------
// cat-catch Ext 列表（去掉字幕类 srt/vtt，ts 单独视为分片）
const MEDIA_EXTS = new Set([
  'flv','hlv','f4v','mp4','mp3','wma','wav','m4a','ts','webm','ogg','ogv',
  'acc','mov','mkv','m4s','mpeg','avi','wmv','asf','movie','divx','mpeg4',
  'vid','aac','weba','opus',
]);
// cat-catch Type 列表（content-type 前缀/全等匹配）
const MEDIA_TYPES = [
  'audio/', 'video/',
  'application/ogg', 'application/vnd.apple.mpegurl', 'application/x-mpegurl',
  'application/mpegurl', 'application/octet-stream-m3u8',
  'application/dash+xml', 'application/m4s',
];
// 分片类扩展：单片不作为候选（除非整页只有分片）
const SEGMENT_EXTS = new Set(['ts','m4s','aac','acc']);
// 纯音频扩展（低分候选）
const AUDIO_EXTS = new Set(['mp3','m4a','aac','opus','weba','wma','wav']);
// 常见广告/埋点特征
const AD_PATTERNS = /doubleclick|googlesyndication|analytics|beacon|tracker|\/ad\//i;

function extOf(url) {
  try {
    const p = new URL(url).pathname;
    const m = p.match(/\.([a-z0-9]{2,5})$/i);
    return m ? m[1].toLowerCase() : '';
  } catch { return ''; }
}

// 判定 kind: 'hls' | 'dash' | 'file' | null（不是媒体）
function classify(url, contentType) {
  const ct = (contentType || '').toLowerCase();
  let u;
  try { u = url.toLowerCase(); } catch { return null; }
  const ext = extOf(url);
  // hls：路径/查询含 .m3u8/.m3u，或 content-type 含 mpegurl
  if (/\.m3u8?(\?|&|$)/.test(u) || ct.includes('mpegurl')) return 'hls';
  // dash：.mpd 或 content-type application/dash+xml
  if (/\.mpd(\?|&|$)/.test(u) || ct === 'application/dash+xml') return 'dash';
  // file：content-type 以 video/ 或 audio/ 开头，或扩展名在媒体集合内
  if (MEDIA_TYPES.some(t => ct.startsWith(t.replace('/*','/')) && !t.endsWith('/x-mpegurl'))) {
    if (ct.startsWith('video/') || ct.startsWith('audio/')) return 'file';
  }
  if (MEDIA_TYPES.some(t => ct === t)) return 'file';
  if (ext && MEDIA_EXTS.has(ext)) return 'file';
  return null;
}

// ---------- 小工具 ----------
function logErr(msg) { process.stderr.write(msg + '\n'); }
function hostOf(url) { try { return new URL(url).hostname; } catch { return ''; } }
function sameDomain(url, pageUrl) {
  const h = hostOf(url), p = hostOf(pageUrl);
  if (!h || !p) return false;
  return h === p || h.endsWith('.' + p) || p.endsWith('.' + h);
}
function slugOf(url) {
  const s = url.replace(/^https?:\/\//, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '').slice(0, 60);
  return s || 'page';
}

// ---------- 播放列表轻量分析 ----------
// 拉取 playlist 文本（≤64KB）并解析 hls/dash 字段；失败返回 {ok:false,...}
async function analyzePlaylist(context, url, refPageUrl, cookieStr) {
  const out = { ok: false };
  let text = null;
  const headers = { Referer: refPageUrl };
  if (cookieStr) headers['Cookie'] = cookieStr;
  try {
    // 优先用浏览器上下文内的 request（共享代理/环境）
    const resp = await context.request.get(url, { headers, timeout: 12000 });
    if (resp.ok()) {
      text = (await resp.text()).slice(0, 65536);
    }
  } catch {}
  if (text == null) {
    try {
      const r = await fetch(url, { headers, signal: AbortSignal.timeout(12000) });
      if (r.ok()) text = (await r.text()).slice(0, 65536);
    } catch {}
  }
  if (text == null) {
    return { ok: false, note: 'playlist 拉取失败（网络/鉴权/大小）' };
  }
  // HLS 解析
  if (/^#EXTM3U/m.test(text)) {
    const lines = text.split(/\r?\n/);
    const streamInfs = lines.filter(l => l.startsWith('#EXT-X-STREAM-INF'));
    const extInfs = lines.filter(l => l.startsWith('#EXTINF:'));
    const isMaster = streamInfs.length > 0;
    let maxHeight = null;
    for (const l of streamInfs) {
      const m = l.match(/RESOLUTION="?(\d+)x(\d+)"?/);
      if (m) { maxHeight = Math.max(maxHeight || 0, Number(m[2])); continue; }
    }
    // 从 EXT-X-MAP / 首段也尝试取高度（media playlist 无 RESOLUTION 时）
    let keyMethod = 'NONE';
    for (const l of lines) {
      const m = l.match(/^#EXT-X-KEY:.*?METHOD=([A-Z0-9-]+)/);
      if (m && m[1] !== 'NONE') { keyMethod = m[1]; break; }
      if (m && m[1] === 'NONE') keyMethod = 'NONE';
    }
    // 独立音频组：master 里的 EXT-X-MEDIA:TYPE=AUDIO
    const audioGroup = lines.some(l => l.startsWith('#EXT-X-MEDIA:') && /TYPE=AUDIO/.test(l));
    // 估算总时长
    let duration = 0;
    for (const l of extInfs) {
      const m = l.match(/^#EXTINF:\s*([0-9.]+),/);
      if (m) duration += Number(m[1]);
    }
    return {
      ok: true, master: isMaster, variants: streamInfs.length,
      maxHeight, audioGroup, encrypted: keyMethod,
      segments: extInfs.length, duration: Math.round(duration * 10) / 10 || null,
      note: isMaster ? 'master 播放列表' : 'media 播放列表',
    };
  }
  // DASH 解析（轻量：取最大视频 height 与段模板信息）
  if (/<MPD[\s>]/i.test(text)) {
    const heights = [...text.matchAll(/height="([0-9]+)"/g)].map(m => Number(m[1]));
    const maxHeight = heights.length ? Math.max(...heights) : null;
    const hasAudio = /<Audio[^>]*>/i.test(text);
    const segments = (text.match(/\/?(SegmentTemplate|SegmentList|SegmentBase)/g) || []).length;
    const durM = text.match(/duration="PT?([0-9HMS.]+)"/i);
    return {
      ok: true, master: true, variants: 0,
      maxHeight, audioGroup: hasAudio, encrypted: null,
      segments, duration: null,
      note: 'DASH MPD' + (durM ? ' duration=' + durM[1] : ''),
    };
  }
  return { ok: false, note: '非 m3u8/mpd 内容（前 64KB）' };
}

// ---------- 主流程 ----------
async function main() {
  const t0 = performance.now(); // 单调钟，避免 VM 时钟跳变导致 elapsedSec 失真
  let browser = null, context = null, page = null;
  let mode = 'launch';

  const mobileUA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148';
  const ctxOpts = args.mobile
    ? { userAgent: mobileUA, viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 3 }
    : { viewport: { width: 1366, height: 900 } };

  // 模式判定（skill 硬性约束）：未指定方案时默认用 Playwright 自起浏览器；
  // 只有显式 --cdp 才附着调试端口 —— 不再默认探测 9222，避免误附着到无关浏览器，
  // 也避免绕过浏览器渲染与网络嗅探去直接取页面。
  let cdpEndpoint = args.cdp;
  if (!args.cdp && !args.launch) {
    logErr('[sniff] 未指定方案：默认用 Playwright 启动浏览器（要附着已有 Chrome 请显式 --cdp ' + DEFAULT_CDP + '）');
  }

  if (cdpEndpoint) {
    mode = 'cdp';
    try {
      browser = await pw.chromium.connectOverCDP(cdpEndpoint, { timeout: 10000 });
    } catch (e) {
      if (args.cdp) { // 显式 --cdp 失败不降级，直接报错
        logErr('[sniff] CDP 连接失败: ' + e.message);
        process.exit(1);
      }
      cdpEndpoint = null; mode = 'launch';
    }
    if (cdpEndpoint) {
      const existing = browser.contexts();
      // 默认复用默认上下文（含登录态）；--mobile 需要独立上下文才能注入 UA
      context = (existing.length && !args.mobile) ? existing[0] : await browser.newContext(ctxOpts);
    }
  }
  if (!cdpEndpoint) {
    mode = 'launch';
    browser = await pw.chromium.launch({
      headless: !args.headed,
      args: ['--no-sandbox'],
    });
    context = await browser.newContext({ ...ctxOpts, ...(args.userDataDir ? { } : {}) });
    if (args.userDataDir) {
      // 需要持久化登录态时用 persistent context 重开
      await context.close();
      browser = await browser.close();
      context = await pw.chromium.launchPersistentContext(args.userDataDir, {
        headless: !args.headed,
        args: ['--no-sandbox'],
        ...ctxOpts,
      });
    }
  }

  // 候选收集
  const candidates = new Map(); // url -> rec
  let reqCounter = 0;
  const pageHost = hostOf(args.url);

  function addCandidate(url, info) {
    if (!url || !/^https?:/i.test(url)) return;
    const kind = classify(url, info.contentType);
    if (!kind) return;
    if (candidates.has(url)) {
      // 补全缺失信息
      const old = candidates.get(url);
      if (old.contentType == null && info.contentType) old.contentType = info.contentType;
      if (old.contentLength == null && info.contentLength != null) old.contentLength = info.contentLength;
      if (!old.referer && info.referer) old.referer = info.referer;
      return;
    }
    candidates.set(url, {
      kind, url,
      contentType: info.contentType || null,
      contentLength: info.contentLength != null ? info.contentLength : null,
      ext: extOf(url) || null,
      referer: info.referer || null,
      order: ++reqCounter,
      hls: null,
      note: null,
    });
  }

  page = await context.newPage();
  page.setDefaultTimeout(30000);

  // 监听网络
  page.on('response', async (resp) => {
    try {
      const u = resp.url();
      const ct = resp.headers()['content-type'] || '';
      let cl = resp.headers()['content-length'];
      cl = cl != null ? Number(cl) : null;
      const req = resp.request();
      const ref = (req && req.headers()['referer']) || null;
      addCandidate(u, { contentType: ct, contentLength: cl, referer: ref });
      // hls/dash 分片对应的 playlist 有时在 JS 变量里，这里同时抓 performance（周期性）
    } catch {}
  });
  // 只用于抓请求头（Referer/Origin），响应信息以 response 事件为准
  const reqHeaders = new Map(); // url -> {referer, origin, cookie}
  page.on('request', (r) => {
    try {
      const h = r.headers();
      if (!reqHeaders.has(r.url())) {
        reqHeaders.set(r.url(), {
          referer: h['referer'] || null,
          origin: h['origin'] || null,
          cookie: h['cookie'] || null,
        });
      }
    } catch {}
  });

  // 页面内脚本补充：resource timing + video/audio 元素 + 页面内联 JSON/JS 兜底
  const collectFromPage = async () => {
    try {
      const data = await page.evaluate(() => {
        const found = new Set();
        // 1) performance resource timing
        try { for (const e of performance.getEntriesByType('resource')) found.add(e.name); } catch (e) {}
        // 2) video/audio 元素与 source 标签（blob: 是 MSE 流，真实源走网络嗅探或内联 JSON）
        for (const el of document.querySelectorAll('video,audio')) {
          if (el.src) found.add(el.src);
          for (const s of el.querySelectorAll('source')) if (s.src) found.add(s.src);
        }
        // 3) 页面内联 JSON/JS（JSON-LD、videoInitialData 等）：
        //    服务端渲染的播放器配置常把 m3u8 内联在 HTML 里，& 被转义为 \u0026、/ 转义为 \/
        const srcs = [];
        for (const sc of document.querySelectorAll('script')) {
          if (sc.type && !/json/i.test(sc.type)) continue; // 只取内联的 json/ld+json
          if (sc.src) continue;
          srcs.push(sc.textContent || '');
        }
        try {
          const win = window;
          for (const k of ['__INITIAL_STATE__', 'initialState', 'pageData', 'videoInitialData', 'playerData', 'playInfo', '__NUXT__']) {
            if (win[k]) srcs.push(typeof win[k] === 'string' ? win[k] : JSON.stringify(win[k]));
          }
        } catch (e) {}
        const MEDIA_RE = /https?:\/\/[A-Za-z0-9._~%\/\-]+?\.(?:m3u8|mpd|mp4|webm|mkv|flv|mov|m4s|ts|m4a|mp3|aac|ogg|ogv|opus|weba)\b[^"']*/g;
        for (const t of srcs) {
          const u = t.replace(/\\u0026/g, '&').replace(/\\u002F/gi, '/').replace(/\\\\\//g, '/').replace(/\\\//g, '/');
          for (const m of u.matchAll(MEDIA_RE)) {
            found.add(m[0].replace(/[\)\],;:\s]+$/, ''));
          }
        }
        return [...found];
      });
      for (const u of data) {
        if (u.startsWith('blob:')) continue; // MSE 流无法直接下载，其真实源靠网络嗅探/内联 JSON 捕获
        let abs;
        try { abs = new URL(u, page.url()).href; } catch { continue; }
        const extra = reqHeaders.get(abs) || {};
        addCandidate(abs, {
          contentType: null,
          contentLength: null,
          referer: extra.referer || null,
        });
      }
    } catch {}
  };


  // 自动播放尝试
  const checkPlaying = async () => {
    try {
      return await page.evaluate(() =>
        [...document.querySelectorAll('video')].some(v => v.readyState >= 2 && !v.paused)
      );
    } catch { return false; }
  };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  async function tryAutoPlay() {
    if (!args.clickPlay) return;
    const steps = [];
    // 1) video.play()
    steps.push(async () => {
      const ok = await page.evaluate(async () => {
        for (const v of document.querySelectorAll('video')) {
          try { await v.play(); return true; } catch (e) {}
        }
        return false;
      });
      return ok;
    });
    // 2) 点击文本匹配 播放/play 的元素
    steps.push(async () => {
      return await page.evaluate(() => {
        const els = [...document.querySelectorAll('button, a, div, span, i, p')];
        for (const el of els) {
          const t = (el.textContent || '').trim();
          if (t.length <= 12 && /播放|点击播放|开始播放|play/i.test(t)) {
            try { el.click(); return true; } catch (e) {}
          }
        }
        return false;
      });
    });
    // 3) 常见播放器播放按钮选择器
    for (const sel of ['.vjs-big-play-button', '.dplayer-play-icon', '.xgplayer-start', '.jwicon-play', '[class*="big-play"]', '[class*="play-btn"]', '[class*="playbtn"]']) {
      steps.push(async () => {
        try {
          const el = await page.$(sel);
          if (el) { await el.click({ timeout: 2000 }); return true; }
        } catch {}
        return false;
      });
    }
    for (const step of steps) {
      let ok = false;
      try { ok = await step(); } catch {}
      if (ok) {
        await sleep(800);
        if (await checkPlaying()) { logErr('[sniff] 自动播放成功'); return; }
      }
      await sleep(500);
    }
    logErr('[sniff] 自动播放尝试结束（未确认播放中，继续收集）');
  };

  logErr(`[sniff] 模式=${mode} 打开页面: ${args.url}`);
  try {
    await page.goto(args.url, { waitUntil: 'load', timeout: 60000 });
  } catch (e) {
    logErr('[sniff] goto 警告（继续收集）: ' + e.message.split('\n')[0]);
  }
  const startT = Date.now();

  // 进度 + 周期性收集
  let stop = false;
  const timer = setInterval(async () => {
    const elapsed = Math.round((Date.now() - startT) / 1000);
    if (elapsed >= args.seconds) { stop = true; clearInterval(timer); return; }
    try { await collectFromPage(); } catch {}
    logErr(`[sniff] 进度 ${elapsed}s / ${args.seconds}s 候选=${candidates.size}`);
  }, 5000);

  const playPromise = tryAutoPlay();

  // 等待到时长
  while (!stop) {
    await sleep(1000);
  }
  // 播放尝试最多再等 3s（不突破总时长太多），结束后再收集两次（播放后可能才出流）
  try { await Promise.race([playPromise, sleep(3000)]); } catch {}
  try { await collectFromPage(); } catch {}
  try { await collectFromPage(); } catch {}

  // ---------- 页面元数据 ----------
  let pageTitle = null, ogTitle = null, ogDescription = null, description = null, finalUrl = page.url(), durationHint = null;
  try {
    const meta = await page.evaluate(() => {
      const g = s => document.querySelector(s)?.content || null;
      const vids = [...document.querySelectorAll('video')].map(v => v.duration).filter(d => Number.isFinite(d) && d > 0);
      return {
        title: document.title || null,
        ogTitle: g('meta[property="og:title"]'),
        ogDescription: g('meta[property="og:description"]'),
        description: g('meta[name="description"]'),
        maxVideoDuration: vids.length ? Math.max(...vids) : null,
      };
    });
    pageTitle = meta.title; ogTitle = meta.ogTitle; ogDescription = meta.ogDescription;
    description = meta.description;
    durationHint = meta.maxVideoDuration ? Math.round(meta.maxVideoDuration * 10) / 10 : null;
  } catch (e) {
    logErr('[sniff] 元数据获取失败: ' + e.message.split('\n')[0]);
  }

  // cookies：只保留与候选 URL 同域的（无候选时全部保留）
  let cookieStr = '';
  try {
    const cks = await context.cookies();
    const candHosts = new Set([...candidates.values()].map(c => hostOf(c.url)).filter(Boolean));
    const picked = cks.filter(c => {
      if (candHosts.size === 0) return true;
      for (const h of candHosts) {
        if (h === c.domain || h.endsWith(c.domain.replace(/^\./, '')) || c.domain.replace(/^\./, '') === h) return true;
      }
      return false;
    });
    cookieStr = picked.map(c => `${c.name}=${c.value}`).join('; ');
  } catch (e) {
    logErr('[sniff] cookies 获取失败: ' + e.message.split('\n')[0]);
  }

  // ---------- playlist 分析（并行） ----------
    const listCands = [...candidates.values()].filter(c => c.kind === 'hls' || c.kind === 'dash');
  await Promise.allSettled(listCands.map(async c => {
    const r = await analyzePlaylist(context, c.url, finalUrl || args.url, cookieStr);
    if (r.ok) {
      c.hls = r;
      if (durationHint == null && r.duration) durationHint = r.duration;
      if (!c.note) c.note = r.note;
    }
  }));

  // ---------- 打分 ----------
  const allReqs = [...candidates.values()];
  const maxOrder = allReqs.length ? Math.max(...allReqs.map(c => c.order)) : 0;
  const last30 = maxOrder > 0 ? Math.ceil(maxOrder * 0.7) : 0; // 最后 30%

  // 分片判定（.ts/.m4s/.aac 单片默认不作候选）
  const isSegment = c => c.kind === 'file' && c.ext && SEGMENT_EXTS.has(c.ext);
  const recs = [...candidates.values()].map(c => {
    let score = 0;
    const notes = [];
    const h = c.hls || {};
    const isMaster = c.kind === 'hls' && h.master === true;
    const isMedia = c.kind === 'hls' && h.master === false;
    if (c.kind === 'hls') {
      if (isMaster) { score += 100; notes.push('hls master'); }
      else if (isMedia) { score += 60; notes.push('hls media'); }
      else { score += 60; notes.push('hls 未解析'); }
    } else if (c.kind === 'dash') { score += 70; notes.push('dash'); }
    else {
      const isAudioOnly = (c.contentType || '').startsWith('audio/') ||
        (c.ext && AUDIO_EXTS.has(c.ext));
      if (isAudioOnly) { score += 10; notes.push('纯音频'); }
      else { score += 50; notes.push('file 直链'); }
    }
    // 加分
    const mh = h.maxHeight || 0;
    if (mh >= 1080) score += 15;
    else if (mh >= 720) score += 10;
    const cl = c.contentLength;
    if (cl != null && cl > 50 * 1024 * 1024) score += 10;
    else if (cl != null && cl > 10 * 1024 * 1024) score += 5;
    if (last30 > 0 && c.order >= last30) score += 8;
    if (sameDomain(c.url, finalUrl || args.url)) { score += 3; notes.push('同域'); }
    // 播放列表时长与页面 video.duration 对比：区分预览片与完整正片
    if (c.kind === 'hls' && durationHint && c.hls && c.hls.duration) {
      const pd = c.hls.duration;
      if (Math.abs(pd - durationHint) / durationHint <= 0.15) { score += 15; notes.push('时长匹配页面视频'); }
      else if (pd < durationHint * 0.6) { score -= 10; notes.push('疑似预览片（远短于页面视频）'); }
    }
    // 扣分
    if (c.kind === 'file' && cl != null && cl < 100 * 1024) { score -= 30; notes.push('过小可能为广告/提示音'); }
    if (AD_PATTERNS.test(c.url)) { score -= 50; notes.push('疑似广告/埋点'); }
    return { ...c, score, note: notes.join('；') || null, _isSegment: isSegment(c) };
  });

  // 分片排除：有非分片候选时，分片不作为候选；否则只保留一条最佳分片
  let finalRecs = recs;
  const nonSeg = recs.filter(r => !r._isSegment);
  const seg = recs.filter(r => r._isSegment);
  if (seg.length && nonSeg.length) {
    finalRecs = nonSeg;
  } else if (seg.length && !nonSeg.length) {
    seg.sort((a, b) => (b.contentLength || 0) - (a.contentLength || 0) || b.score - a.score);
    finalRecs = [seg[0]];
    finalRecs[0].note = '仅有分片' + (finalRecs[0].note ? '；' + finalRecs[0].note : '');
  }

  // 推荐：唯一一条。优先级 hls > dash > file；再比 maxHeight、contentLength、score
  const kindRank = { hls: 3, dash: 2, file: 1 };
  finalRecs.sort((a, b) => {
    if (kindRank[a.kind] !== kindRank[b.kind]) return kindRank[b.kind] - kindRank[a.kind];
    if (a.score !== b.score) return b.score - a.score;
    const am = (a.hls && a.hls.maxHeight) || 0, bm = (b.hls && b.hls.maxHeight) || 0;
    if (am !== bm) return bm - am;
    if ((a.contentLength || 0) !== (b.contentLength || 0)) return (b.contentLength || 0) - (a.contentLength || 0);
    return b.order - a.order;
  });
  const recommended = finalRecs[0] || null;

  // 组装输出
  finalRecs = finalRecs.map((c, i) => ({
    id: 'c' + (i + 1),
    kind: c.kind,
    url: c.url,
    contentType: c.contentType,
    contentLength: c.contentLength,
    ext: c.ext,
    referer: c.referer,
    score: c.score,
    recommended: recommended ? c.url === recommended.url : false,
    hls: c.hls,
    note: c.url === (recommended && recommended.url)
      ? ('推荐：' + (c.note || 'score 最高'))
      : c.note,
  }));

  // 报告路径
  const reportDir = process.env.VSNIFF_REPORT_DIR || '/data/tmp/vsniff';
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const reportPath = args.out || path.join(reportDir, `${slugOf(args.url)}-${ts}.json`);

  const report = {
    pageUrl: args.url,
    finalUrl,
    pageTitle,
    ogTitle,
    ogDescription,
    description,
    durationHint,
    cookies: cookieStr || null,
    userAgent: args.mobile ? mobileUA : null,
    reportPath,
    mode,
    elapsedSec: Math.round((performance.now() - t0) / 100) / 10,
    candidates: finalRecs,
  };
  // 桌面模式补取真实 UA（对象字面量里不能 async）
  if (!args.mobile && report.userAgent == null) {
    try { report.userAgent = await page.evaluate(() => navigator.userAgent); } catch {}
  }

  // 落盘 + stdout
  try {
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
  } catch (e) {
    logErr('[sniff] 报告落盘失败: ' + e.message);
  }
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');

  // stderr 人类可读摘要
  logErr('');
  logErr('=== video-sniff 摘要 ===');
  logErr(`页面: ${pageTitle || '(无标题)'}\nURL: ${finalUrl}`);
  if (!finalRecs.length) logErr('候选: （无）');
  finalRecs.forEach(c => {
    const u = c.url.length > 90 ? c.url.slice(0, 87) + '...' : c.url;
    const res = c.hls && c.hls.maxHeight ? ' ' + c.hls.maxHeight + 'p' : '';
    const sz = c.contentLength != null ? ' ' + (c.contentLength / 1048576).toFixed(1) + 'MB' : '';
    logErr(` [${c.id}] ${c.kind}${res}${sz} score=${c.score}  ${u}`);
  });
  if (recommended) {
    const recOut = finalRecs.find(c => c.recommended);
    logErr(`推荐: ${recOut ? recOut.id : '?'} ${recommended.kind} ${recommended.url}`);
  }
  logErr(`报告: ${reportPath}`);

  // 清理
  try { if (mode === 'cdp') { await page.close(); if (browser.contexts().length <= 0 && !args.cdp) await browser.close(); } else { await browser.close(); } } catch {}
  if (cdpEndpoint && mode === 'cdp' && browser) { try { await browser.close(); } catch {} } // 关闭 CDP 连接（不杀浏览器）
}

main().catch(e => {
  logErr('[sniff] 致命错误: ' + (e && e.stack || e));
  process.exit(1);
});
