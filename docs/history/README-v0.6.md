# AFP Lab v0.6 — Generalized Field Config

AFP / AKENO Field Protocol。明野はサンプルの実験フィールドで、プログラムに固定された地域ではありません。v0.5の通信・地形モデル、分散Recorder、Observatoryを維持した小規模な改修です。Python 3.10以上、標準ライブラリのみ。

## Windowsで起動

ZIPを別フォルダに展開してコマンドプロンプトで実行します。

```cmd
cd /d "%USERPROFILE%\Downloads\afp-lab-v0.6\afp-lab"
python -m unittest -v
python planner.py --cache "%USERPROFILE%\Downloads\afp-lab-v0.4\afp-lab\dem-cache" --open
```

キャッシュの保存場所が異なる場合は適宜変更してください。キャッシュを指定しなくても `python planner.py --open` で起動できます。ブラウザが開かない場合は http://127.0.0.1:8765/ を開きます。終了はCtrl+C。ローカルHTTPサーバーを起動している間だけ操作できます。

## 既存の配置を開く

v0.5で保存した配置JSONを、Field Config内の「Field JSONを開く」で読み込みます。v0.4の `geography/akeno.json` なども読込可能です。旧ファイルにないフィールド名・初期表示設定は実験名と地形原点、配置から補います。保存すると新しいメタデータが加わります。旧ファイルは変更しません。

次回から直接そのフィールドで起動するには、保存したField JSONを指定します（パスは保存先に合わせて変更してください）。

```cmd
python planner.py --config "%USERPROFILE%\Downloads\field-my-field.json" --cache "%USERPROFILE%\Downloads\afp-lab-v0.4\afp-lab\dem-cache" --open
```

`--config` を省略したときだけ `geography/catalog.json` が示す同梱サンプル（明野）を開きます。「起動時の設定」は現在のサーバー起動時に指定したファイルに戻ります。

## 新しいフィールドを作る

1. 地図をドラッグするか、「初期表示・地図移動」の緯度・経度を入力して「指定地点へ移動」を押します。
2. 「新規フィールド」を押すと、現在の地図中心を原点とする端末0台の構成を作成します。以前の編集内容は置き換わるので必要に応じて保存してください。無線・伝搬モデルの設定は引き継ぎます。
3. フィールド名を設定します。実験名は別欄で変更できます。
4. 「＋ 端末」や「＋ 自宅を配置」で端末を追加します。観測拠点、アンテナ高さ、送信計画を設定します。
5. 原点は「地図で指定」「地図中心を原点に」、または緯度・経度入力後の「原点を反映」で変更できます。端末座標は変更しません。表示の十字が原点、破線が局所平面モデルの計算範囲です。端末が範囲外なら警告し、実験を拒否します。
6. 希望の地図位置・ズーム・背景地図を選び、「現在の表示を初期値に」を押します。「初期表示へ」はこの設定に戻ります。地図の移動や初期表示の設定自体は電波伝搬計算に影響しません。
7. 「Field JSONを保存」でファイルに出力します。端末0台または1台の途中状態も保存・読込できます。ただし地形実験は2〜20台、適切な送信計画が必要です。
8. 「地形を取得して実験」を押すと従来通り地形モデルを生成し、AFPを実行します。実験は別ディレクトリに保存します。

フィールドの切り替えはファイル読込で行います。ブラウザの永続ストレージや外部アカウントには保存しません。未保存の編集内容は開く操作で置き換わります。

## CLIでの実験・再集約

```cmd
python lab.py --open
python terrain.py geography/akeno.json --compare
python lab.py prepared/terrain.json prepared/terrain-staggered.json --out experiments/akeno --open
python lab.py --collect results/traces/01 results/traces/06 --out experiments/replay --open
```

`terrain.py` には任意の完成済みField JSONを渡せます。`--cache` と `--offline` も従来通り利用可能です。旧版のtrace形式は変更していません。

## 構造

- `geography/catalog.json` / `geography/akeno.json`: 起動時サンプルと地域固有の設定。
- `field_config.py`: Field Config読込と検証。編集途中と実行可能状態を区別。
- `providers.py`: 背景地図の提供元・タイル仕様・出典情報、および標高取得のインターフェースとファクトリー。
- `dem_gsi.py`: 国土地理院の標高PNGデコード・ダウンロード・キャッシュ。旧キャッシュ形式を維持。
- `terrain.py`: 地理座標変換、地形断面、伝搬計算、凍結シナリオ生成。`ElevationProvider.sample(lat, lon)` を利用。
- `planner.py` / `planner.html`: ローカルAPIと汎用地図エディター。
- `lab.py` / `node.py` / `radio.py` / `recorder.py`: 既存の実験・通信・観測処理。AFPは地形や他端末の内部情報に依存しない。

## 検証と制約

63件の自動テスト（従来53 + 追加10）成功。既存8シナリオの主要性能指標はv0.5と一致。別地域座標でのテストは人工の平坦DEMを使用。Chromiumで新旧操作、原点変更、空フィールド保存、初期表示と地域切替をテスト用地図/APIで検証。ローカルHTTP APIはPythonの実通信で確認しました。実地図への接続、Windowsでのv0.6操作は未確認です。

現時点で実装済みの提供元は国土地理院のみ。海外DEMや他社タイルはアダプター追加が必要です。地図の提供範囲内でもDEMが欠損する地点は実験できません。原点から各軸±15km（約30km四方）の局所モデル制限は維持しています。周波数920〜928MHz、出力等は日本向けの従来のモデル制約です。森林、建物、実機感度、無線遅延などは未校正です。面的カバレッジは未実装です。

Field JSONや結果には自宅等の正確な座標が含まれるため共有・公開時は注意してください。背景タイル・標高タイルは国土地理院への通信で取得します。`--offline` はDEM取得だけをキャッシュ限定にする機能です。地図表示にはブラウザの通信またはキャッシュが必要です。

詳細は `DESIGN-v0.6.md`、以前の操作は `README-v0.5.md` を参照してください。
