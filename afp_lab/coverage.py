"""Bounded, deterministic terrain coverage. No AFP nodes, events, or radio changes.
Grid cells are point predictions at cell centres, not measured coverage.
"""
import math
from .field_config import check_field
from .terrain import number, xy, latlon, path_model, propagation_settings, link_profile

MAX_CELLS=10000
MAX_SAMPLES=4_000_000
MODEL='fspl-dominant-knife-edge-v1'


def plan(raw,request):
    """Validate *before* accessing DEM. Accept one-node drafts, not just runnable scenarios."""
    check_field(raw)
    if not isinstance(request,dict): raise ValueError('Coverage settings required')
    ident=request.get('source_id')
    if type(ident) is not int: raise ValueError('Select a source node')
    node=next((n for n in raw['nodes'] if n['id']==ident),None)
    if node is None: raise ValueError('Coverage source node not found')
    g=raw['geography']; lat0=g['origin_lat'];lon0=g['origin_lon']
    settings=propagation_settings(g); step=number(g.get('profile_step_m',10),'profile_step_m',5,100)
    radius=number(request.get('radius_m',5000),'radius_m',100,10000)
    spacing=number(request.get('spacing_m',200),'spacing_m',50,500)
    if spacing>radius: raise ValueError('Grid spacing must not exceed radius')
    height=number(request.get('receiver_antenna_m',1.5),'receiver_antenna_m',.1,100)
    stable=number(request.get('stable_margin_db',10),'stable_margin_db',1,40)
    x,y=xy(node['lat'],node['lon'],lat0,lon0);x,y=round(x,3),round(y,3)
    if max(abs(x)+radius,abs(y)+radius)>15000: raise ValueError('Coverage radius exceeds terrain extent (origin +/-15 km); move origin or reduce radius')
    # Use the same rounded local coordinates as prepare(). Grid centres north to south.
    n=math.floor(radius/spacing); size=2*n+1
    # Reject oversized requests before allocating grids or issuing network requests.
    if math.pi*(radius/spacing)**2>MAX_CELLS*1.02: raise ValueError(f'Grid too large; use coarser spacing (max {MAX_CELLS} cells)')
    count=samples=0
    for row in range(size):
        for col in range(size):
            d=math.hypot((col-n)*spacing,(n-row)*spacing)
            if d<=radius:
                count+=1
                if d>=1:samples+=max(2,math.ceil(d/step))+1
    if count>MAX_CELLS or samples>MAX_SAMPLES:
        raise ValueError(f'Computation limit: {count} cells, {samples} profile samples; max {MAX_CELLS} cells / {MAX_SAMPLES} samples. Reduce radius or increase spacing/profile step.')
    # ensure the whole region is within geographic input bounds (including cell centres)
    for dx,dy in [(-radius,-radius),(radius,radius)]:
        lat,lon=latlon(x+dx,y+dy,lat0,lon0)
        number(lat,'coverage latitude',-80,80);number(lon,'coverage longitude',-179,179)
    return dict(model=MODEL,origin_lat=lat0,origin_lon=lon0,settings=settings,profile_step_m=step,
                source=dict(id=ident,label=str(node.get('label',f'N{ident}')),lat=node['lat'],lon=node['lon'],x=x,y=y,antenna_m=number(node.get('antenna_m',2),'antenna_m',.1,100)),
                radius_m=radius,spacing_m=spacing,receiver_antenna_m=height,stable_margin_db=stable,
                size=size,center_index=n,cell_count=count,profile_sample_count=samples)


def endpoint(p,row,col):
    if type(row) is not int or type(col) is not int or not 0<=row<p['size'] or not 0<=col<p['size']:
        raise ValueError('Invalid grid cell')
    n=p['center_index'];s=p['spacing_m'];a=p['source']; dx=(col-n)*s;dy=(n-row)*s
    if math.hypot(dx,dy)>p['radius_m']:return None
    x,y=round(a['x']+dx,3),round(a['y']+dy,3);lat,lon=latlon(x,y,p['origin_lat'],p['origin_lon'])
    return dict(id=0,x=x,y=y,lat=lat,lon=lon,antenna_m=p['receiver_antenna_m'])


def link(p,b,dem):
    a=dict(p['source']);a['ground_m']=dem.sample(a['lat'],a['lon']);b=dict(b);b['ground_m']=dem.sample(b['lat'],b['lon'])
    profile=link_profile(a,b,dem,p['origin_lat'],p['origin_lon'],p['profile_step_m'])
    return path_model(a,b,profile,**p['settings'])


def missing_data(exc):
    # GSI's explicit unavailable-data cases only. Corrupt tiles / network errors fail the run.
    return str(exc).startswith(('No GSI elevation data at ','Offline cache missing '))


def compute(raw,request,dem,source_kind='gsi_dem',progress=None):
    p=plan(raw,request)
    if source_kind not in ('gsi_dem','synthetic_test'):raise ValueError('Invalid terrain source')
    a=p['source'];a['ground_m']=dem.sample(a['lat'],a['lon'])  # missing base is fatal
    rows=[];known=unknown=reachable=stable=0;done=0
    for r in range(p['size']):
        cells=[]
        for c in range(p['size']):
            b=endpoint(p,r,c)
            if b is None:cells.append(None);continue
            if r==p['center_index'] and c==p['center_index']:
                cells.append({'unknown':'source_location'});unknown+=1
            else:
                try:
                    v=link(p,b,dem)
                except ValueError as e:
                    if not missing_data(e):raise
                    cells.append({'unknown':'dem_unavailable'});unknown+=1
                else:
                    cells.append({k:v[k] for k in ('rssi_dbm','margin_db','los','fresnel60','reachable','diffraction_db','distance_m')});known+=1
                    reachable+=v['reachable'];stable+=v['margin_db']>=p['stable_margin_db']
            done+=1
            if progress and (done%250==0 or done==p['cell_count']):progress(done,p['cell_count'])
        rows.append(cells)
    return dict(schema='afp-coverage-v1',source_kind=source_kind,plan=p,cells=rows,
                summary=dict(known=known,unknown=unknown,reachable=reachable,stable=stable),
                tiles=dict(getattr(dem,'provenance',{})),attribution='国土地理院 標高タイルを加工' if source_kind=='gsi_dem' else 'SYNTHETIC TEST DATA / NOT GSI')


def inspect_cell(result,row,col,dem):
    p=result['plan'];b=endpoint(p,row,col)
    if b is None:raise ValueError('Outside coverage radius')
    cell=result['cells'][row][col]
    if 'unknown' in cell:raise ValueError('No predicted link for this cell: '+cell['unknown'])
    v=link(p,b,dem)
    # Do not present a new profile as belonging to a frozen coverage map if inputs changed.
    if any(v[k]!=value for k,value in cell.items()):raise ValueError('Link differs from saved coverage; recalculate map')
    if result['source_kind']=='gsi_dem':
        tiles=getattr(dem,'provenance',{})
        if not tiles or any(result['tiles'].get(k)!=value for k,value in tiles.items()):
            raise ValueError('DEM cache differs from saved coverage; recalculate map')
    return dict(link=v,receiver=b,source=p['source'],source_kind=result['source_kind'])
