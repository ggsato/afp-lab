"""Local-only AFP map editor. Standard library; no server or account required outside PC."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import argparse, copy, json, math, re, secrets, threading, webbrowser
from datetime import datetime, timezone
from .lab import validate, record_scenario, write_report
from .recorder import collect, write_trace, read_trace
from .terrain import prepare, xy, number
from .field_config import check_field, load_field
from .coverage import plan as coverage_plan, compute as compute_coverage, inspect_cell
from .providers import MAP_PROVIDERS, DEM_PROVIDERS, provider_ids, create_dem

from .paths import ROOT, WEB_ROOT
LIMIT = 256_000

def read_template():
    return load_field()

def check_config(raw):
    """Reject invalid layouts/plans before making any external DEM request."""
    if not isinstance(raw, dict) or 'terrain' in raw:
        raise ValueError('Use an unprepared geographic config, not prepared terrain JSON')
    check_field(raw)
    s = copy.deepcopy(raw)
    geo = s.pop('geography', None)
    if not isinstance(geo, dict): raise ValueError('geography is required')
    lat0 = number(geo.get('origin_lat'), 'origin_lat', -80, 80)
    lon0 = number(geo.get('origin_lon'), 'origin_lon', -179, 179)
    for k,v,lo,hi in [('frequency_mhz',923,920,928),('tx_dbm',13,-20,13),('sensitivity_dbm',-120,-160,-40),('extra_loss_db',0,0,100),('antenna_gain_db',0,-30,30),('profile_step_m',10,5,100)]:
        number(geo.get(k,v),k,lo,hi)
    nodes = s.get('nodes')
    if not isinstance(nodes,list) or not 2<=len(nodes)<=20: raise ValueError('配置は2〜20台です')
    for n in nodes:
        if not isinstance(n,dict): raise ValueError('Invalid node')
        lat = number(n.get('lat'),'lat',-80,80); lon = number(n.get('lon'),'lon',-179,179)
        x,y = xy(lat,lon,lat0,lon0)
        if max(abs(x),abs(y)) > 15000: raise ValueError('端末は地形原点から15km以内に配置してください')
        n.update(x=round(x,3),y=round(y,3),antenna_m=number(n.get('antenna_m',2),'antenna_m',.1,100))
    for i,a in enumerate(nodes):
        for b in nodes[i+1:]:
            if math.hypot(a['x']-b['x'],a['y']-b['y'])<1: raise ValueError('端末間の距離は1m以上必要です')
    validate(s)
    json.dumps(raw,allow_nan=False)
    return raw

def save_json(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def run_layout(raw, dem, out, compare=False, interval=3.0, source_kind='gsi_dem'):
    check_config(raw)
    interval=number(interval,'comparison interval',.1,60)
    if type(compare) is not bool: raise ValueError('Invalid comparison flag')
    # One frozen terrain snapshot, shared by both schedules.
    frozen=prepare(raw,dem,source_kind); validate(frozen)
    cases=[frozen]
    if compare and len(frozen['messages'])>1:
        alt=copy.deepcopy(frozen); alt['name']=frozen['name'][:75]+' / staggered'
        for i,m in enumerate(alt['messages']):m['at']=i*interval
        alt['duration_s']=max(alt['duration_s'],(len(alt['messages'])-1)*interval+15)
        if alt['messages']!=frozen['messages']:
            validate(alt);cases.append(alt)
        else:
            alt=copy.deepcopy(frozen); alt['name']=frozen['name'][:75]+' / simultaneous'
            for m in alt['messages']:m['at']=0
            validate(alt);cases.append(alt)
    out.mkdir(parents=True,exist_ok=False)
    save_json(out/'geography.json',raw)
    results=[]
    for i,s in enumerate(cases,1):
        save_json(out/f'prepared-{i:02d}.json',s)
        manifest,streams=record_scenario(s); dest=out/'traces'/f'{i:02d}'
        write_trace(dest,manifest,streams); results.append(collect(*read_trace(dest)))
    write_report(results,out)
    terrain=frozen['terrain']
    return {'nodes':terrain['nodes'],'pairs':[{k:v for k,v in p.items() if k!='profile'} for p in terrain['pairs']],
            'tile_count':len(terrain['tiles']),'source_kind':terrain['source_kind'],
            'summaries':[{'name':r['scenario']['name'],'summary':r['summary']} for r in results]}

class PlannerServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, address, cache, output, offline=False, dem_factory=None, source_kind='gsi_dem', config=None):
        self.config=copy.deepcopy(check_field(config)) if config is not None else read_template()
        self.cache=Path(cache); self.output=Path(output);self.offline=offline
        self.dem_factory=dem_factory; self.source_kind=source_kind
        self.token=secrets.token_hex(24); self.run_lock=threading.Lock()
        super().__init__(address, Handler)
    @property
    def origin(self): return f'http://127.0.0.1:{self.server_port}'

class Handler(BaseHTTPRequestHandler):
    def _send(self,status,data,ctype):
        self.send_response(status); self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY'); self.end_headers(); self.wfile.write(data)
    def _json(self,status,obj): self._send(status,json.dumps(obj,ensure_ascii=False,allow_nan=False).encode(),'application/json; charset=utf-8')
    def _host_ok(self): return self.headers.get('Host')==self.server.origin.split('//')[1]
    def do_GET(self):
        if not self._host_ok():return self._json(403,{'error':'Invalid host'})
        p=urlsplit(self.path).path
        if p=='/': return self._send(200,(WEB_ROOT/'planner.html').read_bytes(),'text/html; charset=utf-8')
        if p=='/api/config':return self._json(200,{'config':self.server.config,'token':self.server.token,'offline':self.server.offline,'map_providers':MAP_PROVIDERS,'dem_providers':DEM_PROVIDERS})
        if re.fullmatch(r'/runs/[0-9TZ_-]+[a-f0-9]{8}/index\.html',p):
            f=self.server.output/p.split('/')[2]/'index.html'
            if f.is_file():return self._send(200,f.read_bytes(),'text/html; charset=utf-8')
        return self._json(404,{'error':'Not found'})
    def do_POST(self):
        if not self._host_ok() or self.headers.get('Origin')!=self.server.origin or self.headers.get('X-AFP-Token')!=self.server.token:
            return self._json(403,{'error':'Local same-origin request required'})
        route=urlsplit(self.path).path
        if route not in ('/api/run','/api/coverage','/api/coverage/profile'):return self._json(404,{'error':'Not found'})
        if self.headers.get_content_type()!='application/json':return self._json(415,{'error':'JSON required'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 1<=n<=LIMIT:raise ValueError('Invalid request length')
            req=json.loads(self.rfile.read(n))
            if not isinstance(req,dict):raise ValueError('Expected JSON object')
            if route=='/api/run':
                raw=req['config'];check_config(raw)
            elif route=='/api/coverage':
                raw=req['config'];coverage_plan(raw,req['coverage'])
            else:
                ident=req['run_id']
                if not isinstance(ident,str) or not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',ident):raise ValueError('Invalid coverage run ID')
            if not self.server.run_lock.acquire(blocking=False):return self._json(409,{'error':'Another experiment is running'})
            try:
                if route=='/api/coverage/profile':
                    saved=json.loads((self.server.output/'coverage'/ident/'coverage.json').read_text(encoding='utf-8'))
                    dem=self.server.dem_factory() if self.server.dem_factory else create_dem(provider_ids(saved['config'])[1],self.server.cache,True)
                    return self._json(200,inspect_cell(saved['result'],req['row'],req['col'],dem))
                name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(4)
                if route=='/api/coverage':
                    dest=self.server.output/'coverage'/name
                    print('Coverage:',name,flush=True)
                    dem=self.server.dem_factory() if self.server.dem_factory else create_dem(provider_ids(raw)[1],self.server.cache,self.server.offline)
                    result=compute_coverage(raw,req['coverage'],dem,self.server.source_kind,lambda done,total:print(f'Coverage: {done}/{total} cells',flush=True))
                    dest.mkdir(parents=True,exist_ok=False)
                    save_json(dest/'coverage.json',{'config':raw,'request':req['coverage'],'result':result})
                    return self._json(200,{'run_id':name,'directory':str(dest.resolve()),'result':result})
                dest=self.server.output/name
                print('Experiment:',name,flush=True)
                dem=self.server.dem_factory() if self.server.dem_factory else create_dem(provider_ids(raw)[1],self.server.cache,self.server.offline)
                result=run_layout(raw,dem,dest,req.get('compare',False),req.get('interval',3),self.server.source_kind)
                result.update(report_url=f'/runs/{name}/index.html',directory=str(dest.resolve()))
            finally:self.server.run_lock.release()
            return self._json(200,result)
        except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
            return self._json(400,{'error':str(exc)})
    def log_message(self,fmt,*args):
        # Do not log coordinates or request bodies; report path contains only run ID.
        if not self.path.startswith('/api/config'):super().log_message(fmt,*args)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8765);p.add_argument('--cache',type=Path,default=ROOT/'dem-cache');p.add_argument('--out',type=Path,default=ROOT/'experiments'/'planner');p.add_argument('--offline',action='store_true',help='Use cached DEM only (background map still needs browser network/cache)');p.add_argument('--open',action='store_true')
    p.add_argument('--config',type=Path,help='Field JSON to open at startup; default from configs/geography/catalog.json')
    a=p.parse_args()
    try:
        with PlannerServer(('127.0.0.1',a.port),a.cache,a.out,a.offline,config=load_field(a.config)) as s:
            print('AFP Map Planner v0.7:',s.origin,flush=True);print('Ctrl+C to stop. DEM cache:',s.cache.resolve(),flush=True)
            if a.open:webbrowser.open(s.origin)
            try:s.serve_forever()
            except KeyboardInterrupt:pass
    except (OSError,ValueError,TypeError,KeyError) as exc:p.exit(1,f'Error: {exc}\n')
if __name__=='__main__':main()
