import copy, json, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from afp_lab.planner import read_template, check_config, run_layout, PlannerServer
from tests.test_terrain import SyntheticDEM
from afp_lab.lab import validate
from afp_lab.recorder import collect, read_trace

class TestPlanner(unittest.TestCase):
    def test_original_geography_valid(self):
        raw=read_template();before=copy.deepcopy(raw)
        self.assertEqual(check_config(raw),before);self.assertEqual(raw,before)
    def test_reject_duplicate_id_before_dem(self):
        raw=read_template();raw['nodes'][1]['id']=1
        with self.assertRaises(ValueError):check_config(raw)
    def test_reject_deleted_message_endpoint(self):
        raw=read_template();raw['nodes'].pop(1)
        with self.assertRaises(ValueError):check_config(raw)
    def test_reject_outside_region(self):
        raw=read_template();raw['nodes'][0]['lat']+=1
        with self.assertRaises(ValueError):check_config(raw)
    def test_reject_collocated_nodes(self):
        raw=read_template();raw['nodes'][0].update(lat=raw['nodes'][1]['lat'],lon=raw['nodes'][1]['lon'])
        with self.assertRaises(ValueError):check_config(raw)
    def test_reject_invalid_height_and_prepared(self):
        raw=read_template();raw['nodes'][0]['antenna_m']=0
        with self.assertRaises(ValueError):check_config(raw)
        raw=read_template();raw['terrain']={}
        with self.assertRaises(ValueError):check_config(raw)
    def test_roundtrip_and_frozen_terrain(self):
        raw=read_template();raw['planner']={'home_id':2,'base_id':2,'mode':'auto'}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';r=run_layout(raw,SyntheticDEM(),out,True,3,'synthetic_test')
            self.assertEqual(len(r['pairs']),3);self.assertEqual(len(r['summaries']),2)
            self.assertEqual(r['source_kind'],'synthetic_test');self.assertEqual(json.loads((out/'geography.json').read_text(encoding='utf-8')),raw)
            a,b=[json.loads((out/f'prepared-{i:02d}.json').read_text(encoding='utf-8')) for i in (1,2)]
            self.assertEqual(a['terrain'],b['terrain']);self.assertEqual([m['at'] for m in b['messages']],[0,3]);self.assertEqual(r['summaries'][1]['summary'],collect(*read_trace(out/'traces'/'02'))['summary'])
            self.assertNotIn('planner',json.loads((out/'traces'/'01'/'manifest.json').read_text(encoding='utf-8'))['node_plans']['1'])
            self.assertTrue((out/'index.html').is_file())
    def test_compare_existing_staggered(self):
        raw=read_template();raw['messages'][1]['at']=3
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';r=run_layout(raw,SyntheticDEM(),out,True,3,'synthetic_test')
            self.assertEqual(len(r['summaries']),2);b=json.loads((out/'prepared-02.json').read_text(encoding='utf-8'));self.assertEqual([m['at'] for m in b['messages']],[0,0])
    def test_http_local_security_and_config(self):
        with tempfile.TemporaryDirectory() as tmp, PlannerServer(('127.0.0.1',0),tmp,tmp,True) as server:
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                url=server.origin
                with urllib.request.urlopen(url+'/api/config') as r:data=json.load(r)
                self.assertTrue(data['offline']);self.assertEqual(data['config'],read_template())
                body=json.dumps({'config':read_template()}).encode()
                req=urllib.request.Request(url+'/api/run',data=body,headers={'Content-Type':'application/json','Origin':'https://other.invalid','X-AFP-Token':data['token']})
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
                self.assertEqual(e.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url+'/README.md')
                self.assertEqual(e.exception.code,404)
                req=urllib.request.Request(url+'/api/run',data=body,headers={'Content-Type':'application/json','Origin':url,'X-AFP-Token':data['token']})
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
                self.assertEqual(e.exception.code,400);self.assertIn('Offline cache missing',json.load(e.exception)['error'])
            finally:server.shutdown();t.join()
    def test_http_run_report_success(self):
        with tempfile.TemporaryDirectory() as tmp, PlannerServer(('127.0.0.1',0),tmp,Path(tmp)/'runs',dem_factory=SyntheticDEM,source_kind='synthetic_test') as server:
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                url=server.origin
                with urllib.request.urlopen(url+'/api/config') as response: data=json.load(response)
                body=json.dumps({'config':read_template(),'compare':True,'interval':3}).encode()
                req=urllib.request.Request(url+'/api/run',data=body,headers={'Content-Type':'application/json','Origin':url,'X-AFP-Token':data['token']})
                with urllib.request.urlopen(req) as response: result=json.load(response)
                self.assertEqual(result['source_kind'],'synthetic_test');self.assertEqual(len(result['pairs']),3)
                self.assertEqual(len(result['summaries']),2)
                with urllib.request.urlopen(url+result['report_url']) as response: self.assertIn(b'Network Observatory',response.read())
                self.assertTrue((Path(result['directory'])/'geography.json').is_file())
            finally:server.shutdown();t.join()
if __name__=='__main__':unittest.main()
