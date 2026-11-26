# v0.6 設計変更 — Field Config

目的：地域固有のデータをソフトウェアから分離する。プロトコル研究や地形モデルの高度化はこの変更に含めない。

## データ契約

従来の `name`, `geography`, `radio`, `nodes`, `messages`, `duration_s` を保持する。`name` は実験名、`planner.field_name` はフィールド名。新しいフィールドメタデータは以下。

```json
{
  "planner": {
    "field_name": "My field",
    "view": {"lat": 35.785, "lon": 138.445, "zoom": 13, "layer": "std"},
    "map_provider": "gsi",
    "home_id": null,
    "base_id": null,
    "mode": "auto",
    "spacing_s": 3,
    "compare": true
  },
  "geography": {
    "origin_lat": 35.785,
    "origin_lon": 138.445,
    "dem_provider": "gsi_dem"
  }
}
```

上記は新旧メタデータの説明用抜粋であり、完全な実験ファイルではない。座標はサンプル地域。地図の初期表示は伝搬計算から独立する。原点は地理座標を局所平面へ変換する基準であり、基地局の位置ではない。原点の変更は端末の緯度経度を変更しない。各軸±15kmの範囲を保つ。Field Configの編集中は0..20台、範囲外配置も保持可能。実行時は旧版の厳密なチェックを行う。

## 責務分割

- `field_config` はサンプル選択とField Config検証を担当。`--config` で任意のローカルファイルから起動する。
- `providers` の地図記述子はサーバー側の信頼済み定義。Field ConfigにはIDのみを保存し、任意のURLを設定から実行しない。
- `dem_gsi` は旧 `terrain.py` のGSI取得部分をそのまま分離。標高タイルのファイルパスとSHA-256を維持。`terrain.py` は互換性のため旧インポート名を再公開する。
- `terrain.prepare` は `ElevationProvider.sample` を使う。新DEMを追加するときはファクトリー、出典/キャッシュ、凍結地形検証、UI表示を追加する必要がある。今回はGSI以外を実装しない。背景地図提供元の設定は地形計算に使わない。
- AFPノード、RadioInterface、仮想電波場、分散ログ、Collector、実験制御アルゴリズムは変更しない。旧版のシナリオとログを引き続き読み込める。

## 非目標

新しい伝搬モデル、面的カバレッジ、無線制御アルゴリズム、オンラインアカウント管理、海外データ対応。個人の位置は推定しない。地図表示/DEM取得以外の外部サービスを追加しない。

## 検証

旧53件と新10件の自動テスト、旧8シナリオの回帰、別地域座標＋テスト用DEMでの実験。ChromiumのオフラインfixtureでUI操作とJSON互換性を確認。実データ通信/Windowsはユーザー環境で確認する。
