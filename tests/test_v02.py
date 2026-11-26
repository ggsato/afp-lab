import copy
import json
from pathlib import Path
import tempfile
import unittest
from afp_lab.afp import Clock, Packet, DATA
from afp_lab.lab import run_scenario, validate, write_report
from afp_lab.radio import VirtualE220, Field

from afp_lab.paths import CONFIG_ROOT

def sample(n):
    return json.loads(next((CONFIG_ROOT/'scenarios').glob(f'{n:02d}_*.json')).read_text(encoding='utf-8'))

class TestV02(unittest.TestCase):
    def test_relay_and_ack(self):
        r=run_scenario(sample(1)); s=r['summary']
        self.assertEqual((s['delivered'],s['acked'],s['rf_tx']), (1,1,4))
        self.assertAlmostEqual(s['mean_ack_rtt_s'],1.173919,places=6)
        self.assertEqual([e['sender'] for e in r['events'] if e['event']=='tx'],[1,2,3,2])
        self.assertEqual(r['links'],[[1,2],[2,3]])
    def test_hidden_collision_and_stagger(self):
        c=run_scenario(sample(2))['summary']; d=run_scenario(sample(5))['summary']
        self.assertEqual((c['delivered'],c['collision']), (0,2))
        self.assertEqual((d['delivered'],d['acked'],d['collision']), (2,2,0))
    def test_addressed_filter(self):
        r=run_scenario(sample(3))
        self.assertEqual(r['summary']['filtered'],1)
        self.assertTrue(any(e['event']=='filtered' and e['receiver']==3 for e in r['events']))
        self.assertFalse(any(e['event']=='rx' and e.get('src')==1 and e.get('node_id')==3 for e in r['events']))
    def test_queue_drop_and_recovery(self):
        r=run_scenario(sample(4));s=r['summary']
        self.assertEqual((s['offered'],s['delivered'],s['acked'],s['queue_drop']), (3,2,2,1))
        ids=[e['seq'] for e in r['events'] if e['event']=='queue_drop']
        self.assertEqual(ids,[3])
    def test_ttl_and_no_relay(self):
        r=sample(1);r['radio']['ttl']=1
        self.assertEqual(run_scenario(r)['summary']['delivered'],0)
        r=sample(1);r['nodes'][1]['relay']=False
        self.assertEqual(run_scenario(r)['summary']['delivered'],0)
    def test_channel_separation(self):
        r=sample(3);r['nodes'][1]['channel']=1
        self.assertEqual(run_scenario(r)['summary']['delivered'],0)
    def test_half_duplex(self):
        r=sample(2);r['nodes'][2]['x']=400
        s=run_scenario(r)['summary'];self.assertEqual(s['half_duplex'],2)
        self.assertEqual(s['delivered'],0)
    def test_filter_does_not_prevent_rf_collision(self):
        r=sample(2);r['messages'][0]['link_dst']=2;r['messages'][1]['link_dst']=1
        s=run_scenario(r)['summary'];self.assertEqual(s['collision'],2)
    def test_uart_model_binary(self):
        c=Clock();f=Field(c,1000,1758,.05)
        a=VirtualE220(f,1,(0,0),0,9600,2,200)
        b=VirtualE220(f,2,(10,0),0,9600,2,200)
        received=[];b.set_receiver(received.append)
        data=Packet(DATA,1,2,1,payload=b'\x00\xff\x00').encode()
        self.assertTrue(a.send(data,2));self.assertEqual(received,[])
        c.run();self.assertEqual(received[0].payload,data);self.assertIsNone(received[0].rssi)
        self.assertFalse(a.capabilities()['host_tx_done'])
        tx=next(e for e in f.events if e['event']=='tx')
        self.assertAlmostEqual(tx['t'],(len(data)+3)*10/9600,places=6)
        self.assertEqual(a.outstanding,0)
    def test_invalid_scenarios(self):
        r=sample(1);r['nodes'][1]['id']=1
        with self.assertRaises(ValueError):validate(r)
        r=sample(1);r['messages'][0]['payload']='x'*188
        with self.assertRaises(ValueError):validate(r)
        r=sample(1);r['radio']['radius_m']=float('nan')
        with self.assertRaises(ValueError):validate(r)
    def test_reproducibility(self):
        self.assertEqual(run_scenario(sample(1)),run_scenario(sample(1)))
    def test_report_embeds_data_safely(self):
        r=sample(1);r['name']='</script><script>alert(1)</script>'
        result=run_scenario(r)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);path=write_report([result],out)
            self.assertEqual(json.loads((out/'experiments.json').read_text(encoding='utf-8'))['results'][0],result)
            content=path.read_text(encoding='utf-8');self.assertNotIn(r['name'],content)
            self.assertNotIn('/*__AFP_DATA__*/',content)

if __name__=='__main__':unittest.main()
