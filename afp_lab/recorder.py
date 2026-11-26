"""Distributed trace contract and offline collector. No dependency on simulator.
A stream owns one monotonic clock. The manifest declares its clock mapping.
"""
from dataclasses import asdict
from pathlib import Path
import json
import hashlib
import statistics
import math
from .runtime import ClockMapping

SCHEMA = 1
LOCAL_EVENTS = {'origin','admitted','queue_drop','uart_tx_end','rx','deliver','relay','ack',
                'duplicate','ttl_drop','send_rejected','invalid_frame','uart_error'}
FIELD_EVENTS = {'tx','rf_tx_end','rf_rx','collision','half_duplex','filtered','no_receiver','module_drop'}
# Actual radio instruments can record other field events in a future schema.

class Recorder:
    def __init__(self, experiment_id, stream_id, mode, source, clock, node_id=None, sink=None, retain=True):
        if mode not in ('simulation','physical') or source not in ('local','field'):
            raise ValueError('Invalid recorder mode/source')
        if (source=='local') != (node_id is not None): raise ValueError('Invalid recorder owner')
        self.experiment_id, self.stream_id, self.mode, self.source = experiment_id, stream_id, mode, source
        self.clock, self.node_id = clock, node_id
        self.records=[]
        self.sink,self.retain=sink,retain
        self.count=0; self.last_t_us=None
    def log(self,event,**fields):
        allowed=LOCAL_EVENTS if self.source=='local' else FIELD_EVENTS
        if event not in allowed: raise ValueError(f'{event} is not a {self.source} observation')
        if self.count>=100000: raise RuntimeError('Trace limit reached')
        if set(fields)&{'schema_version','experiment_id','stream_id','mode','source','node_id','event_seq','t_us','event','t','clock_uncertainty_us'}:
            raise ValueError('Reserved event field')
        record=dict(schema_version=SCHEMA,experiment_id=self.experiment_id,stream_id=self.stream_id,
                    mode=self.mode,source=self.source,node_id=self.node_id,event_seq=self.count+1,
                    t_us=round(self.clock.now*1e6),event=event,**fields)
        # Hardware-facing traces do not contain the simulator's RF truth.
        if self.source=='local' and set(fields)&{'sender','receiver','txid','candidates','duration','rf_end','uart_end'}:
            raise ValueError('Field-only metadata in local stream')
        if self.last_t_us is not None and record['t_us']<self.last_t_us:
            raise ValueError('Recorder clock went backwards')
        if self.sink is not None: self.sink(record)
        if self.retain: self.records.append(record)
        self.count+=1;self.last_t_us=record['t_us']
    def descriptor(self,mapping,complete=True):
        return dict(stream_id=self.stream_id,source=self.source,node_id=self.node_id,
                    clock_mapping=asdict(mapping) if mapping is not None else None,
                    complete=complete,record_count=self.count,file=f'{self.stream_id}.jsonl')


