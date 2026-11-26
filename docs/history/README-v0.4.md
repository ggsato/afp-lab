# AFP Lab v0.4 — Terrain-aware field research

明野データ実験フィールド / AKENO Field Protocol

v0.3 の分散Recorder、端末別時計、NodeSession、Collector、既存6実験を維持し、地形研究を拡張したバージョンです。Python 3.10以上、標準ライブラリのみ。Windows CMD、macOS/Linuxで共通のPythonコマンドを使用できます。

## 1. オフラインで動作確認

ZIPの中の `afp-lab` に移動します。Windows CMD:

```cmd
cd /d "%USERPROFILE%\Downloads\afp-lab-v0.4\afp-lab"
python -m unittest -v
python lab.py --open
```

従来の6実験と、人工地形の2実験（07/08）を実行します。07/08は人工的な丘陵を使ったテストデータであり、国土地理院のデータ・明野の実地形ではありません。Network Observatoryのシナリオ選択で07または08を選ぶと地形パネルが表示されます。`Node 1 — 3` を選ぶと人工的な尾根により直接リンクが遮蔽される例を確認できます。

## 2. 明野の実際の地形を取得する（初回のみネット接続）

```cmd
python terrain.py geography/akeno.json --compare
```

国土地理院のPNG標高タイルを `dem-cache/` に保存します。DEM5A、DEM5B、DEM5C（z15）、DEM10B（z14）の順に画素単位で利用可能なデータを選びます。PNGのRGB値を公式仕様に従い符号付き標高mに変換します。HTTP 404/410 または無効画素の場合だけ次のレイヤーを試します。ネットワークエラー・破損PNG・すべて欠損の場合はエラー終了し、人工データやゼロ標高に置き換えません。初回は複数タイルを取得します。

取得したタイルのURL、レイヤー、SHA-256、サンプリング済み標高、全リンクの断面と計算結果を `prepared/terrain.json` と `prepared/terrain-staggered.json` に保存します。前者はコンフィグにある送信時刻、後者は同じ地形で3秒間隔の送信（メッセージ順）です。

```cmd
python lab.py prepared/terrain.json prepared/terrain-staggered.json --out experiments/akeno --open
```

同じ標高キャッシュで再計算する場合:

```cmd
python terrain.py geography/akeno.json --offline --compare --out prepared-offline
```

`lab.py` は準備済みJSONから実行するのでネットアクセス不要です。`dem-cache` がなくても prepared JSON と traces から実験・集約を再現できます。キャッシュはユーザーが保有する研究用データです。更新を反映する場合は別キャッシュを `--cache dem-cache-new` で指定してください。取得に失敗した場合の古い prepared ファイルは自動消去しません。成功メッセージを確認してから実験してください。

開発環境は外部GSIタイルへのアクセスが制限されていたため、GSI本番データの取得は未検証です。デコーダ、取得処理（モックHTTP）、キャッシュ、欠損フォールバック、地形計算、既存プロトコルとの接続、ブラウザ操作はテスト済みです。Windowsから初回取得を実施してください。

## 3. 端末を置き換えて実験する

`geography/akeno.json` は候補地点を仮に置いた例です。実機の設置場所や私有地の正確な位置は設定していません。各地点の緯度・経度、アンテナの地面からの高さを変更してください。例:

```json
{"id": 2, "label": "Central candidate", "lat": 35.787, "lon": 138.447, "antenna_m": 5, "relay": true}
```

`geography` には周波数、送信出力、アンテナ利得合計、受信判定閾値、固定追加損失、地形断面のサンプリング間隔を指定します。現在の既定例（923MHz、13dBm、閾値-120dBm、固定追加損失15dB）は仮定であり、E220の測定済みパラメータではありません。日本国内の適法な周波数・帯域・送信条件は実機試験前に別途確認してください。`radio.air_rate_bps` と地形モデルの感度は現時点で自動連動しません。`radius_m` は地形シナリオでは使用しません。

