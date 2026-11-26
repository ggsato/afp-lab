import unittest
from afp_lab.afp import Packet, DATA
from afp_lab.demo import scenario

class TestAFP(unittest.TestCase):
    def test_codec(self):
        p=Packet(DATA,1,2,3,payload=b'\x00\xff')
        self.assertEqual(Packet.decode(p.encode()),p)
        with self.assertRaises(ValueError): Packet.decode(p.encode()+b'x')
    def test_relay_ack(self):
        r=scenario(); self.assertEqual(r['delivered'],1); self.assertTrue(r['acked'])
    def test_collision(self):
        r=scenario(True); self.assertEqual(r['delivered'],0); self.assertFalse(r['acked'])
        self.assertTrue(any(e['event']=='collision_or_half_duplex' for e in r['events']))

if __name__=='__main__': unittest.main()
