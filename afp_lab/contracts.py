"""Host-visible contracts only. No simulator, global clock, or RF oracle."""
from dataclasses import dataclass
from typing import Callable, Protocol

BROADCAST = 0xffff

@dataclass(frozen=True)
class RxFrame:
    payload: bytes
    rssi: int | None = None

class RadioInterface(Protocol):
    address: int
    def send(self, payload: bytes, destination: int = BROADCAST,
             channel: int | None = None) -> bool:
        """Admission to the HOST queue only; not module admission or RF delivery."""
        ...
    def set_receiver(self, callback: Callable[[RxFrame], None]) -> None: ...
    def capabilities(self) -> dict: ...

class NodeClock(Protocol):
    @property
    def now(self) -> float: ...
    def later(self, delay: float, callback: Callable, *args) -> None: ...
