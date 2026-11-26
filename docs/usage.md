# Usage / 操作ガイド

Python 3.10+; use `python3` if that is your executable. Run all commands in the repository root. No MCU, package installation or internet access is needed for the bundled simulations or test suite. The planner UI is primarily Japanese.

## 1. Protocol Research (offline)

```sh
python -m unittest -v
python -m afp_lab.lab --out experiments/demo --open
python -m afp_lab.lab configs/scenarios/02_collision.json configs/scenarios/05_staggered.json --out experiments/timing --open
python -m afp_lab.lab --collect experiments/demo/traces/01 experiments/demo/traces/06 --out experiments/replay --open
```

Open `index.html` in the output directory if needed. Each run saves `experiments.json`, the self-contained HTML and, for simulation, `traces/NN/manifest.json`, node plans and JSONL streams. Use a fresh `--out` directory to preserve earlier runs; reuse overwrites known report files. The report's internal engine version remains 0.6.0 because v0.7 adds planning coverage, not a changed packet engine.

## 2. Radio Field Research (map)

```sh
python -m afp_lab.planner --open
```

Stop with Ctrl+C. If port 8765 is occupied, stop the previous server or add `--port 8766`. Open the indicated loopback URL if the browser does not start. To reuse a saved layout/cache:

```sh
python -m afp_lab.planner --config private/my-field.json --cache dem-cache --open
```

Create the private directory and place your own field file there first. Without `--config`, `configs/geography/catalog.json` selects the example. To start another field, select 新規フィールド, edit the origin and choose nodes. 地図の表示中心 is not the calculation origin. Add nodes with ＋端末, edit antenna height and apply with 入力を反映. Choose a base and message timing for pairwise experiments, then 地形を取得して実験. Field JSON is the editable configuration, not a measured dataset.

Coverage Map: select a source, 3 km radius, 200 m spacing and 1.5 m receiving antenna height to start. Press 到達マップを計算. Click a cell for the modeled path profile and RSSI. Change 安定目安 or opacity without recomputing. Green >= stable margin, light green >= half stable margin, yellow >= 0 dB, red below threshold; gray means unknown or source location. The default stable margin is 10 dB. These are thresholds, not confidence intervals. Changing source or physical calculation conditions invalidates the overlay. Adding other nodes does not. Save Field JSON separately from the coverage result. The result is automatically stored under `experiments/planner/coverage/<run-id>/coverage.json`. Saved result overlays cannot yet be opened directly; recompute with the saved configuration.

The default 5 km/200 m grid contains 1,961 centers (1,960 nonzero-distance links). If the computation limit is reached, reduce radius, increase grid spacing or increase profile step. If the cache is missing/corrupt, use online mode or correct the cache. Do not expose the local HTTP service publicly; it is designed for one local user, not a multi-user web service.

## 3. CLI terrain preparation (online once)

```sh
python -m afp_lab.terrain configs/geography/akeno.json --cache dem-cache --compare --out prepared
python -m afp_lab.lab prepared/terrain.json prepared/terrain-staggered.json --out experiments/akeno-example --open
python -m afp_lab.terrain configs/geography/akeno.json --cache dem-cache --offline --compare --out prepared-offline
```

A frozen prepared scenario needs no network during `python -m afp_lab.lab`. `--offline` requires all necessary cached DEM tiles (including known unavailable tiles); the planner's browser background may still fetch map tiles. Use the same cache for inspecting a coverage profile. The project does not distribute GSI tiles. See [data notes](data-and-privacy.md).

日本語の詳細な画面操作は [v0.7の原ガイド](history/README-v0.7.md) と [v0.6のField Configガイド](history/README-v0.6.md) にあります。旧版のパスや当時の検証状況は歴史資料として残しています。現在の起動方法と確認状況は本ガイド・[Validation](validation.md)を優先してください。
