import copy
import json
from pathlib import Path
import tempfile
import unittest
from afp_lab.afp import Packet, DATA, ACK
from afp_lab.contracts import RxFrame
from afp_lab.lab import record_scenario, run_scenario, split_config, validate, write_report
from afp_lab.node import AFPNode, NodeSession
from afp_lab.recorder import Recorder, JsonlSink, collect, read_trace, write_trace
from afp_lab.runtime import MonotonicRuntime, ClockMapping
from tests.test_v02 import sample

class TestV03(unittest.TestCase):
    def test_local_not_oracle(self):
        m,s=record_scenario(sample(1))
        for name, events in s.items():
            if name=='field': continue
            for e in events:
                self.assertEqual(e['source'],'local')
                self.assertFalse(set(e)&{'sender','receiver','txid','candidates','duration','rf_end','uart_end'})
                self.assertNotIn(e['event'],{'tx','rf_rx','rf_tx_end','collision','module_drop'})
        rx=next(e for e in s['node-3'] if e['event']=='rx')
        self.assertEqual(rx['src'],1) # origin, not relay 2
        self.assertEqual(rx['node_id'],3)
        self.assertIsNone(rx['rssi'])
    def test_clock_mapping(self):
        m,s=record_scenario(sample(6));r=collect(m,s)
        self.assertEqual(r['summary']['delivered'],1)
        self.assertEqual(r['summary']['acked'],1)
        origin=next(e for e in r['events'] if e['event']=='origin')
        delivery=next(e for e in r['events'] if e['event']=='deliver')
        ack=next(e for e in r['events'] if e['event']=='ack')
        self.assertEqual(origin['t_us'],8000000);self.assertEqual(origin['t'],0)
        self.assertGreater(delivery['t_us'],15000000);self.assertLess(delivery['t'],1)
        self.assertAlmostEqual(r['summary']['mean_ack_rtt_s'],(ack['t_us']-origin['t_us'])/1e6)
        self.assertEqual(origin['clock_uncertainty_us'],1)
    def test_missing_field_does_not_change_host_metrics(self):
        m,s=record_scenario(sample(1));baseline=collect(m,s)
        del s['field'];r=collect(m,s)
        for k in ('offered','delivered','acked','pdr','ack_ratio','mean_ack_rtt_s'):
            self.assertEqual(r['summary'][k],baseline['summary'][k])
        for k in ('rf_tx','collision','half_duplex','filtered','airtime_sum_s','module_drop'):
            self.assertIsNone(r['summary'][k])
        self.assertEqual(r['links'],[])
    def test_missing_local_not_failure(self):
        m,s=record_scenario(sample(1));del s['node-3'];r=collect(m,s)
        self.assertFalse(r['summary']['local_complete']);self.assertIsNone(r['summary']['pdr']);self.assertIsNone(r['summary']['ack_ratio'])
    def test_truncated_stream_not_complete(self):
        m,s=record_scenario(sample(1));s['node-3'].pop();r=collect(m,s)
        self.assertFalse(r['summary']['local_complete']);self.assertIsNone(r['summary']['pdr'])
    def test_unsynchronized_no_timeline_invention(self):
        m,s=record_scenario(sample(1));next(d for d in m['streams'] if d['node_id']==3)['clock_mapping']=None
        r=collect(m,s);self.assertEqual(r['summary']['pdr'],1)
        self.assertFalse(any(e['node_id']==3 for e in r['events']))
        self.assertTrue(any('Unaligned' in w for w in r['warnings']))
    def test_jsonl_roundtrip(self):
        m,s=record_scenario(sample(6));r=collect(m,s)
        with tempfile.TemporaryDirectory() as d:
            write_trace(d,m,s);self.assertEqual(collect(*read_trace(d)),r)
    def test_host_queue_not_held_until_rf_done(self):
        raw=sample(4);raw['radio']['queue_capacity']=1;raw['radio']['module_queue_capacity']=1
        raw['messages']=raw['messages'][:2];raw['messages'][1]['at']=.05
        r=run_scenario(raw)
        self.assertEqual(r['summary']['queue_drop'],0)
        self.assertEqual(r['summary']['module_drop'],1)
        self.assertEqual(r['summary']['delivered'],1)
        self.assertEqual(sum(e['event']=='admitted' and e['node_id']==1 for e in r['events']),2)
    def test_local_config_no_field_data(self):
        plans,env=split_config(validate(sample(6)))
        self.assertEqual({m['src'] for m in plans[1]['commands']},{1})
        self.assertFalse(set(plans[1])&{'x','y','radius_m','clock_offset_us','clock_drift_ppm','module_queue_capacity'})
        self.assertIn('radius_m',env)
    def test_node_runtime_non_simulator(self):
        # A standalone host with injected monotonic source + stub radio, no Field.
        t=[0.0];clock=MonotonicRuntime(lambda:t[0]);rec=Recorder('fixture','node-1','physical','local',clock,1)
        class StubRadio:
            address=1
            def set_receiver(self,cb): self.cb=cb
            def send(self,raw,destination): self.sent=raw;return True
        radio=StubRadio();node=AFPNode(radio,clock,rec.log,False,.1,.2,4);session=NodeSession(node)
        session.start([dict(src=1,dst=2,at=.1,payload='x',link_dst=2)])
        self.assertEqual(clock.poll(),0);t[0]=.1;self.assertEqual(clock.poll(),1)
        self.assertEqual(Packet.decode(radio.sent).payload,b'x')
        t[0]=.2;radio.cb(RxFrame(b'bad'));radio.cb(RxFrame(Packet(ACK,2,1,1).encode(),-85))
        self.assertEqual([e['event'] for e in rec.records],['origin','invalid_frame','ack'])
    def test_physical_offline_collector(self):
        # Constructed fixture, NOT real hardware measurements.
        scenario=validate(sample(3));from afp_lab.recorder import scenario_digest
        clocks=[MonotonicRuntime(lambda:0),MonotonicRuntime(lambda:0),MonotonicRuntime(lambda:0)]
        recs=[Recorder('physical-fixture',f'node-{i}','physical','local',clocks[i-1],i) for i in (1,2,3)]
        recs[0].log('origin',src=1,dst=2,seq=1,bytes=3);recs[1].log('deliver',src=1,dst=2,seq=1,kind='DATA',ttl=4)
        recs[0].log('ack',src=2,dst=1,seq=1,kind='ACK',ttl=4)
        m=dict(schema_version=1,version='0.3.0',model='fixture',mode='physical',experiment_id='physical-fixture',scenario=scenario,scenario_sha256=scenario_digest(scenario),streams=[r.descriptor(ClockMapping(0,0,1,1000,'fixture')) for r in recs])
        r=collect(m,{x.stream_id:x.records for x in recs});self.assertEqual(r['summary']['pdr'],1);self.assertIsNone(r['summary']['collision']);self.assertIsNone(r['summary']['rf_tx'])
        with tempfile.TemporaryDirectory() as d: write_report([r],Path(d))
    def test_reject_oracle_field_in_local_stream(self):
        m,s=record_scenario(sample(1));s['node-1'][0]['sender']=1
        with self.assertRaises(ValueError):collect(m,s)
    def test_observation_window_limits_execution(self):
        raw=sample(1);raw['duration_s']=.05;r=run_scenario(raw)
        self.assertEqual(r['summary']['offered'],1);self.assertEqual(r['summary']['delivered'],0)
        self.assertEqual(r['observation_window_s'],.05);self.assertLessEqual(r['summary']['end_s'],.05)

    def test_start_skew(self):
        raw=sample(1);raw['nodes'][0]['start_delay_s']=.25
        r=run_scenario(raw);origin=next(e for e in r['events'] if e['event']=='origin')
        self.assertAlmostEqual(origin['t'],.25,places=6)
        self.assertEqual(r['summary']['delivered'],1)
    def test_incremental_local_sink(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'node-1.jsonl';clock=MonotonicRuntime(lambda:0)
            with JsonlSink(path) as sink:
                r=Recorder('fixture','node-1','physical','local',clock,1,sink=sink,retain=False)
                r.log('origin',src=1,dst=2,seq=1)
                self.assertEqual(r.records,[])
                self.assertEqual(r.descriptor(None)['record_count'],1)
                self.assertEqual(json.loads(path.read_text())['event_seq'],1)
            with self.assertRaises(FileExistsError):
                with JsonlSink(path): pass
