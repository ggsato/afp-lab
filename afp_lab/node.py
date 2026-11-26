"""Shared host-side AFP logic. No knowledge of virtual geography or other nodes."""
from dataclasses import replace
import struct
from .afp import Packet, DATA, ACK
from .contracts import RadioInterface, NodeClock, BROADCAST

class AFPNode:
    def __init__(self, radio: RadioInterface, clock: NodeClock, log, relay, relay_delay, ack_delay, ttl):
        self.radio, self.clock, self.log = radio, clock, log
        self.address, self.relay = radio.address, relay
        self.relay_delay, self.ack_delay, self.ttl = relay_delay, ack_delay, ttl
        self.seq = 0
        self.seen, self.pending = set(), set()
        radio.set_receiver(self.receive)

    def send(self, dst, payload, link_dst=BROADCAST):
        self.seq += 1
        p = Packet(DATA, self.address, dst, self.seq, self.ttl, payload)
        self.seen.add((DATA,p.src,p.dst,p.seq))
        self.pending.add((dst,p.seq))
        self.log('origin', src=p.src, dst=p.dst, seq=p.seq, bytes=len(payload))
        if not self.emit(p, link_dst):
            self.pending.discard((dst,p.seq))

    def emit(self, p, link_dst=BROADCAST):
        accepted = self.radio.send(p.encode(), link_dst)
        if not accepted:
            self.log('send_rejected', kind='DATA' if p.kind==DATA else 'ACK',
                     src=p.src,dst=p.dst,seq=p.seq,ttl=p.ttl)
        return accepted

    def receive(self, frame):
        # Malformed/noisy/foreign bytes must not stop the node.
        try:
            p = Packet.decode(frame.payload)
        except (ValueError, struct.error):
            self.log('invalid_frame', bytes=len(frame.payload))
            return
        key = (p.kind,p.src,p.dst,p.seq)
        info = dict(kind='DATA' if p.kind==DATA else 'ACK', src=p.src,dst=p.dst,seq=p.seq,ttl=p.ttl)
        if key in self.seen:
            self.log('duplicate', **info)
            return
        self.seen.add(key)
        if p.dst == self.address:
            if p.kind == DATA:
                self.log('deliver', **info)
                self.clock.later(self.ack_delay, self.emit, Packet(ACK,self.address,p.src,p.seq,self.ttl))
            elif (p.src,p.seq) in self.pending:
                self.pending.remove((p.src,p.seq))
                self.log('ack', **info)
        elif self.relay and p.ttl > 1:
            self.log('relay', **info)
            self.clock.later(self.relay_delay, self.emit, replace(p,ttl=p.ttl-1))
        elif self.relay:
            self.log('ttl_drop', **info)

class NodeSession:
    """Install only this node's commands. at is a delay from local start.
    Real controller must arrange the start barrier; no network synchronization here.
    """
    def __init__(self, node):
        self.node=node
        self.started=False
    def start(self, commands):
        if self.started: raise RuntimeError('Session already started')
        if any(m['src'] != self.node.address for m in commands):
            raise ValueError('Node session received another node\'s command')
        self.started=True
        for m in commands:
            self.node.clock.later(m['at'],self.node.send,m['dst'],m['payload'].encode(),m['link_dst'])
