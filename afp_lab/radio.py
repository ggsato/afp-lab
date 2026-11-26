"""Approximate virtual E220 transport. Field truth never reaches host callbacks."""
from collections import deque
import math
import struct
from .afp import Packet
from .contracts import BROADCAST, RxFrame, RadioInterface
from .recorder import Recorder

def packet_info(raw):
    try:
        p = Packet.decode(raw)
        return dict(kind='DATA' if p.kind == 1 else 'ACK', src=p.src, dst=p.dst,
                    seq=p.seq, ttl=p.ttl)
    except (ValueError, TypeError, struct.error):
        return {}

class Field:
    def __init__(self, clock, radius, rate, overhead, recorder=None, terrain=None):
        self.clock = clock
        self.radius, self.rate, self.overhead = radius, rate, overhead
        self.radios, self.active = {}, []
        self.recorder = recorder or Recorder("standalone", "field", "simulation", "field", clock)
        self.next_tx = 1
        self.terrain = None if terrain is None else {tuple(sorted((p["a"],p["b"]))):p for p in terrain["pairs"]}

    def log(self, event, **fields):
        self.recorder.log(event, **fields)

    @property
    def events(self):
        # Compatibility for standalone tests; not a host API.
        return [dict(e,t=e['t_us']/1e6) for e in self.recorder.records]

    def reachable(self, a, b):
        if self.terrain is not None:
            return self.terrain[tuple(sorted((a.address,b.address)))]['reachable']
        return math.dist(a.position, b.position) <= self.radius

    def rssi(self, a, b):
        if self.terrain is None:return None
        return max(-256,min(-1,round(self.terrain[tuple(sorted((a,b)))]['rssi_dbm'])))

    def links(self):
        devices = list(self.radios.values())
        return [[a.address, b.address] for i, a in enumerate(devices)
                for b in devices[i+1:] if a.channel == b.channel and self.reachable(a,b)]

    def transmit(self, radio, job):
        now = self.clock.now
        raw, dest, channel, local_tx_id = job
        txid=self.next_tx; self.next_tx+=1
        duration = self.overhead + 8 * len(raw) / self.rate
        receivers = {b.address for b in self.radios.values()
                     if b is not radio and b.channel == channel and self.reachable(radio, b)}
        tx = dict(sender=radio.address, raw=raw, dest=dest, channel=channel,
                  txid=txid, local_tx_id=local_tx_id, end=now+duration, receivers=receivers, lost={})
        for other in self.active:
            if other['end'] <= now + 1e-12:
                continue
            # Different channels do not interfere in this simple model. Half duplex still applies.
            if channel == other['channel']:
                for addr in receivers & other['receivers']:
                    tx['lost'].setdefault(addr, 'collision')
                    other['lost'].setdefault(addr, 'collision')
            if radio.address in other['receivers']:
                other['lost'][radio.address] = 'half_duplex'
            if other['sender'] in receivers:
                tx['lost'][other['sender']] = 'half_duplex'
        self.active.append(tx)
        self.log('tx', sender=radio.address, link_dst=dest, channel=channel, txid=txid, local_tx_id=local_tx_id,
                 bytes=len(raw), duration=round(duration,6), candidates=sorted(receivers),
                 **packet_info(raw))
        self.clock.later(duration, self.finish, radio, tx)

    def finish(self, radio, tx):
        self.active.remove(tx)
        common = dict(sender=tx['sender'], txid=tx['txid'], local_tx_id=tx['local_tx_id'], channel=tx['channel'],
                      **packet_info(tx['raw']))
        self.log('rf_tx_end', **common)
        if not tx['receivers']:
            self.log('no_receiver', **common)
        for addr in sorted(tx['receivers']):
            if addr in tx['lost']:
                self.log(tx['lost'][addr], receiver=addr, **common)
            elif tx['dest'] not in (BROADCAST, addr):
                self.log('filtered', receiver=addr, **common)
            else:
                self.log('rf_rx', receiver=addr, **common)
                self.radios[addr].air_receive(tx['raw'], self.rssi(tx['sender'],addr))
        radio.air_done()

class VirtualE220:
    def __init__(self, field, address, position, channel, uart_baud, queue_capacity, max_frame,
                 recorder=None, module_queue_capacity=4):
        self.field, self.clock = field, field.clock
        self.address, self.position, self.channel = address, position, channel
        self.uart_baud, self.queue_capacity, self.max_frame = uart_baud, queue_capacity, max_frame
        self.module_queue_capacity=module_queue_capacity
        self.recorder=recorder or Recorder('standalone',f'node-{address}','simulation','local',self.clock,address)
        self.tx_uart_until = self.rx_uart_until = 0.0
        self.queue = deque()  # hidden model of the module, NOT a host observable
        self.outstanding = 0  # host queue incl. UART write in progress
        self.transmitting = False
        self._next_local_tx = 1
        self.callback = lambda frame: None
        field.radios[address] = self

    def capabilities(self):
        return dict(addressed_send=True, broadcast=True, max_frame=self.max_frame,
                    receive_rssi=self.field.terrain is not None, receive_snr=False, host_tx_done=False, uart_baud=self.uart_baud)

    def set_receiver(self, callback):
        self.callback = callback

    def send(self, payload, destination=BROADCAST, channel=None):
        channel = self.channel if channel is None else channel
        if not isinstance(payload, bytes) or not 1 <= len(payload) <= self.max_frame:
            raise ValueError('Invalid frame size/type')
        if not 0 <= destination <= BROADCAST or not 0 <= channel <= 30:
            raise ValueError('Invalid link destination/channel')
        if self.outstanding >= self.queue_capacity:
            self.recorder.log('queue_drop', link_dst=destination, **packet_info(payload))
            return False
        local_tx_id=self._next_local_tx; self._next_local_tx+=1
        self.outstanding += 1
        start = max(self.clock.now, self.tx_uart_until)
        duration = (3+len(payload))*10/self.uart_baud
        self.tx_uart_until = start+duration
        self.recorder.log('admitted', local_tx_id=local_tx_id, link_dst=destination,
                          uart_bytes=len(payload)+3, queue_depth=self.outstanding, **packet_info(payload))
        self.clock.later(self.tx_uart_until-self.clock.now, self.uart_done,
                         (payload,destination,channel,local_tx_id))
        return True

    def uart_done(self, job):
        # Host queue frees at local UART completion, not RF completion.
        self.outstanding -= 1
        self.recorder.log('uart_tx_end', local_tx_id=job[3], **packet_info(job[0]))
        if len(self.queue)+int(self.transmitting) >= self.module_queue_capacity:
            # Simulated module overflow is invisible to the E220 Unit host.
            self.field.log('module_drop', sender=self.address, local_tx_id=job[3],
                           link_dst=job[1], channel=job[2], **packet_info(job[0]))
            return
        self.queue.append(job)
        self.start_next()

    def start_next(self):
        if self.queue and not self.transmitting:
            self.transmitting = True
            self.field.transmit(self, self.queue.popleft())

    def air_done(self):
        self.transmitting = False
        self.start_next()

    def air_receive(self, raw, rssi=None):
        start = max(self.clock.now, self.rx_uart_until)
        self.rx_uart_until = start + (len(raw)+1)*10/self.uart_baud
        self.clock.later(self.rx_uart_until-self.clock.now, self.host_receive, raw, rssi)

    def host_receive(self, raw, rssi=None):
        # AFP source is in payload; immediate RF sender/txid is not exposed.
        self.recorder.log('rx', bytes=len(raw), rssi=rssi, **packet_info(raw))
        self.callback(RxFrame(raw,rssi))
