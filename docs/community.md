# Community discussion starters (drafts, not posted)

Use after the public repository URL is known. Replace `<repository URL>` before posting; no endorsement or affiliation is implied.

## M5Stack Community — English

**Researching local sensor networks with the M5Stack E220: an open experimental lab**

Hello! We are exploring local environmental observation in Akeno, Yamanashi, Japan. The goal is to make sensor data collection and analysis accessible, not to promote a new protocol. We have built AFP Lab, a small Python-standard-library experimental platform that separates protocol logic, an approximate virtual UART radio, distributed records, and terrain-aware coverage planning. No physical AFP firmware has been released yet.

The Japanese E220 library raised interesting questions about UART frame boundaries, host admission versus actual RF transmission, RSSI and wake-up/ready signals. These are source-review questions, not confirmed hardware faults. We would like to learn how other users operate E220 units over time: what workloads, power arrangements, receive handling and measurements have worked? Have you used local sensor aggregation or fixed relays?

Source, reproducible simulations, the v0.1–v0.7 design narrative and the E220 research notes: <repository URL>. Feedback, corrections, and reproducible reports are welcome; you do not need to use AFP. Thank you!

## M5Stack日本語コミュニティ

**E220を用いた地域センサーネットワーク研究 — 通信実験・地形による到達性予測**

山梨県北杜市明野で、地域のセンサーデータ収集・分析を手軽にする研究をしています。Python標準ライブラリで動くAFP Labを作り、通信ロジック、仮想UART無線、分散記録、地形を考慮した到達マップを分離しました。現時点では仮想実験・地形予測の段階で、実機用AFPファームウェアは未実装です。

日本向けE220ライブラリを調べ、UART受信フレームの境界、送信完了の意味、RSSI、AUXやWORなどの疑問が出てきました。実機不具合を確認したものではなく、実験で知りたい論点です。長期センサー計測や中継、電源管理などでE220を実際に使っている方は、どんな使い方・工夫・課題がありますか？

ソースコード、再現可能な実験、v0.1〜v0.7の設計経緯、E220の調査記録：<repository URL>。AFPを使うことを前提にせず、既存方式を含めて議論したいです。情報共有・指摘を歓迎します。
