"""Independent node clocks. Callbacks are serialized on a local event loop."""
import heapq
import itertools
import time
from dataclasses import dataclass

class SimulationEngine:
    def __init__(self):
        self.now = 0.0
        self._queue = []
        self._order = itertools.count()
    def later(self, delay, fn, *args):
        if delay < 0: raise ValueError('Negative delay')
        heapq.heappush(self._queue, (self.now+delay, next(self._order), fn, args))
    def run_until(self, end):
        if end < self.now: raise ValueError('Time cannot go backwards')
        count = 0
        while self._queue and self._queue[0][0] <= end:
            self.now, _, fn, args = heapq.heappop(self._queue)
            fn(*args); count += 1
            if count > 300000: raise RuntimeError('Simulation callback limit')
        self.now = end

@dataclass(frozen=True)
class ClockMapping:
    """t_experiment_us = reference_us + (t_local_us - local_anchor_us) * scale.
    uncertainty_us is a declared bound/estimate over the capture window, not a guarantee.
    """
    local_anchor_us: int
    reference_us: int
    scale: float = 1.0
    uncertainty_us: int = 0
    method: str = 'declared'
    def __post_init__(self):
        import math
        if (type(self.local_anchor_us) is not int or type(self.reference_us) is not int
            or type(self.uncertainty_us) is not int or self.uncertainty_us < 0
            or type(self.scale) not in (float,int) or not math.isfinite(self.scale) or self.scale <= 0
            or not isinstance(self.method,str) or not self.method):
            raise ValueError('Invalid clock mapping')
    def align(self, t_us):
        return self.reference_us + round((t_us-self.local_anchor_us)*self.scale)

class VirtualNodeClock:
    def __init__(self, engine, offset_us=0, drift_ppm=0):
        self._engine = engine
        self._offset = offset_us / 1e6
        self._rate = 1 + drift_ppm / 1e6
        self.mapping = ClockMapping(offset_us,0,1/self._rate,1,'simulation_exact_model')
    @property
    def now(self):
        return self._offset + self._engine.now*self._rate
    def later(self, delay, callback, *args):
        self._engine.later(delay/self._rate,callback,*args)

class MonotonicRuntime:
    """Host-side local scheduler for future real adapters; no background threads.
    poll() must be called by the device loop, along with its radio polling.
    """
    def __init__(self, monotonic=time.monotonic):
        self._monotonic = monotonic
        self._start = monotonic()
        self._queue = []
        self._order = itertools.count()
    @property
    def now(self): return self._monotonic()-self._start
    def later(self,delay,callback,*args):
        if delay < 0: raise ValueError('Negative delay')
        heapq.heappush(self._queue,(self.now+delay,next(self._order),callback,args))
    def poll(self, limit=1000):
        count=0
        while self._queue and self._queue[0][0] <= self.now and count < limit:
            _,_,fn,args=heapq.heappop(self._queue);fn(*args);count+=1
        return count
