# Validation and evidence / 検証記録

## Baseline integrity (public package preparation, 2026-11-26)

The original public package was extracted from `afp-lab-v0.7.zip` (SHA-256 `60c2083ca610faa4386e3554915178cb6772680e99f9a06ae454fddfa1bf6eb6`). At the initial packaging step, all 34 original executable Python/HTML files, sample JSON and JSONL files outside generated `results/` were checked byte-for-byte against that archive. The original public-package test log is preserved under `history/`.

### Repository layout revision (2026-11-26)

The package is now organized into `afp_lab/`, `tests/`, `configs/`, `examples/` and `docs/`. Changes to Python code are limited to package imports, resource paths, command help and package markers. The 74 existing test cases and assertions are retained; imports, mock target paths and fixture paths are adapted to the new layout. The protocol, radio, terrain and coverage algorithms, record schemas, HTML templates and bundled data are unchanged. The internal experiment engine version stays 0.6.0.

- Linux, Python 3.13.5: `python -m unittest -v` — 74/74 PASS (2.922 s in the revision check).
- Executed old and new packages against the same eight bundled scenarios. All generated files (experiment JSON, HTML and trace directories) matched byte-for-byte.
- Replayed traces 01 and 06 in each package; all generated replay files also matched byte-for-byte.
- The planner's local HTTP tests cover HTML serving, configuration, coverage computation and profile inspection using fixtures. The CLI entry point and argument help were checked. No new live-GSI or hardware run has been made on this package revision.
- The hosted GitHub Actions matrix (Python 3.10/3.13, Windows/macOS/Linux) is updated for module entry points; it has not yet run on GitHub. The Mermaid diagrams are authored for GitHub's Markdown renderer; hosted rendering has not yet been checked.

See [the layout revision test log](history/TEST-RESULTS-public-layout.txt). Previous evidence below remains applicable to the original v0.7 prototype and must not be confused with newly repeated field verification.

## Scenario baseline (simulation, not field observations)

| Scenario | Delivered/offered | ACK | RF TX | Collisions | Host queue drops |
| --- | ---: | ---: | ---: | ---: | ---: |
| 01 Relay / ACK | 1/1 | 1 | 4 | 0 | 0 |
| 02 Hidden-node collision | 0/2 | 0 | 2 | 2 | 0 |
| 03 Link address filtering | 1/1 | 1 | 2 | 0 | 0 |
| 04 UART queue saturation | 2/3 | 2 | 4 | 0 | 1 |
| 05 Staggered sends | 2/2 | 2 | 8 | 0 | 0 |
| 06 Independent node clocks | 1/1 | 1 | 4 | 0 | 0 |
| 07 Synthetic hills / simultaneous | 0/2 | 0 | 2 | 2 | 0 |
| 08 Synthetic hills / staggered | 2/2 | 2 | 4 | 0 | 0 |

Reproduce from the root:

```sh
python -m unittest -v
python -m afp_lab.lab --out experiments/regression
python -m afp_lab.lab --collect experiments/regression/traces/01 experiments/regression/traces/06 --out experiments/replay
```

## Earlier v0.7 evidence (2026-11-25)

- Development environment: 63 existing + 11 new tests, original eight scenario summaries preserved. Browser fixture tested with synthetic terrain/background and a test HTTP bridge due to environment restrictions. Artificial DEM 5 km/200 m grid: 1,961 centers, 656,132 profile samples, about 1.6 seconds in one illustrative measurement; real GSI fetch/decode not included.
- Project operator's Windows run (Python 3.15 series): all 74 tests passed in 4.420 s. Map Planner returned HTTP 200. A real GSI-backed coverage computation reached 1,961/1,961 cells and returned HTTP 200, approximately 52 s from the recorded run-ID timestamp to the HTTP response, including tile acquisition. This is project-reported operational evidence, not an independently repeated benchmark. The raw private log with local user paths and tile indices is deliberately not redistributed.
- Test logs include expected HTTP 400/403/404 responses from validation/security tests. Python 3.15 produced `ResourceWarning` messages for HTTPError cleanup in tests; the suite passed. No source changes were made to silence those warnings in this package.

Earlier original [test logs and design notes](history/README.md) retain the historical verification status at the time of each prototype. The later Windows run supersedes the old v0.7 statement that live GSI and Windows were unverified. Neither the browser fixture nor Windows operation establishes measured radio performance.

## Not validated

No actual AFP radio adapter or embedded firmware; no bench calibration of E220 timing, receive framing, sensitivity, energy or regulatory compliance; no field measurements, statistical coverage confidence, real time synchronization, long-term equipment endurance or disaster-use readiness. macOS and Raspberry Pi OS are plausible Python targets but not verified here. The E220 source investigation is separate from measured behavior. The planner is local research software, not a hardened public network service.
