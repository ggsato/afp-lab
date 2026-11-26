# v0.7 設計変更 — Radio Coverage Map

## 目的と非目標

単一の基地局を選ぶだけで、端末配置前に地域の予測受信強度を俯瞰できるようにする。通信プロトコル、仮想デバイス、分散記録、地形伝搬式、地域設定の契約は維持。複数基地局最適化、伝搬モデルの変更、実測補正、実験ログの変更は対象外。

## 責務とデータ

- `terrain.propagation_settings` と `terrain.link_profile` を既存 `prepare` から抽出。両研究で同じ設定範囲・断面サンプリング・`path_model` を使う。既存コードの計算結果は変えない。
- `coverage.plan` はField Config（0..20台の編集途中形式も可）と基準端末ID、半径、格子間隔、受信アンテナ高、表示目安を検証。通信計画は不要。基地局から局所平面上の規則格子を作成し、円内の中心点だけ計算。中心点は距離ゼロのため不明。最大10,000点・400万サンプルと原点±15kmの制限をDEM取得前に確認する。
- `coverage.compute` は標高提供元・既存の伝搬モデルのみ利用。実験エンジンやAFPノードのインスタンスを作らない。結果は `afp-coverage-v1`、北→南・西→東の2次元 `cells`、計算設定と基準座標、指標、使用DEMタイルの来歴。円外はnull、欠損は明示したunknown、成功時はRSSI、margin、LOS、回折損失など。
- `planner.py` は既存のHost/Origin/token検証・排他制御を共有し、`POST /api/coverage` と `POST /api/coverage/profile` を追加。結果は一意なIDでローカル保存。profile APIは保存したセルと設定でキャッシュ限定の断面を再計算し、同じ予測値およびDEM来歴であることを検証する。通信実験の結果ディレクトリとは分離。
- `planner.html` はCanvasレイヤーを地図タイルと端末・リンクSVGの間に置く。地図座標と局所平面座標を変換して、同じ格子中心がクリック判定の基準となる。閾値・濃度の変更は描画のみ。基準端末以外の追加や移動は計算を無効化しない。基準端末・原点・伝搬パラメータ・格子条件が変わればレイヤーを無効化する。Field JSONの `planner.coverage` は任意の追加メタデータ（旧JSONも読める）。

## 実験基盤への影響

AFP、Node Session、Radio Interface、Virtual Radio Field、Recorder、Collector、Observatoryは変更なし。従来の通信実験のバージョン表示はそのまま。変更済み既存実行コードは `terrain.py`、`planner.py`、`planner.html` のみ。追加コードは `coverage.py` と `test_coverage.py`。

## 検証

既存63テスト + 追加11テスト = 74件成功。既存8シナリオの全summaryはv0.6配布物と一致。人工DEMで半径5km・200m間隔の1,961点の計算を約1.6秒で実施（実データ取得時間を含まない）。Python HTTP API実通信、ブラウザUIはテスト用背景とHTTPブリッジで操作確認。実GSI/Windows未確認。保存したCoverage JSONの再表示は未実装で、再計算する。実機校正は今後の研究とする。
