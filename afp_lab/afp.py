"""AFP v0.1 experimental simulator; not an E220 firmware emulator."""
from dataclasses import dataclass, replace
import heapq
import itertools
import math
import struct

HEADER = struct.Struct('>BBHHIBH')
DATA, ACK = 1, 2

@dataclass(frozen=True)
class Packet:
    kind: int
    src: int
    dst: int
    seq: int
    ttl: int = 4
    payload: bytes = b''

    def encode(self):
        return HEADER.pack(1,self.kind,self.src,self.dst,self.seq,self.ttl,len(self.payload))+self.payload

    @classmethod
    def decode(cls, raw):
        version,kind,src,dst,seq,ttl,n=HEADER.unpack_from(raw)
        if version!=1 or kind not in (DATA,ACK) or len(raw)!=HEADER.size+n:
            raise ValueError('invalid frame')
        return cls(kind,src,dst,seq,ttl,raw[HEADER.size:])

class Clock:
    def __init__(self):
        self.now=0.; self.queue=[]; self.order=itertools.count()
    def later(self, delay, fn, *args):
        heapq.heappush(self.queue,(self.now+delay,next(self.order),fn,args))
    def run(self):
        while self.queue:
            self.now,_,fn,args=heapq.heappop(self.queue); fn(*args)

class Medium:
    def __init__(self, clock, rate=1758, radius=1000):
        self.clock=clock; self.rate=rate; self.radius=radius
        self.nodes={}; self.active=[]; self.log=[]
    def event(self, kind, **kw):
        self.log.append(dict(t=round(self.clock.now,6),event=kind,**kw))
    def reachable(self,a,b):
        return math.dist(self.nodes[a].position,self.nodes[b].position)<=self.radius
    def send(self, sender, raw):
        if len(raw)>200: raise ValueError('frame exceeds experimental limit')
        if any(t['sender']==sender for t in self.active):
            self.event('busy',sender=sender); return False
        receivers={a for a in self.nodes if a!=sender and self.reachable(sender,a)}
        tx=dict(sender=sender,raw=raw,receivers=receivers,lost=set())
        for other in self.active:
            # Simplified same-channel collision and half-duplex model.
            tx['lost'].update(receivers & other['receivers'])
            other['lost'].update(receivers & other['receivers'])
            if sender in other['receivers']: other['lost'].add(sender)
            if other['sender'] in receivers: tx['lost'].add(other['sender'])
        self.active.append(tx)
        duration=0.05+8*len(raw)/self.rate
        self.event('tx',sender=sender,bytes=len(raw),duration=round(duration,6))
        self.clock.later(duration,self.finish,tx); return True
    def finish(self,tx):
        self.active.remove(tx)
        for address in sorted(tx['receivers']):
            if address in tx['lost']:
                self.event('collision_or_half_duplex',sender=tx['sender'],receiver=address)
            else:
                self.event('rx',sender=tx['sender'],receiver=address)
                self.nodes[address].receive(tx['raw'])

class Node:
    def __init__(self, medium, address, position, relay=False):
        self.medium=medium; self.address=address; self.position=position; self.relay=relay
        self.seq=0; self.seen=set(); self.delivered=[]; self.acked=set(); self.pending=set()
        medium.nodes[address]=self
    def emit(self,p):
        return self.medium.send(self.address,p.encode())
    def send(self,dst,payload):
        self.seq+=1; p=Packet(DATA,self.address,dst,self.seq,payload=payload)
        self.seen.add((DATA,p.src,p.dst,p.seq)); self.pending.add((dst,p.seq))
        self.emit(p); return p.seq
    def receive(self,raw):
        p=Packet.decode(raw); key=(p.kind,p.src,p.dst,p.seq)
        if key in self.seen: return
        self.seen.add(key)
        if p.dst==self.address:
            if p.kind==DATA:
                self.delivered.append(p)
                self.medium.clock.later(.2,self.emit,Packet(ACK,self.address,p.src,p.seq))
            elif (p.src,p.seq) in self.pending:
                self.acked.add((p.src,p.seq)); self.pending.remove((p.src,p.seq))
                self.medium.event('ack',node=self.address,peer=p.src,seq=p.seq)
        elif self.relay and p.ttl>1:
            self.medium.clock.later(.1,self.emit,replace(p,ttl=p.ttl-1))
