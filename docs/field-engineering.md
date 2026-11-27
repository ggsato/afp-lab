# Field Engineering / フィールド設備技術

**Research plan, not validated deployment instructions.** This is the third pillar alongside Protocol Research and Radio Field Research. It addresses a different question: how can local people install and maintain an observation network affordably and safely?

## Equipment design records / 設備設計資料

- [FE-PWR-001 — Modular Solar Power Supply / モジュール組立式独立太陽光電源](field-engineering/power-module.md): Rev. 0.1, procurement complete, prototype not yet validated. Covers the shared 1S solar power module, component selection, assembly design and planned tests for FE-05/FE-06.

## Candidate roles

| Role | Purpose | Questions |
| --- | --- | --- |
| Sensor node | Observe the environment; local wired, BLE or Wi-Fi link where sufficient | Measurement accuracy, power, exposure, replacement |
| Field collector | Aggregate nearby observations; local storage and long-range link | Data reduction, outages, buffer, antenna, battery |
| Relay node | Extend coverage from suitable locations | Continuous receive power, solar/battery sizing, winter operation |
| Base station | Collect, store and analyze data | Availability, backups, network access, physical maintenance |

The role is independent of the transport choice. ESP32, nRF52, RP2040 or another MCU may be appropriate depending on the interfaces, certification, power and reliability requirements. Not every sensor needs LoRa. Local aggregation may reduce overhead; it also creates a failure domain, so data retention and recovery matter.

## Proposed experiments

| ID | Change one factor | Observe |
| --- | --- | --- |
| FE-01 | Stock antenna in/out of suitable resin enclosure | RSSI, delivered packets, case proximity |
| FE-02 | Antenna orientation (same approved antenna) | RSSI and delivery under different polarization geometry |
| FE-03 | Safe, controlled antenna height and position | Predicted versus measured link quality |
| FE-04 | Natural dry/wet conditions | Variability, moisture ingress and weather effects |
| FE-05 | Day/night temperature inside enclosure | Condensation, temperature limits, sensor bias |
| FE-06 | Supported receive/sleep modes and workload | Whole-device Wh/day, peak current, startup behavior |
| FE-07 | BLE/Wi-Fi/wired local aggregation | Completeness, latency, energy and maintenance effort |

Record a baseline first; keep all other conditions fixed as far as practical and repeat measurements. RSSI is only available for received packets; also record the number sent and lost to avoid selection bias. Document failures and uncertainty. Solar autonomy requires measured device energy, site-specific seasonal generation and safe battery charging within manufacturer temperature limits. A module's rating does not establish the assembled device's rating.

## Installation and safety

Use equipment with appropriate weather resistance; account for UV, wind, snow, water ingress, condensation, heat, lightning and mounting. Protect electronics while exposing sensors appropriately (e.g. radiation shield and airflow for ambient temperature). Consult qualified local contractors for permanent outdoor mounting, electrical work, lightning protection and other work requiring qualifications. Do not assume an arbitrary antenna or cable is covered by Japanese technical conformity certification; use the approved combination and verify with the manufacturer or relevant authority. No antenna modification or firmware change is approved by this project.

## Field records

For each device, track: anonymous site/device ID, MCU and radio model/revision, firmware, certification/configuration, antenna model/gain/orientation/height, feedline, enclosure, power source and protection, sensor installation/calibration, measurement time, maintenance, and observed data. Keep exact coordinates and private owner information outside the public repository. Publish generalized diagrams, safe repeatable methods, cost estimates and anonymized results with consent.

平時のセンサーデータ収集を中心に、災害時に地域内掲示板を補完的に利用する構想がある。ただし災害対応は未実装で、認証・優先配送・情報の失効・迂回・非常電源・運用手順などの検証が必要。既存の緊急通報や防災設備を置き換えない。地域の電気・通信・施工業者が担える作業を、安全と資格要件を考慮して標準化し、設置・保守の知識を地域に蓄積することも研究の目的とする。
