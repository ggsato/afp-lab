# M5Stack E220 (JP): host interface research notes / 技術調査

**Status:** source review, not a bench-test result. AFP Lab does not bundle or flash the M5Stack library or Ebyte firmware. These observations concern the reviewed host library only; they do not establish a defect in the E220's internal firmware. We welcome corrections and reproducible measurements.

## Scope and references

- [M5Stack Unit LoRaE220-920 documentation](https://docs.m5stack.com/ja/unit/Unit_LoRaE220-920)
- [M5-LoRa-E220-JP](https://github.com/m5stack/M5-LoRa-E220-JP), reviewed `main` on 2026-11-26. Source identity by Git blob SHA (not a commit ID):
  - [`src/M5_LoRa_E220_JP.cpp`](https://github.com/m5stack/M5-LoRa-E220-JP/blob/main/src/M5_LoRa_E220_JP.cpp): `f4415b358e2679ce6aa3b331236a4979e04275b9`
  - [`src/M5_LoRa_E220_JP_DEF.h`](https://github.com/m5stack/M5-LoRa-E220-JP/blob/main/src/M5_LoRa_E220_JP_DEF.h): `95d6b545ee7e1f01503f0f9a3d06689528fa6c22`
- [Community discussion: E220 wake-up / AUX](https://community.m5stack.com/topic/7236/lora-unit-with-antenna-e220-how-to-wake-up)
- [Meshtastic mesh algorithm](https://meshtastic.org/docs/overview/mesh-algo/) and [Meshtasticator](https://github.com/meshtastic/Meshtasticator) for independent comparison.

The JP library's definitions include BW125 SF5–9, BW250 SF5–10 and BW500 SF5–11, and four nominal subpacket sizes (32/64/128/200). The SF9/BW125 comment gives 1,758 bps; the default UART comment gives 9,600 baud. Neither nominal bit rate nor a code comment establishes RF airtime or permissible Japanese settings. Do not assume other E220 variants have the same capabilities.

## Observations / open questions

| ID | Source-level observation | Question or hypothesis to verify |
| --- | --- | --- |
| E220-01 | `SendFrame` builds a three-byte target address/channel prefix, writes UART and flushes; it returns 0 after the semaphore block even if acquisition fails. | Does the caller distinguish admission, UART completion and on-air completion? What happens under contention? |
| E220-02 | `SendFrame` reads and discards pending RX bytes after writing, with delays. | Can a valid incoming frame be discarded when traffic overlaps? Under what timing? |
| E220-03 | `RecieveFrame` waits for data indefinitely and uses an idle gap (10 ms after draining) to infer the end. | Can UART scheduling, back-to-back packets or subpacket timing split or merge application frames? |
| E220-04 | `RecieveFrame` treats the last byte as RSSI and rejects accumulated lengths >200. | Is RSSI always enabled in the intended configuration? Does a 200-byte data payload plus RSSI exceed this library's accepted length? Verify safe buffer bounds before stress testing. |
| E220-05 | The received payload/RSSI structure does not give an immediate RF hop ID. | Distinguish AFP original sender from the last physical transmitter. Can the application obtain a reliable last-hop identity at all? |
| E220-06 | `InitLoRaSetting` tests response length; no matching response-byte comparison is visible in this function. | Confirm configuration by readback, not response size alone. |
| E220-07 | `SetDefaultConfigValue` uses `0b0` for LBT with an enabled comment; header defines `LBT_DISABLE=0b0`. Its power value `0b01` is commented 13 dBm while the header defines that value as 12 dBm. | Which configuration is actually applied? Verify against the module manual and approved settings. Do not treat comments as proof of compliance. |
| E220-08 | Module settings and the documented Unit interface mediate radio operations; AUX is not exposed on the Grove data connection. | Which readiness, wake-up and completion events can the host actually observe? What delays are guaranteed? |

The radio's own timing and buffer internals are not visible from these sources. Neither an Arduino return value nor a virtual field's `rf_tx_end` is proof of real RF completion. `VirtualE220` deliberately models hidden state, but is not a firmware emulator. A module's 16-bit setting named encryption key is not sufficient evidence of modern authentication or confidentiality; AFP itself has no security protocol.

## Bench research (proposed, no RF experiments completed)

Use only a verified lawful radio/antenna configuration in Japan. Check the exact unit and applicable certification, allowed channel/power and transmission conditions; do not disable regulatory controls to run a test. Start with two units, stock antennas and moderate traffic in an authorized environment. Record module/board revisions, library commit, serial settings, actual radio readback, power supply, antenna and test conditions. Use bounded UART logs with sequence numbers and monotonic timestamps. If needed, consult qualified radio specialists before RF instrumentation or conducted tests. Do not transmit without an approved configuration.

1. Baseline isolated messages: compare bytes sent/received, RSSI, elapsed time and ACK.
2. Inspect host API under contention and bounded receive windows; use mocks first to test locks and framing without RF.
3. Test payload lengths near configured boundaries with safe buffer sizing, RSSI enabled/disabled where lawful and supported, and controlled message spacing. Record invalid/merged/truncated frames rather than attributing causes prematurely.
4. Compare documented configuration, readback and observed behavior. Examine readiness and receive behavior using approved modes and settings only.
5. Compare field records with the same packet workload; state exactly which event is measured versus inferred. Test firmware revisions separately.

## Why this matters / 日本語要約

E220はUARTの向こう側に独自のファームウェアを持ちます。ホストライブラリのコードから確認できる挙動と、無線機内部で起きることを分離します。上表のE220-01〜08は再現済みの製品不具合ではなく、実機評価の論点です。送信要求受付・UART転送完了・電波送信完了・配送成功を区別すること、受信境界とRSSIを検証すること、設定値のコメントと実際の値を照合することが主なテーマです。

公式ライブラリをそのまま使うか、必要な部分だけ改善するか、別モジュールを選ぶかは実験後に判断します。Meshtasticの直接無線制御とは抽象化の境界が異なり、通常のE220 UART Unitへ公式Meshtastic firmwareをそのまま書き込むことは想定していません。AFPに高度な制御が必要なら別Radio実装を検討します。目的は無線機の内部を握ることではなく、必要なデータがどの程度確実に得られるかを知ることです。

Questions for M5Stack users: What long-running sensor deployments have you built? How do you delimit UART frames, check completion and manage simultaneous reception, wake-up or power loss? What are your measured throughput, packet delivery and energy results? Please share versions, reproducible steps and observed evidence rather than private deployment locations.
