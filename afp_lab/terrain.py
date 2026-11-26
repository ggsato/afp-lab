"""GSI elevation tile acquisition and transparent, deterministic terrain link model.
Only standard-library Python. Network access occurs in prepare(), never in AFP.
"""
from pathlib import Path
import argparse, copy, json, math

from .dem_gsi import GsiDEM, decode_png, pixel, BASE, SOURCES  # compatibility exports
from .providers import ElevationProvider, dem_provider_id, create_dem
EARTH=6371008.8
C=299792458.0

# Local tangent-plane approximation is adequate for this bounded regional experiment.
def xy(lat,lon,lat0,lon0):
    return (EARTH*math.radians(lon-lon0)*math.cos(math.radians(lat0)),EARTH*math.radians(lat-lat0))
def latlon(x,y,lat0,lon0):
    return lat0+math.degrees(y/EARTH),lon0+math.degrees(x/(EARTH*math.cos(math.radians(lat0))))

def path_model(a,b,profile,frequency_mhz=923.0,tx_dbm=13.0,sensitivity_dbm=-120.0,extra_loss_db=0.0,antenna_gain_db=0.0):
    """Single dominant knife-edge approximation, not a complete ITU terrain model."""
    d=math.hypot(b['x']-a['x'],b['y']-a['y']); lam=C/(frequency_mhz*1e6)
    if d<1: raise ValueError('Node separation must be >= 1 m')
    h1=profile[0]+a['antenna_m'];h2=profile[-1]+b['antenna_m']
    points=[]; worst_v=-math.inf; min_clear=math.inf; min_ratio=math.inf; obstacle=None
    for i,z in enumerate(profile):
        t=i/(len(profile)-1); d1=d*t;d2=d-d1
        earth_bulge=d1*d2/(2*EARTH*4/3); ground=z+earth_bulge
        ray=h1+(h2-h1)*t; r=math.sqrt(lam*d1*d2/d);clear=ray-ground
        points.append([round(d1,3),round(ground,3),round(ray,3),round(r,3)])
        if r>0:
            v=-math.sqrt(2)*clear/r; min_clear=min(min_clear,clear); min_ratio=min(min_ratio,clear/r)
            if v>worst_v: worst_v=v;obstacle=d1
    diffraction=0.0 if worst_v<=-.78 else 6.9+20*math.log10(math.sqrt((worst_v-.1)**2+1)+worst_v-.1)
    fspl=20*math.log10(4*math.pi*d/lam); rssi=tx_dbm+antenna_gain_db-fspl-diffraction-extra_loss_db
    return dict(a=a['id'],b=b['id'],distance_m=round(d,2),los=min_clear>=0,fresnel60=min_ratio>=.6,
                min_clearance_m=round(min_clear,2),min_fresnel_ratio=round(min_ratio,3),obstacle_m=round(obstacle,2),
                fspl_db=round(fspl,3),diffraction_db=round(diffraction,3),rssi_dbm=round(rssi,3),
                margin_db=round(rssi-sensitivity_dbm,3),reachable=rssi>=sensitivity_dbm,profile=points)

def number(v,name,lo,hi):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError(f'{name}: expected number {lo}..{hi}')
    return float(v)

def propagation_settings(geo):
    return {k:number(geo.get(k,v),k,lo,hi) for k,v,lo,hi in [('frequency_mhz',923,920,928),('tx_dbm',13,-20,13),('sensitivity_dbm',-120,-160,-40),('extra_loss_db',0,0,100),('antenna_gain_db',0,-30,30)]}

def link_profile(a,b,dem,lat0,lon0,step):
    """Identical sampling for a point-to-point scenario and a coverage cell."""
    d=math.dist((a['x'],a['y']),(b['x'],b['y']));count=max(2,math.ceil(d/step));profile=[]
    for j in range(count+1):
        t=j/count;lat,lon=latlon(a['x']+(b['x']-a['x'])*t,a['y']+(b['y']-a['y'])*t,lat0,lon0)
        profile.append(dem.sample(lat,lon) if 0<j<count else a['ground_m'] if j==0 else b['ground_m'])
    return profile

