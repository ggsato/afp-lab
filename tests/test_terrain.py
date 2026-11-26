import copy, json, math, struct, tempfile, unittest, zlib
from pathlib import Path
from unittest.mock import patch
from afp_lab.terrain import GsiDEM, decode_png, path_model, pixel, prepare, xy
from afp_lab.lab import run_scenario, record_scenario, validate, write_report
from afp_lab.recorder import collect, write_trace, read_trace

from afp_lab.paths import CONFIG_ROOT

def png_tile(values):
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    row=b''.join((v & 0xffffff).to_bytes(3,'big') for v in values)
    row=(row*((256+len(values)-1)//len(values)))[:768]
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',256,256,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+row)*256))+chunk(b'IEND',b'')

class SyntheticDEM:
    """Test-only hills, no field observations or GSI data."""
    def sample(self,lat,lon):
        x,y=xy(lat,lon,35.785,138.445)
        return 650+.015*x+25*math.exp(-((x-500)/850)**2)+8*math.sin(y/600)

class TestTerrain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads((CONFIG_ROOT/'geography'/'akeno.json').read_text(encoding='utf-8'))
        cls.terrain=prepare(cls.raw,SyntheticDEM(),'synthetic_test')
    def test_png_signed_nodata(self):
        p=decode_png(png_tile([12345,-1234,0x800000]));self.assertEqual(p[0][:3],[123.45,-12.34,None]);self.assertEqual(len(p),256)
    def test_png_crc(self):
        p=bytearray(png_tile([1]));p[25]^=1
        with self.assertRaises(ValueError):decode_png(p)
    def test_cache_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=png_tile([75000]);dem=GsiDEM(tmp,offline=True)
            px,py=pixel(35.785,138.445,15);path=Path(tmp)/f'dem5a_png/15/{px//256}/{py//256}.png';path.parent.mkdir(parents=True);path.write_bytes(p)
            self.assertEqual(dem.sample(35.785,138.445),750)
            self.assertEqual(len(dem.provenance),1)
            with self.assertRaises(ValueError):dem.sample(35.9,138.4)
    def test_gsi_download_then_offline(self):
        p=png_tile([80000]);from io import BytesIO
        with tempfile.TemporaryDirectory() as tmp:
            with patch('urllib.request.urlopen',return_value=BytesIO(p)) as fetch:
                a=GsiDEM(tmp);self.assertEqual(a.sample(35.785,138.445),800);self.assertEqual(fetch.call_count,1)
                b=GsiDEM(tmp,True);self.assertEqual(b.sample(35.785,138.445),800);self.assertEqual(a.provenance,b.provenance);self.assertEqual(fetch.call_count,1)
    def test_nodata_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            for layer,z,v in [('dem5a_png',15,0x800000),('dem5b_png',15,90000)]:
                px,py=pixel(35.785,138.445,z);path=Path(tmp)/f'{layer}/{z}/{px//256}/{py//256}.png';path.parent.mkdir(parents=True);path.write_bytes(png_tile([v]))
            self.assertEqual(GsiDEM(tmp,True).sample(35.785,138.445),900)
    def test_path_physics(self):
        a={'id':1,'x':0,'y':0,'antenna_m':30};b={'id':2,'x':5000,'y':0,'antenna_m':30}
        flat=path_model(a,b,[0]*101);ridge=path_model(a,b,[0]*50+[100]+[0]*50)
        self.assertAlmostEqual(flat['fspl_db'],105.73,places=1);self.assertTrue(flat['los']);self.assertTrue(flat['fresnel60']);self.assertFalse(ridge['los']);self.assertGreater(ridge['diffraction_db'],20);self.assertLess(ridge['rssi_dbm'],flat['rssi_dbm'])
    def test_height_improves_clearance(self):
        a={'id':1,'x':0,'y':0,'antenna_m':2};b={'id':2,'x':1000,'y':0,'antenna_m':2};profile=[0,20,0]
        low=path_model(a,b,profile);a['antenna_m']=40;b['antenna_m']=40;high=path_model(a,b,profile)
        self.assertGreater(high['margin_db'],low['margin_db']);self.assertTrue(high['los'])
    def test_prepare_and_reproducibility(self):
        self.assertEqual(self.terrain,prepare(self.raw,SyntheticDEM(),'synthetic_test'))
        self.assertEqual(len(self.terrain['terrain']['pairs']),3)
        self.assertEqual(len(self.terrain['terrain']['grid']['values']),41)
    def test_field_not_in_node_plan(self):
        m,s=record_scenario(self.terrain)
        self.assertIn('terrain',m['virtual_environment']);self.assertNotIn('terrain',m['node_plans']['1']);self.assertNotIn('lat',m['node_plans']['1'])
        self.assertEqual(m['model'],'fspl-dominant-knife-edge-v1')
        self.assertTrue(all('sender' not in e for stream,events in s.items() if stream!='field' for e in events))
    def test_threshold_not_radius(self):
        t=copy.deepcopy(self.terrain);t['radio']['radius_m']=1;t['messages']=t['messages'][:1]
        r=run_scenario(t);expected=t['terrain']['pairs'][0]['reachable'];self.assertTrue(expected);self.assertEqual(r['summary']['delivered'],1)
        # RF observation available in local trace, not knowledge of remote sender.
        self.assertTrue(any(e.get('rssi') is not None for e in r['events'] if e['event']=='rx'))
    def test_same_terrain_stagger(self):
        t=copy.deepcopy(self.terrain);a=run_scenario(t);t['messages'][1]['at']=3;b=run_scenario(t)
        self.assertEqual(a['summary']['delivered'],0);self.assertEqual(b['summary']['delivered'],2)
        self.assertEqual(a['scenario']['terrain'],b['scenario']['terrain'])
    def test_frozen_scenario_validation(self):
        t=copy.deepcopy(self.terrain);t['nodes'][0]['x']+=1
        with self.assertRaises(ValueError):validate(t)
        t=copy.deepcopy(self.terrain);t['nodes'][0]['antenna_m']+=1
        with self.assertRaises(ValueError):validate(t)
        with self.assertRaises(ValueError):validate(self.raw)
    def test_offline_replay(self):
        m,s=record_scenario(self.terrain);r=collect(m,s)
        with tempfile.TemporaryDirectory() as tmp:
            write_trace(tmp,m,s);self.assertEqual(collect(*read_trace(tmp)),r)
        s.pop('field');r2=collect(m,s);self.assertEqual(r['summary']['pdr'],r2['summary']['pdr']);self.assertIsNone(r2['summary']['rf_tx'])

if __name__=='__main__':unittest.main()
