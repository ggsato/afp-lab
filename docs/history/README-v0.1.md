# AKENO Field Protocol Lab v0.1

Python 3.10+ / standard library only.

```sh
python3 -m unittest -v
python3 demo.py
```

Experimental packet: version(1), kind(1), source(2), destination(2), sequence(4), TTL(1), payload length(2), payload. Big endian. No security: simulation only.

Deterministic event clock; three nodes, middle node relays by flooding with duplicate suppression and TTL. ACK is an end-to-end experimental acknowledgment. Simultaneous transmissions to a common receiver collide. Half-duplex modeled. No retries, persistence, authentication, scheduling, realistic path loss, capture effect, LBT, hardware UART framing or firmware timing. The 200-byte limit and 1758 bps are experimental parameters; airtime is a crude approximation, not regulatory evidence. Radius is a synthetic 1000 m threshold, not a prediction. The medium currently broadcasts to all reachable nodes, unlike E220 addressed filtering; hardware adapter and explicit link destination remain future work. No hardware transmission code included.

Next: isolate RadioInterface, model E220 UART/queue and link destination, add trace scenarios, retries and timeouts, authenticated frame format with standard AEAD, scheduling, hardware-in-loop calibration.
