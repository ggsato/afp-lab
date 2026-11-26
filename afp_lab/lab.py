"""AFP Lab v0.6: distributed recording and terrain-aware experiments."""
from pathlib import Path
import argparse
import json
import math
import webbrowser
from .afp import HEADER
from .contracts import BROADCAST
from .node import AFPNode, NodeSession
from .radio import VirtualE220, Field
from .runtime import SimulationEngine, VirtualNodeClock, ClockMapping
from .recorder import Recorder, collect, write_trace, read_trace, scenario_digest

from .paths import ROOT, CONFIG_ROOT, WEB_ROOT
VERSION = '0.6.0'
MODEL = 'radius-uart-v2'

def numeric(v, name, lo, hi, integer=False):
    if type(v) not in ((int,) if integer else (int,float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError(f'{name}: expected {"integer" if integer else "number"} in {lo}..{hi}')
    return v


def validate(raw):
    if not isinstance(raw,dict): raise ValueError('Scenario must be a JSON object')
    defaults = dict(radius_m=1000, air_rate_bps=1758, air_overhead_s=.05,
                    uart_baud=9600, queue_capacity=4, max_frame_bytes=200, module_queue_capacity=4,
                    relay_delay_s=.1, ack_delay_s=.2, ttl=4)
    name = raw.get('name','scenario')
    if not isinstance(name,str) or not 1 <= len(name) <= 100: raise ValueError('Invalid scenario name')
    radio = raw.get('radio',{})
    if not isinstance(radio,dict): raise ValueError('radio must be an object')
    unknown = set(radio)-set(defaults)
    if unknown: raise ValueError(f'Unknown radio parameters: {sorted(unknown)}')
    s = defaults | radio
    for key,lo,hi,integer in [('radius_m',1,100000,False),('air_rate_bps',1,1000000,False),
                              ('air_overhead_s',0,60,False),('uart_baud',1200,115200,True),
                              ('queue_capacity',1,100,True),('module_queue_capacity',1,100,True),('max_frame_bytes',HEADER.size,200,True),
                              ('relay_delay_s',0,60,False),('ack_delay_s',0,60,False),('ttl',1,16,True)]:
        numeric(s[key],key,lo,hi,integer)
    nodes = raw.get('nodes',[])
    if not isinstance(nodes,list) or not 2 <= len(nodes) <= 100: raise ValueError('Expected 2..100 nodes')
    ids = set(); out_nodes = []
    for n in nodes:
        if not isinstance(n,dict): raise ValueError('Node must be object')
        a = numeric(n.get('id'),'node.id',1,65534,True)
        if a in ids: raise ValueError('Duplicate node id')
        ids.add(a)
        x = numeric(n.get('x'),'node.x',-1000000,1000000); y = numeric(n.get('y'),'node.y',-1000000,1000000)
        label = n.get('label',f'Node {a}'); relay = n.get('relay',False)
        if not isinstance(label,str) or len(label)>60 or type(relay) is not bool: raise ValueError('Invalid label/relay')
        channel = numeric(n.get('channel',0),'channel',0,30,True)
        offset=numeric(n.get('clock_offset_us',0),'clock_offset_us',0,10**12,True)
        drift=numeric(n.get('clock_drift_ppm',0),'clock_drift_ppm',-10000,10000)
        start_delay=numeric(n.get('start_delay_s',0),'start_delay_s',0,86400)
        out_nodes.append(dict(id=a,x=x,y=y,label=label,relay=relay,channel=channel,clock_offset_us=offset,clock_drift_ppm=drift,start_delay_s=start_delay))
    messages = raw.get('messages',[])
    if not isinstance(messages,list) or not 1<=len(messages)<=1000: raise ValueError('Expected 1..1000 messages')
    out_messages=[]
    for m in messages:
        if not isinstance(m,dict): raise ValueError('Message must be object')
        t=numeric(m.get('at',0),'message.at',0,86400)
        src=numeric(m.get('src'),'message.src',1,65534,True); dst=numeric(m.get('dst'),'message.dst',1,65534,True)
        if src not in ids or dst not in ids or src==dst: raise ValueError('Message endpoints must be different defined nodes')
        p=m.get('payload','')
        if not isinstance(p,str) or len(p.encode('utf-8'))+HEADER.size>s['max_frame_bytes']: raise ValueError('Payload too large or not text')
        link_dst = m.get('link_dst',BROADCAST)
        numeric(link_dst,'message.link_dst',1,BROADCAST,True)
        if link_dst != BROADCAST and link_dst not in ids: raise ValueError('Unknown link_dst')
        out_messages.append(dict(at=t,src=src,dst=dst,payload=p,link_dst=link_dst))
    last=max(m['at'] for m in out_messages)
    window=numeric(raw.get('duration_s',last+30),'duration_s',0.001,90000)
    if window<=last: raise ValueError('duration_s must exceed the last planned send time')
    result=dict(name=name,radio=s,nodes=out_nodes,messages=out_messages,duration_s=window)
    if 'geography' in raw: raise ValueError('Geographic config must be prepared using terrain.py first')
    if 'terrain' in raw:
        from .terrain import validate_terrain
        result['terrain']=validate_terrain(raw['terrain'],out_nodes)
        positions={n['id']:n for n in result['terrain']['nodes']}
        for n in nodes:
            for k in ('lat','lon','antenna_m'):
                if k in n and n[k]!=positions[n['id']][k]: raise ValueError('Geographic node changed; prepare again')
    return result


def split_config(scenario):
    """Host plans are independent of model settings, geography and peer clocks."""
    s=scenario['radio']
    return ({n['id']:dict(node_id=n['id'],relay=n['relay'],channel=n['channel'],
                        uart_baud=s['uart_baud'],queue_capacity=s['queue_capacity'],
                        max_frame_bytes=s['max_frame_bytes'],relay_delay_s=s['relay_delay_s'],
                        ack_delay_s=s['ack_delay_s'],ttl=s['ttl'],duration_s=scenario['duration_s'],
                        commands=[m.copy() for m in scenario['messages'] if m['src']==n['id']])
             for n in scenario['nodes']},
            dict(radius_m=s['radius_m'],air_rate_bps=s['air_rate_bps'],air_overhead_s=s['air_overhead_s'],
                 module_queue_capacity=s['module_queue_capacity'],
                 nodes=[{k:n[k] for k in ('id','x','y','clock_offset_us','clock_drift_ppm','start_delay_s')} for n in scenario['nodes']]))


def record_scenario(raw):
    scenario=validate(raw); s=scenario['radio']; engine=SimulationEngine()
    digest=scenario_digest(scenario); exp='sim-'+digest[:24]
    plans,environment=split_config(scenario)
    fr=Recorder(exp,'field','simulation','field',engine)
    terrain=scenario.get('terrain')
    if terrain is not None: environment['terrain']=terrain
    field=Field(engine,environment['radius_m'],environment['air_rate_bps'],environment['air_overhead_s'],fr,terrain=terrain)
    descriptors=[fr.descriptor(ClockMapping(0,0,1,1,'simulation_reference'))]
    streams={'field':fr.records}; sessions={}
    for n in environment['nodes']:
        a=n['id']; plan=plans[a]
        clock=VirtualNodeClock(engine,n['clock_offset_us'],n['clock_drift_ppm'])
        rec=Recorder(exp,f'node-{a}','simulation','local',clock,a)
        radio=VirtualE220(field,a,(n['x'],n['y']),plan['channel'],plan['uart_baud'],plan['queue_capacity'],plan['max_frame_bytes'],
                         rec,environment['module_queue_capacity'])
        node=AFPNode(radio,clock,rec.log,plan['relay'],plan['relay_delay_s'],plan['ack_delay_s'],plan['ttl'])
        sessions[a]=NodeSession(node)
        descriptors.append(rec.descriptor(clock.mapping)); streams[rec.stream_id]=rec.records
    for n in environment['nodes']:
        a=n['id']; engine.later(n['start_delay_s'],sessions[a].start,plans[a]['commands'])
    engine.run_until(scenario['duration_s'])
    for d in descriptors: d['record_count']=len(streams[d['stream_id']])
    manifest=dict(schema_version=1,version=VERSION,model=terrain['model'] if terrain else MODEL,mode='simulation',experiment_id=exp,
                  scenario_sha256=digest,scenario=scenario,streams=descriptors,
                  node_plans={str(k):dict(v,experiment_id=exp) for k,v in plans.items()},virtual_environment=environment,
                  observation_window_s=scenario['duration_s'],links=field.links())
    return manifest,streams


def run_scenario(raw):
    return collect(*record_scenario(raw))


def write_report(results, output):
    output.mkdir(parents=True,exist_ok=True)
    bundle=dict(version=VERSION,model=MODEL,results=results)
    (output/'experiments.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
    template=(WEB_ROOT/'observatory.html').read_text(encoding='utf-8')
    # Embedded JSON cannot terminate its script element even for untrusted labels.
    data=json.dumps(bundle,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    path=output/'index.html'
    path.write_text(template.replace('/*__AFP_DATA__*/',data,1),encoding='utf-8')
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenarios',nargs='*',type=Path,help='JSON scenario files; default: bundled examples')
    parser.add_argument('--out',type=Path,default=ROOT/'results',help='Output directory (overwrites report and JSON)')
    parser.add_argument('--open',action='store_true',help='Open local HTML in default browser')
    parser.add_argument('--collect',nargs='+',type=Path,metavar='TRACE_DIR',help='Rebuild from existing manifest + JSONL (no simulation)')
    args=parser.parse_args()
    paths=args.scenarios or sorted((CONFIG_ROOT/'scenarios').glob('*.json'))
    try:
        if args.collect:
            if args.scenarios: raise ValueError('Do not combine scenario files and --collect')
            results=[collect(*read_trace(p)) for p in args.collect]
        else:
            results=[]
            for i,p in enumerate(paths,1):
                manifest,streams=record_scenario(json.loads(p.read_text(encoding='utf-8-sig')))
                trace_dir=args.out/'traces'/f'{i:02d}'
                # Clear only known old trace files when reusing output directories.
                trace_dir.mkdir(parents=True,exist_ok=True)
                for old in trace_dir.glob('*.jsonl'): old.unlink()
                for old in (trace_dir/'plans').glob('node-*.json'): old.unlink()
                write_trace(trace_dir,manifest,streams)
                results.append(collect(*read_trace(trace_dir)))
        report=write_report(results,args.out)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as e:
        parser.exit(1,f'Error: {e}\n')
    for r in results:
        s=r['summary']; print(f"{r['scenario']['name']}: delivered {s['delivered']}/{s['offered']}, ACK {s['acked']}, RF TX {s['rf_tx']}, collisions {s['collision']}, queue drops {s['queue_drop']}")
    print(f'Report: {report.resolve()}')
    if args.open: webbrowser.open(report.resolve().as_uri())

if __name__=='__main__': main()
