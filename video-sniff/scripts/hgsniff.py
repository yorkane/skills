import json, os, subprocess, sys, urllib.request, glob
# usage: python3 hgsniff.py <video_id> [max_ep]
# probe title, bisect max ep, serial download with per-ep duration verify
VID=sys.argv[1]
API='https://huangguoai.com/api/videos/%s/play?ep=%%d'%VID
BASE='/home/aigc/.codex/skills/video-sniff/scripts/vsdl'
def play(ep):
    req=urllib.request.Request(API%ep,headers={'User-Agent':'Mozilla/5.0'})
    return json.load(urllib.request.urlopen(req,timeout=10))
def okdata(d):
    return isinstance(d.get('data'),dict) and bool(d['data'].get('video_url'))
def dur(f):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f],capture_output=True,text=True)
    return float(p.stdout.strip()) if p.stdout.strip() else 0
first=play(1)
if not okdata(first):
    print('EP1_FAIL', json.dumps(first,ensure_ascii=False)[:300]); raise SystemExit(1)
a=first['data']
pt=a.get('page_title','')
# 《剧名》第N集 ... | 黄果短剧  ->  extract show name and category suffix
import re as _re
m=_re.match(r'《(.+?)》',pt)
show=m.group(1) if m else _re.sub(r'\s*\|.*$','',pt)
m2=_re.search(r'(AI成人[^ |]+)',pt)
cat=m2.group(1) if m2 else 'AI短剧'
print('SHOW=',show,'CAT=',cat,flush=True)
if len(sys.argv)>2:
    maxep=int(sys.argv[2])
else:
    lo,hi=1,3000
    while lo<hi:
        mid=(lo+hi+1)//2
        if okdata(play(mid)): lo=mid
        else: hi=mid-1
    maxep=lo
print('MAX_EP=',maxep,flush=True)
res=[]
for ep in range(1,maxep+1):
    d=play(ep)['data']
    name='《%s》第%d集 %s'%(show,ep,cat)
    fs=glob.glob('/data/download/video/《%s》第%d集 *'%(_re.escape(show),ep))
    if fs and abs(dur(fs[0])-d['duration'])<3:
        print('ep%02d SKIP exists'%ep,flush=True); res.append(True); continue
    cmd=[BASE,'--url',d['video_url'],'--kind','hls',
         '--referer','https://huangguoai.com/video/%s/ep-%d/'%(VID,ep),'--title',name,
         '--outdir','/data/download/video','--json']
    r=subprocess.run(cmd,capture_output=True,text=True)
    line=(r.stdout.strip().splitlines() or [''])[-1]
    info=json.loads(line) if line.startswith('{') else {}
    if not info.get('ok'):
        print('ep%02d FAIL'%(ep),(r.stdout[-200:]+r.stderr[-400:])); res.append(False); continue
    f=info['file']; dd=dur(f); ok=abs(dd-d['duration'])<3; res.append(ok)
    print('ep%02d %s %.1fs(api %s) %.0fMB %s'%(ep,'OK' if ok else 'MISMATCH',dd,d['duration'],os.path.getsize(f)/1e6,info.get('resolution','')),flush=True)
print('ALL_GOOD' if all(res) else 'CHECK_FAILED')
