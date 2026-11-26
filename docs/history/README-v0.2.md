# AFP Lab v0.2.0 — AKENO Network Observatory

明野データ実験フィールド / 2026-11-25

仮想無線の実験環境。実機の電波送信は行いません。v0.1 の `afp.py`, `demo.py`, `test_afp.py` をそのまま保持し、新しいモデルを別モジュールに実装しています。AFPバイナリ形式は同一（version=1, 13-byte header）です。

## Windows で開始する

ZIPを展開し、`afp-lab` フォルダに移動します。Python 3.10以上（標準ライブラリのみ）。追加インストール不要。

```cmd
cd /d "%USERPROFILE%\Downloads\afp-lab-v0.2\afp-lab"
python -m unittest -v
python lab.py --open
```

ブラウザが自動で開かない場合は `start "" results\index.html` を実行してください。macOS/Linuxでは `python3 lab.py --open` を使用できます。

`results/index.html` は実験結果を埋め込んだ自己完結型HTMLです。ローカルのブラウザで開き、シナリオを選択、再生・一時停止、前後の時刻に移動できます。RFタイムラインのバーをクリックすると送信開始時刻へ移動します。ログは選択時刻までの最新100件、全イベントは `results/experiments.json` に記録されます。再生はイベント単位で、実時間に比例するものではありません。UIで実験条件を直接編集する機能は未実装です。

ZIPには初回実験結果も収録しています。再実行する場合は `python lab.py`。既存の `results/index.html` と `results/experiments.json` は上書きされます。保存したい実験は `--out` で別ディレクトリを指定してください。

## 実験を変更する

`scenarios/01_relay.json` などをテキストエディタで開いて別名で保存。ノード座標はメートル（局所XY）であり、緯度経度・標高ではありません。以下は最小例。

```json
{
  "name": "My experiment",
  "radio": {"radius_m": 1000, "queue_capacity": 4},
  "nodes": [
    {"id": 1, "x": 0, "y": 0},
    {"id": 2, "x": 800, "y": 0, "relay": true},
    {"id": 3, "x": 1600, "y": 0}
  ],
  "messages": [{"at": 0, "src": 1, "dst": 3, "payload": "temperature=19.8"}]
}
```

`at` は送信要求時刻（仮想秒）。`channel` はノードの受信チャネル（既定0）。`link_dst` は任意の直接の無線宛先（既定65535=ブロードキャスト）で、AFP `dst`（最終宛先）とは独立。中継/ACKは今回の単純なflooding設計のためブロードキャストを使用。受信ノードは同じチャネル、距離内である必要があります。`radio` の全設定項目はUIに表示され、既定値は `lab.py` の `validate()` を参照してください。

```cmd
python lab.py scenarios/02_collision.json scenarios/05_staggered.json --out experiments/compare01 --open
```

パラメータ比較の推奨: 02 と 05 は同じ配置・ペイロード、送信要求時刻だけ変更しています。04 は送信要求がキュー容量を超過する実験です。

## コンポーネント

| ファイル | 責務 |
|---|---|
| `afp.py` | v0.1 codec、仮想時計、旧モデル (変更なし) |
| `demo.py` / `test_afp.py` | v0.1実験と回帰テスト (変更なし) |
| `radio.py` | RadioInterface, VirtualE220, Field（距離・チャネル・衝突） |
| `lab.py` | AFPNode、Scenario Engine、実験結果、CLI、レポート生成 |
| `observatory.html` | データ埋め込み用UIテンプレート（直接開かず、生成結果を開く） |
| `scenarios/*.json` | 5つの再現可能な実験条件 |
| `test_v02.py` | 新モデルの回帰テスト |
| `results/` | 初回のHTMLレポートと全イベントJSON |

### RadioInterface

- `send(payload, destination, channel) -> bool`: ローカル送信受付。Trueは無線送信完了/配送成功を保証しない。
- `set_receiver(callback)`: 受信ペイロードを通知。仮想モデルではRSSIはNone。
- `capabilities()`: 機器の機能。シミュレーターで見えるRF完了時刻は、E220 Unitのホスト側で取得可能な情報とは区別。

観測の段階: `origin` → `admitted` → `uart_tx_end` → `tx` → `rf_tx_end` → `rf_rx` → `rx` → `deliver` / `relay` / `ack`。`txid` はシミュレーター内の無線送信識別子、`src,dst,seq` はAFPレベルの識別子。宛先フィルタはRF受信後に評価されるため、宛先が異なる信号でも衝突を起こします。`queue_drop`, `collision`, `half_duplex`, `filtered`, `ttl_drop`, `no_receiver` は分けて記録します。

実験JSONにはモデルバージョン、正規化されたシナリオ、SHA-256、リンク候補、集計と全イベントを保存します。時刻は小数点以下6桁で出力。PDRはユニークなDATA配送数/送信要求数、ACK率はユニークなACK到達数/送信要求数。衝突数は受信候補ごとの損失数。総送信時間は全送信のRF時間の合計（同時送信の時間を重複計上）。

## 仮定と未実装

- Virtual E220はUART 8N1（送信側3B宛先/チャネル、受信側1B RSSIの時間分のみ）、仮のキュー容量、固定宛先フィルタ、半二重をモデル化した代替物。実E220のUARTフレーミング・分割・AUX・内部バッファ・無線ヘッダ・処理時間は未確認。生UARTレジスタのエミュレーションではありません。
- RF時間は v0.1 と同じ `air_overhead_s + 8 * AFPフレーム長 / air_rate_bps` の近似。真のLoRa airtime、LBT、電波法適合性の評価には使えません。チャネルは論理番号で、実際の周波数/帯域幅/拡散率や隣接チャネル干渉は未モデル化。距離閾値、同一チャネルの重複を全損失とする単純モデル。RSSI/SNR、地形、確率損失、capture effectは未実装。
- 無線プロトコルは実験用。認証、暗号化、再送、経路探索、TDMA、重複キャッシュの期限、永続化、実機ドライバーは未実装。安全な運用に使用しないこと。
- Windowsのv0.1実行はユーザー確認済み。v0.2はLinux/Python 3.13で自動テスト、Chromiumに生成HTMLを読み込ませて画面操作確認済み。Windows実機では未検証。標準ライブラリと自己完結HTMLのみなので移植性を維持。

## 次の研究

1. Virtual Device の仮定を E220 実機で測定・補正。2. 地形とは独立したプロトコルの帯域制御実験（タイミングの比較、再送、優先度）。3. Field の距離閾値を伝搬モデルに置換し、地形・標高・アンテナ高へ拡張。4. 実測ログと同じスキーマに寄せてシミュレーションとの差を分析。