アンテナ高や地点を変更した場合、元の `geography/akeno.json` を編集して `terrain.py` を再実行します。prepared JSONの座標を直接変更しないでください。準備済みJSONは実験のスナップショットです。複数の設定を比較するには別々の `--out` ディレクトリを用意し、`lab.py` に2つ以上のJSONを渡します。

地形パネルは地表標高の概略分布（41×41のサンプル）、端末のリンク予測、端末間地形断面、60%第1フレネルゾーン、見通し、予測RSSI、受信マージンを表示します。実機ログの可視化と区別して「予測」と表示します。ブラウザ内の地形パネルで地点や高さを直接編集する機能、面的なカバレッジ計算は未実装です。

## 4. モデルの意味

- 距離: 緯度経度を地域用の局所XY平面に近似。原点から15km以内に制限。
- 標高: GSI PNG標高タイルの最寄り画素。欠損は次のデータソース、それでも欠損なら停止。
- 地形断面: 指定間隔でサンプリング（両端を含む）。地球曲率は有効地球半径4/3で近似。
- FSPL: 20 log10(4 pi d / lambda)。
- フレネル半径: sqrt(lambda d1 d2 / d)。最も小さい正規化クリアランスを算出。
- 回折: 最も厳しい単一障害物についてITU-R P.526のナイフエッジ近似。複数障害物の累積、丸い尾根、反射、植生、建物、気象、外部干渉、確率的受信率は未モデル化。
- 予測RSSI = 送信出力 + 送受信アンテナ利得合計 - FSPL - 回折損失 - 固定追加損失。
- 予測RSSIが仮定した受信判定閾値以上であれば仮想RF受信候補。見通しの有無だけで受信可否を決めない。
- 受信可能リンクで同時送信が重なる場合はv0.3の単純な衝突モデルを継続。捕捉効果、閾値以下の干渉、SF・周波数の詳細は未モデル化。空中時間は従来モデルのまま。

このモデルは研究用の最初の近似であり、実際に通信できることを保証しません。RSSI値は仮想端末の受信イベントに載りますが、送信元の直接識別子や地形、リンク表、衝突の真因は端末に通知されません。端末計画にも地形データは含まれません。

## 5. 分散ログと再集約

```cmd
python lab.py --collect experiments/akeno/traces/01 experiments/akeno/traces/02 --out experiments/akeno-replay --open
```

v0.3のtrace schemaを維持し、manifestに地形スナップショットとモデル名を追加しました。Fieldログを除いてもLocalの配送・ACK集計は維持されます。モデルが予測したリンクと実際の受信ログを混同しないよう、地形パネルは独立した予測表示です。古いv0.3のtraceも `--collect` で再集約できます。

## 6. 研究上の次のステップ

1. 実際のGSI地形で候補地点を評価し、通信可能予測と不可能予測の境界を確認。
2. E220到着後にRSSI・到達率・アンテナ高・GPS・設定を記録し、モデル残差を分析。
3. 同一地形上で送信間隔・再送・経路探索・TDMAなどのAFP制御を比較。

今回は地形モデルと既存の送信時刻比較に集中し、自動再送、動的経路探索、TDMA、暗号化は追加していません。実機ドライバーも未実装です。以前のREADMEと設計文書を同梱しています。

## 出典

- 国土地理院 地理院タイル一覧: https://maps.gsi.go.jp/development/ichiran.html
- 国土地理院 標高タイル詳細仕様: https://cyberjapandata.gsi.go.jp/development/demtile.html
- ITU-R P.526-16 (2025), Propagation by diffraction: https://www.itu.int/rec/R-REC-P.526/en （単一ナイフエッジ損失の近似式）

実データは配布ZIPには含めていません。地形表示には出典と加工の明記があります。外部公開・再配布する場合は国土地理院の利用規約、測量成果の利用手続を確認してください。