def prepare(raw,dem: ElevationProvider,source_kind='gsi_dem'):
    """Freeze geography, profiles and model output in a portable scenario. No live lookups during run."""
    dem_provider_id(raw)
    s=copy.deepcopy(raw);geo=s.pop('geography'); nodes=s['nodes']
    if not 2<=len(nodes)<=20:raise ValueError('Terrain scenarios support 2..20 nodes')
    lat0=number(geo['origin_lat'],'origin_lat',-80,80);lon0=number(geo['origin_lon'],'origin_lon',-179,179)
    settings=propagation_settings(geo)
    step=number(geo.get('profile_step_m',10),'profile_step_m',5,100)
    positions=[]
    for n in nodes:
        lat=number(n['lat'],'lat',-80,80);lon=number(n['lon'],'lon',-179,179)
        x,y=xy(lat,lon,lat0,lon0)
        if max(abs(x),abs(y))>15000:raise ValueError('Terrain extent limited to 15 km from origin')
        n.update(x=round(x,3),y=round(y,3),antenna_m=number(n.get('antenna_m',2),'antenna_m',.1,100))
        positions.append(dict(id=n['id'],x=n['x'],y=n['y'],lat=lat,lon=lon,antenna_m=n['antenna_m'],ground_m=dem.sample(lat,lon)))
    pairs=[]
    for i,a in enumerate(positions):
        for b in positions[i+1:]:
            pairs.append(path_model(a,b,link_profile(a,b,dem,lat0,lon0,step),**settings))
    # A small geographic overview raster, sampled from the same DEM; not a full resolution map.
    xs=[p['x'] for p in positions];ys=[p['y'] for p in positions];span=max(max(xs)-min(xs),max(ys)-min(ys),500)
    pad=max(150,span*.12); x0=min(xs)-pad;x1=max(xs)+pad;y0=min(ys)-pad;y1=max(ys)+pad
    cols=41;rows=41;grid=[]
    for j in range(rows):
        row=[]
        for i in range(cols):
            lat,lon=latlon(x0+(x1-x0)*(i+.5)/cols,y1-(y1-y0)*(j+.5)/rows,lat0,lon0)
            row.append(round(dem.sample(lat,lon),2))
        grid.append(row)
    s['terrain']=dict(source_kind=source_kind,model='fspl-dominant-knife-edge-v1',origin_lat=lat0,origin_lon=lon0,
                      settings=settings,profile_step_m=step,nodes=positions,pairs=pairs,
                      grid=dict(x0=x0,x1=x1,y0=y0,y1=y1,values=grid),tiles=getattr(dem,'provenance',{}),
                      attribution='国土地理院 標高タイルを加工' if source_kind=='gsi_dem' else 'SYNTHETIC TEST DATA / NOT GSI')
    return s

def validate_terrain(t,nodes):
    if not isinstance(t,dict) or t.get('model')!='fspl-dominant-knife-edge-v1' or t.get('source_kind') not in ('gsi_dem','synthetic_test'):raise ValueError('Invalid frozen terrain')
    positions={n['id']:n for n in nodes}; tn={n['id']:n for n in t['nodes']}
    if set(positions)!=set(tn) or len(tn)!=len(t['nodes']):raise ValueError('Terrain nodes mismatch')
    for i,p in positions.items():
        if (p['x'],p['y'])!=(tn[i]['x'],tn[i]['y']):raise ValueError('Terrain positions changed; prepare again')
    seen=set()
    for p in t['pairs']:
        a,b=p['a'],p['b'];key=tuple(sorted((a,b)))
        if a==b or a not in positions or b not in positions or key in seen:raise ValueError('Invalid terrain link pair')
        seen.add(key)
        number(p['rssi_dbm'],'rssi_dbm',-1000,100)
        if type(p['reachable']) is not bool:raise ValueError('Invalid terrain reachability')
        if len(p['profile'])<3:raise ValueError('Missing terrain profile')
    if len(seen)!=len(nodes)*(len(nodes)-1)//2:raise ValueError('Incomplete terrain links')
    if t['source_kind']=='gsi_dem' and not t['tiles']:raise ValueError('Missing GSI tile provenance')
    # Check all nested values are serializable finite JSON.
    json.dumps(t,allow_nan=False)
    return t

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('config',type=Path);ap.add_argument('--cache',type=Path,default=Path('dem-cache'));ap.add_argument('--out',type=Path,default=Path('prepared'));ap.add_argument('--offline',action='store_true');ap.add_argument('--compare',action='store_true',help='Also generate staggered variant with 3s separation (two or more messages)')
    args=ap.parse_args()
    try:
        raw=json.loads(args.config.read_text(encoding='utf-8-sig'));dem=create_dem(dem_provider_id(raw),args.cache,args.offline);s=prepare(raw,dem)
        from .lab import validate
        validate(s);args.out.mkdir(parents=True,exist_ok=True)
        path=args.out/'terrain.json';path.write_text(json.dumps(s,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        if args.compare:
            v=copy.deepcopy(s);v['name']+=' / staggered'
            for i,m in enumerate(v['messages']):m['at']=3*i
            v['duration_s']=max(v.get('duration_s',30),3*(len(v['messages'])-1)+15);validate(v)
            (args.out/'terrain-staggered.json').write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(f'Prepared: {path.resolve()} | {len(s["terrain"]["tiles"])} GSI tiles')
        for p in s['terrain']['pairs']:print(f'N{p["a"]}-N{p["b"]}: {p["distance_m"]:.0f}m, LOS={p["los"]}, RSSI={p["rssi_dbm"]:.1f}dBm, margin={p["margin_db"]:.1f}dB, reachable={p["reachable"]}')
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:ap.exit(1,f'Error: {e}\n')
if __name__=='__main__':main()
