import copy, json, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
from afp_lab.paths import WEB_ROOT
from afp_lab.field_config import load_field, check_field, default_path
from afp_lab.planner import check_config, run_layout, PlannerServer
from afp_lab.providers import provider_ids, create_dem, MAP_PROVIDERS
from afp_lab.terrain import GsiDEM, prepare
from tests.test_terrain import SyntheticDEM


def other_field():
    """Synthetic candidate coordinates in another region, not measured sites."""
    return {'name':'Another region experiment','geography':{'origin_lat':43.06,'origin_lon':141.35,'dem_provider':'gsi_dem'},
            'nodes':[{'id':1,'lat':43.061,'lon':141.35,'antenna_m':3},{'id':2,'lat':43.062,'lon':141.36,'antenna_m':3}],
            'messages':[{'src':1,'dst':2,'at':0,'payload':'test'}],'duration_s':10,
            'planner':{'field_name':'Test region','view':{'lat':43.08,'lon':141.37,'zoom':15,'layer':'pale'},'map_provider':'gsi','mode':'auto','base_id':2}}

class FlatDEM:
    def sample(self, lat, lon): return 50.0

class TestFieldConfig(unittest.TestCase):
    def test_default_is_data_selected(self):
        self.assertEqual(load_field(), json.loads(default_path().read_text(encoding='utf-8')))
        self.assertIn('view',load_field()['planner'])
        self.assertNotIn('35.785', (WEB_ROOT/'planner.html').read_text(encoding='utf-8'))
    def test_legacy_without_metadata(self):
        raw=load_field(); raw.pop('planner'); raw['geography'].pop('dem_provider')
        self.assertEqual(provider_ids(raw),('gsi','gsi_dem'));self.assertEqual(check_config(raw),raw)
    def test_empty_and_one_node_drafts(self):
        raw=other_field();raw['nodes']=[];raw['messages']=[]
        self.assertEqual(check_field(raw),raw)
        with self.assertRaises(ValueError):check_config(raw)
        raw['nodes']=other_field()['nodes'][:1];self.assertEqual(check_field(raw),raw)
        with self.assertRaises(ValueError):check_config(raw)
    def test_field_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'field.json';raw=other_field();f.write_text(json.dumps(raw),encoding='utf-8-sig');self.assertEqual(load_field(f),raw)
    def test_other_region_end_to_end(self):
        raw=other_field();before=copy.deepcopy(raw)
        with tempfile.TemporaryDirectory() as tmp:
            r=run_layout(raw,FlatDEM(),Path(tmp)/'run',source_kind='synthetic_test')
            self.assertEqual(r['summaries'][0]['summary']['delivered'],1)
            frozen=json.loads((Path(tmp)/'run'/'prepared-01.json').read_text(encoding='utf-8'))
            self.assertEqual(frozen['terrain']['origin_lat'],43.06);self.assertEqual(frozen['terrain']['nodes'][0]['ground_m'],50)
            self.assertEqual(json.loads((Path(tmp)/'run'/'geography.json').read_text(encoding='utf-8')),before)
            manifest=json.loads((Path(tmp)/'run'/'traces'/'01'/'manifest.json').read_text(encoding='utf-8'))
            self.assertNotIn('planner',manifest['node_plans']['1']);self.assertNotIn('geography',manifest['node_plans']['1'])
        self.assertEqual(raw,before)
    def test_view_does_not_change_terrain(self):
        raw=other_field();a=prepare(raw,FlatDEM(),'synthetic_test');raw['planner']['view'].update(lat=35.6,lon=139.7,zoom=8,layer='none');b=prepare(raw,FlatDEM(),'synthetic_test');self.assertEqual(a['terrain'],b['terrain'])
    def test_origin_change_and_outside_limit(self):
        raw=other_field();before=prepare(raw,FlatDEM(),'synthetic_test');raw['geography']['origin_lon']+=.01
        after=prepare(raw,FlatDEM(),'synthetic_test');self.assertNotEqual(before['nodes'][0]['x'],after['nodes'][0]['x']);self.assertEqual(after['terrain']['nodes'][0]['lat'],before['terrain']['nodes'][0]['lat'])
        raw['geography']['origin_lon']=138.445;check_field(raw)
        with self.assertRaises(ValueError):check_config(raw)
    def test_invalid_view_and_providers(self):
        for key,value in [('zoom',19),('lat',90),('layer','unknown')]:
            raw=other_field();raw['planner']['view'][key]=value
            with self.assertRaises(ValueError):check_field(raw)
        for group,key in [('planner','map_provider'),('geography','dem_provider')]:
            raw=other_field();raw[group][key]='https://invalid.example'
            with self.assertRaises(ValueError):check_config(raw)
            if group=='geography':
                with self.assertRaises(ValueError):prepare(raw,FlatDEM(),'synthetic_test')
            else:
                self.assertEqual(prepare(raw,FlatDEM(),'synthetic_test')['terrain'],prepare(other_field(),FlatDEM(),'synthetic_test')['terrain'])
    def test_provider_adapter_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsInstance(create_dem('gsi_dem',tmp,True),GsiDEM)
            with self.assertRaises(ValueError):create_dem('other',tmp)
        self.assertEqual(set(MAP_PROVIDERS['gsi']['layers']),{'std','pale','relief','seamlessphoto'})
    def test_custom_startup_and_provider_api(self):
        with tempfile.TemporaryDirectory() as tmp, PlannerServer(('127.0.0.1',0),tmp,tmp,True,config=other_field()) as server:
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                with urllib.request.urlopen(server.origin+'/api/config') as response:r=json.load(response)
                self.assertEqual(r['config'],other_field());self.assertIn('gsi',r['map_providers']);self.assertIn('gsi_dem',r['dem_providers'])
                raw=other_field();raw['geography']['dem_provider']='unknown'
                req=urllib.request.Request(server.origin+'/api/run',data=json.dumps({'config':raw}).encode(),headers={'Origin':server.origin,'X-AFP-Token':r['token'],'Content-Type':'application/json'})
                with patch('afp_lab.planner.create_dem') as factory:
                    with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
                    self.assertEqual(err.exception.code,400);factory.assert_not_called()
            finally:server.shutdown();t.join()

if __name__=='__main__':unittest.main()
