import copy, json, math, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
from afp_lab.coverage import compute, plan, endpoint, inspect_cell
from afp_lab.terrain import prepare, latlon, xy
from afp_lab.planner import PlannerServer, read_template
from tests.test_terrain import SyntheticDEM, png_tile
from afp_lab.dem_gsi import GsiDEM, pixel

class FlatDEM:
    def sample(self,lat,lon): return 700.0

class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.raw=read_template()
        self.request={'source_id':2,'radius_m':1000,'spacing_m':500,'receiver_antenna_m':2,'stable_margin_db':10}
    def test_one_node_without_messages(self):
        self.raw['nodes']=[self.raw['nodes'][1]];self.raw['messages']=[]
        r=compute(self.raw,self.request,FlatDEM(),'synthetic_test')
        self.assertEqual(r['plan']['cell_count'],13);self.assertEqual(r['summary']['known'],12)
        self.assertEqual(r['cells'][2][2],{'unknown':'source_location'});self.assertIsNone(r['cells'][0][0]);self.assertEqual(r['summary']['known']+r['summary']['unknown'],13)
    def test_same_model_as_pair(self):
        p=plan(self.raw,self.request);b=endpoint(p,2,4)
        raw=copy.deepcopy(self.raw);raw['nodes']=[raw['nodes'][1],dict(id=4,lat=b['lat'],lon=b['lon'],antenna_m=2)]
        raw['messages']=[]
        v=prepare(raw,SyntheticDEM(),'synthetic_test')['terrain']['pairs'][0]
        r=compute(self.raw,self.request,SyntheticDEM(),'synthetic_test');cell=r['cells'][2][4]
        self.assertEqual(cell,{k:v[k] for k in cell});self.assertEqual(inspect_cell(r,2,4,SyntheticDEM())['link']['profile'],v['profile'])
    def test_reproducible_and_original_unchanged(self):
        before=copy.deepcopy(self.raw);a=compute(self.raw,self.request,SyntheticDEM(),'synthetic_test');b=compute(self.raw,self.request,SyntheticDEM(),'synthetic_test')
        self.assertEqual(a,b);self.assertEqual(self.raw,before)
    def test_geography_independent(self):
        raw=copy.deepcopy(self.raw);raw['geography'].update(origin_lat=43,origin_lon=141);raw['nodes']=[dict(id=7,lat=43.01,lon=141.01,antenna_m=4)];raw['messages']=[]
        r=compute(raw,dict(self.request,source_id=7),FlatDEM(),'synthetic_test');self.assertEqual(r['plan']['source']['id'],7);self.assertEqual(r['summary']['known'],12)
    def test_extent_and_computation_limits(self):
        for req in [dict(self.request,radius_m=10000,spacing_m=50),dict(self.request,source_id=404),dict(self.request,spacing_m=49),dict(self.request,radius_m=float('nan')),dict(self.request,receiver_antenna_m=0)]:
            with self.assertRaises(ValueError):plan(self.raw,req)
        self.raw['geography']['profile_step_m']=5
        with self.assertRaises(ValueError):plan(self.raw,dict(self.request,radius_m=10000,spacing_m=200))
        self.raw['nodes'][1]['lon']+=.18
        with self.assertRaises(ValueError):plan(self.raw,self.request)
    def test_missing_elevation_is_unknown_not_zero(self):
        src=self.raw['nodes'][1]
        class Missing:
            def sample(self,lat,lon):
                if lon>src['lon']+.001:raise ValueError('No GSI elevation data at test')
                return 700
        r=compute(self.raw,self.request,Missing(),'synthetic_test')
        self.assertGreater(r['summary']['unknown'],1);self.assertEqual(r['cells'][2][4],{'unknown':'dem_unavailable'})
        with self.assertRaises(ValueError):inspect_cell(r,2,4,Missing())
    def test_bad_dem_and_missing_base_fail(self):
        class Bad:
            def sample(self,lat,lon):raise ValueError('PNG CRC mismatch')
        with self.assertRaisesRegex(ValueError,'CRC'):compute(self.raw,self.request,Bad())
        class Missing:
            def sample(self,lat,lon):raise ValueError('Offline cache missing test')
        with self.assertRaisesRegex(ValueError,'Offline cache'):compute(self.raw,self.request,Missing())
    def test_frozen_cell_provenance(self):
        class Fake(FlatDEM):
            def __init__(self,sha):self.provenance={'tile':{'sha256':sha}}
        r=compute(self.raw,self.request,Fake('a'))
        self.assertEqual(inspect_cell(r,2,4,Fake('a'))['link']['rssi_dbm'],r['cells'][2][4]['rssi_dbm'])
        with self.assertRaisesRegex(ValueError,'DEM cache differs'):inspect_cell(r,2,4,Fake('b'))
        with self.assertRaises(ValueError):inspect_cell(r,-1,4,Fake('a'))
        with self.assertRaises(ValueError):inspect_cell(r,0,0,Fake('a'))
    def test_margin_reclassification_no_physics_change(self):
        a=compute(self.raw,self.request,FlatDEM(),'synthetic_test');b=compute(self.raw,dict(self.request,stable_margin_db=20),FlatDEM(),'synthetic_test')
        self.assertEqual(a['cells'],b['cells']);self.assertGreaterEqual(a['summary']['stable'],b['summary']['stable'])
    def test_gsi_cache_fixture_offline(self):
        # A synthetic PNG encoded in the actual GSI format; no live GSI access.
        px,py=pixel(35.785,138.445,15);z=15;n=256*2**z
        cx=(px//256)*256+128;cy=(py//256)*256+128
        lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*cy/n))));lon=cx/n*360-180
        raw=copy.deepcopy(self.raw);raw['nodes']=[dict(id=2,lat=lat,lon=lon,antenna_m=5)];raw['messages']=[]
        req=dict(self.request,radius_m=100,spacing_m=50)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/f'dem5a_png/{z}/{px//256}/{py//256}.png';path.parent.mkdir(parents=True);path.write_bytes(png_tile([70000]))
            r=compute(raw,req,GsiDEM(tmp,True));self.assertEqual(r['summary']['known'],12);self.assertEqual(len(r['tiles']),1)
            detail=inspect_cell(r,2,4,GsiDEM(tmp,True));self.assertEqual(detail['link']['rssi_dbm'],r['cells'][2][4]['rssi_dbm'])
            path.write_bytes(png_tile([71000]))
            with self.assertRaises(ValueError):inspect_cell(r,2,4,GsiDEM(tmp,True))
    def test_http_coverage_save_and_inspect(self):
        with tempfile.TemporaryDirectory() as tmp,PlannerServer(('127.0.0.1',0),tmp,Path(tmp)/'out',dem_factory=FlatDEM,source_kind='synthetic_test') as server:
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                def post(path,data,token=server.token):
                    q=urllib.request.Request(server.origin+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':server.origin,'X-AFP-Token':token})
                    with urllib.request.urlopen(q) as response:return json.load(response)
                raw=copy.deepcopy(self.raw);raw['nodes']=[raw['nodes'][1]];raw['messages']=[]
                payload={'config':raw,'coverage':self.request}
                with self.assertRaises(urllib.error.HTTPError) as e:post('/api/coverage',payload,'invalid')
                self.assertEqual(e.exception.code,403);e.exception.close()
                result=post('/api/coverage',payload);self.assertEqual(result['result']['summary']['known'],12)
                saved=json.loads((Path(result['directory'])/'coverage.json').read_text(encoding='utf-8'));self.assertEqual(saved['config'],raw);self.assertEqual(saved['result'],result['result'])
                profile=post('/api/coverage/profile',{'run_id':result['run_id'],'row':2,'col':4});self.assertEqual(profile['link']['rssi_dbm'],result['result']['cells'][2][4]['rssi_dbm'])
                with self.assertRaises(urllib.error.HTTPError) as e:post('/api/coverage/profile',{'run_id':'../oops','row':2,'col':4})
                self.assertEqual(e.exception.code,400);e.exception.close()
            finally:server.shutdown();t.join()

if __name__=='__main__':unittest.main()
