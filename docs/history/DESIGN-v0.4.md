# Design v0.4

## Responsibility boundary

- `terrain.py`: DEM取得、キャッシュ、デコード、地形スナップショット生成、電波リンク予測。実験実行時はネットワーク不要。
- `lab.py`: 既存scenario engine。地形スナップショットはvirtual_environment/manifestだけに渡す。位置・アンテナ高が準備済み値と異なる場合は再準備を要求。
- `radio.py`: radiusモデルまたはterrainモデルを選ぶ。予測受信可否をRF候補に使用し、受信時だけRSSIをホストに通知。従来の半二重・衝突モデルは変更しない。
- `node.py`, `contracts.py`, `runtime.py`, `recorder.py`: v0.3の責務・コードを維持。AFPホストには地形・リンク表・直前の無線送信元・RF真因を渡さない。
- `observatory.html`: 地形と予測リンクは独立パネルで表示。既存観測視点の切替と再生を維持。

## Reproducibility

元の地理設定→PNGキャッシュ→prepared JSON→分散trace→HTML。各実験はscenario hashで識別。サンプリング済みの地形とリンクモデルを固定し、Collectorは取得元や無線空間に依存しない。地形は予測条件であり、観測ログではない。

## Decisions / limitations

地形を最初に高度化し、AFPアルゴリズム自体は変更しない。初期モデルは単一ナイフエッジ、固定損失、固定感度閾値。人工地形の比較を同梱し、GSIデータと明確に分離。開発環境ではGSIへのネットワークアクセスができず本番取得は未検証。取得先の利用可能性、実機の感度・RSSI、フィールドの伝搬特性は今後確認する。連続的な面的到達マップと最適配置の自動探索は今後の拡張とする。
