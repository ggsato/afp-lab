# Data, attribution and privacy / データと公開範囲

## Data sources and rights

The repository's original code and original documentation are offered under MIT. It does not distribute M5Stack/Ebyte/Meshtastic firmware, third-party maps or real elevation tiles. External names identify relevant technologies and sources; no affiliation is implied. The original scripts use Python standard-library modules and browser APIs.

GSI (Geospatial Information Authority of Japan / 国土地理院) is the current map/DEM provider. The planner requests std, pale, relief and seamlessphoto backgrounds; `dem_gsi.py` reads DEM5A/5B/5C PNG at z15 and DEM10B (`dem_png`) at z14. The DEM reader follows the signed RGB elevation format with NoData handling. The link approximation is informed by ITU-R P.526 (dominant knife edge); it is not a complete implementation of the recommendation.

- GSI tile list and layer-specific conditions: https://maps.gsi.go.jp/development/ichiran.html
- GSI elevation tile encoding: https://cyberjapandata.gsi.go.jp/development/demtile.html
- GSI content terms: https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html
- ITU-R P.526: https://www.itu.int/rec/R-REC-P.526/en

When publishing GSI-derived maps or results, identify the source and that the data was processed (e.g. 「国土地理院 標高タイルを加工して作成」), check layer-specific attribution, third-party terms, and applicable Survey Act procedures. MIT does not cover downloaded data or relieve these obligations. The bundled screenshot uses generated synthetic tiles/terrain, not GSI data. Sample Akeno coordinates are illustrative candidate points, not site agreements or actual installation positions. The frozen scenarios 07/08 are synthetic tests.

## Local data and external connections

The included service is loopback-only. Field JSON, coverage JSON, prepared scenarios, traces and DEM tile identifiers can reveal precise locations, names, messages, timestamps or coverage of private property. They are local output, not intended as automatic publication material. Map tiles are requested by the browser, and DEM tiles by Python; tile indices reveal requested areas to the provider. There is no intended upload of Field JSON to a project server. Do not equate local operation with zero external traffic. Use an offline DEM cache where appropriate (browser backgrounds are separate).

Keep private input files in `private/` or outside the repository. `.gitignore` helps exclude generated directories, credentials and common field downloads but cannot identify every sensitive filename or redact content. Before commits, check `git status`, staged files, screenshots/metadata and experiment records. Remove exact private coordinates, names, device identifiers and tokens; publish only consented, suitably generalized evidence. If sensitive data enters Git history, deleting the file in a later commit is not sufficient.

公開版では個人の実地形計算ログ、私有地の実配置JSON、取得済みDEMキャッシュを含めない。実行時に生成される結果はローカルで管理する。公開用サンプルと人工地形は配布ZIPに含める。