class JsonlSink:
    """Optional host-side incremental writer. Exclusive create; no silent overwrite.
    Flush each record, but not a guarantee against power loss. Close via with.
    Embedded firmware may emit the same schema over USB or to flash instead.
    """
    def __init__(self,path): self.path=Path(path); self.handle=None
    def __enter__(self):
        self.handle=self.path.open('x',encoding='utf-8',newline='\n'); return self
    def __call__(self,event):
        if self.handle is None: raise RuntimeError('Sink is not open')
        self.handle.write(json.dumps(event,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
        self.handle.flush()
    def __exit__(self,*args): self.handle.close();self.handle=None


def scenario_digest(scenario):
    return hashlib.sha256(json.dumps(scenario,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def collect(manifest, streams):
    """Collect raw streams without access to a node, radio, or simulation engine.
    No clock mapping => preserve raw stream, omit its events from aligned replay.
    Completeness is explicit; RF truth exists only for complete simulated field streams.
    """
    if manifest.get('schema_version')!=SCHEMA: raise ValueError('Unsupported trace schema')
    mode=manifest['mode']; exp=manifest['experiment_id']; scenario=manifest['scenario']
    if mode not in ('simulation','physical'): raise ValueError('Unknown experiment mode')
    ids={n['id'] for n in scenario['nodes']}; descriptors=manifest['streams']
    if not isinstance(exp,str) or not exp: raise ValueError('Invalid experiment id')
    if manifest.get('scenario_sha256')!=scenario_digest(scenario): raise ValueError('Scenario digest mismatch')
    seen_streams=set(); local_owners=set(); available_complete=set(); field_complete=False
    aligned=[]; local=[]; field=[]; warnings=[]; status=[]
    for d in descriptors:
        sid=d['stream_id']; source=d['source']; node_id=d['node_id']
        if sid in seen_streams or source not in ('local','field'): raise ValueError('Invalid/duplicate stream')
        seen_streams.add(sid)
        if source=='local':
            if node_id not in ids or node_id in local_owners: raise ValueError('Invalid/duplicate local owner')
            local_owners.add(node_id)
        elif node_id is not None: raise ValueError('Field stream must have no node owner')
        if type(d['complete']) is not bool: raise ValueError('Invalid stream completeness')
        mapping=ClockMapping(**d['clock_mapping']) if d.get('clock_mapping') is not None else None
        records=streams.get(sid)
        if records is None:
            warnings.append(f'Missing stream: {sid}'); status.append(dict(stream_id=sid,source=source,node_id=node_id,status='missing',aligned=False,count=0)); continue
        if not isinstance(records,list): raise ValueError('Stream must contain a list of records')
        complete=d['complete']
        if complete and (type(d.get('record_count')) is not int or d['record_count']!=len(records)):
            complete=False; warnings.append(f'Record count mismatch: {sid}')
        if not complete: warnings.append(f'Incomplete stream: {sid}')
        if mapping is None: warnings.append(f'Unaligned stream: {sid}')
        if source=='local' and complete: available_complete.add(node_id)
        if source=='field' and complete and mapping is not None: field_complete=True
        previous=None
        for index,e in enumerate(records,1):
            expected=dict(schema_version=SCHEMA,experiment_id=exp,stream_id=sid,mode=mode,source=source,node_id=node_id,event_seq=index)
            if any(e.get(k)!=v for k,v in expected.items()): raise ValueError(f'Stream identity/sequence mismatch: {sid} #{index}')
            if type(e.get('t_us')) is not int or (previous is not None and e['t_us']<previous): raise ValueError(f'Non-monotonic time: {sid}')
            previous=e['t_us']
            if e['event'] not in (LOCAL_EVENTS if source=='local' else FIELD_EVENTS): raise ValueError('Invalid observation source')
            if source=='local' and set(e)&{'sender','receiver','txid','candidates','duration','rf_end','uart_end'}: raise ValueError('Field metadata in local record')
            (local if source=='local' else field).append(e)
            if mapping is not None:
                t_us=mapping.align(e['t_us'])
                # Preserve raw local timestamp; t is a display projection only.
                view=dict(e,t=round(t_us/1e6,6),aligned_t_us=t_us,clock_uncertainty_us=mapping.uncertainty_us)
                if source=='local': view['node']=node_id
                aligned.append(view)
        status.append(dict(stream_id=sid,source=source,node_id=node_id,status='complete' if complete else 'incomplete',aligned=mapping is not None,count=len(records)))
    unknown=set(streams)-seen_streams
    if unknown: raise ValueError(f'Undeclared streams: {sorted(unknown)}')
    missing=ids-available_complete
    if missing: warnings.append(f'Complete local recordings unavailable for nodes {sorted(missing)}')
    if mode=='simulation' and not field_complete: warnings.append('Complete simulated field recording unavailable')
    if mode=='physical': warnings.append('RF ground truth is unavailable; no RF loss cause is inferred from missing ACKs.')
    # Ties across streams are arbitrary, not an inferred causal order.
    aligned.sort(key=lambda e:(e['aligned_t_us'],e['stream_id'],e['event_seq']))
    def message_key(e): return (e['src'],e['dst'],e['seq'])
    origin={message_key(e):e for e in local if e['event']=='origin' and e['node_id']==e['src']}
    delivery={message_key(e):e for e in local if e['event']=='deliver' and e['node_id']==e['dst']}
    acks={(e['dst'],e['src'],e['seq']):e for e in local if e['event']=='ack' and e['node_id']==e['dst']}
    # Correlation and RTT use only host-visible traces. No cross-clock subtraction.
    delivered=len(origin.keys()&delivery.keys()); acked=len(origin.keys()&acks.keys())
    rtts=[]
    for key, e in origin.items():
        if key in acks and acks[key]['stream_id']==e['stream_id']:
            delta=acks[key]['t_us']-e['t_us']
            if delta>=0: rtts.append(delta/1e6)
    host_complete=not missing
    txs=[e for e in field if e['event']=='tx']
    rf_known=mode=='simulation' and field_complete
    count_field=lambda kind:sum(e['event']==kind for e in field) if rf_known else None
    summary=dict(offered=len(origin),delivered=delivered,acked=acked,
                 planned=len(scenario['messages']),local_complete=host_complete,
                 pdr=round(delivered/len(origin),6) if host_complete and origin else None,
                 ack_ratio=round(acked/len(origin),6) if host_complete and origin else None,
                 rf_tx=len(txs) if rf_known else None,collision=count_field('collision'),
                 half_duplex=count_field('half_duplex'),filtered=count_field('filtered'),
                 module_drop=count_field('module_drop'),queue_drop=sum(e['event']=='queue_drop' for e in local),
                 airtime_sum_s=round(sum(e['duration'] for e in txs),6) if rf_known else None,
                 mean_ack_rtt_s=round(statistics.mean(rtts),6) if rtts else None,
                 end_s=max([0]+[e['t'] for e in aligned]))
    return dict(version=manifest['version'],model=manifest['model'],mode=mode,experiment_id=exp,
                scenario_sha256=manifest['scenario_sha256'],scenario=scenario,
                links=manifest.get('links',[]) if mode=='simulation' and field_complete else [],
                summary=summary,events=aligned,stream_status=status,warnings=warnings,
                observation_window_s=manifest.get('observation_window_s'),
                trace_schema_version=SCHEMA)


def write_trace(directory, manifest, streams):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if manifest.get('node_plans'):
        plans=directory/'plans';plans.mkdir(exist_ok=True)
        for node_id,plan in manifest['node_plans'].items():
            if not str(node_id).isdigit(): raise ValueError('Invalid node plan ID')
            (plans/f'node-{node_id}.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for d in manifest['streams']:
        if d['stream_id'] in streams:
            path=safe_file(directory,d['file'])
            with path.open('w',encoding='utf-8',newline='\n') as f:
                for e in streams[d['stream_id']]: f.write(json.dumps(e,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def safe_file(directory,name):
    if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.jsonl') or '/' in name or '\\' in name:
        raise ValueError('Stream file must be a simple .jsonl filename')
    return directory/name


def read_trace(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8-sig'))
    streams={}
    for d in manifest['streams']:
        p=safe_file(directory,d['file'])
        if p.is_file():
            with p.open(encoding='utf-8-sig') as f: streams[d['stream_id']]=[json.loads(line) for line in f if line.strip()]
    return manifest,streams
