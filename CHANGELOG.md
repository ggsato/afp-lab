# Changelog

## v0.7 — public repository layout and documentation revision (2026-11-26)

- Make the parent project website prominent in both READMEs.
- Add seven Mermaid architecture diagrams in each language to the design evolution narrative, highlighting the responsibilities added or changed at every stage.
- Organize Python code as `afp_lab/`, HTML templates as `afp_lab/web/`, tests as `tests/`, input data as `configs/`, and the original trace example as `examples/`. Use `python -m afp_lab.lab` / `python -m afp_lab.planner` / `python -m afp_lab.terrain` from the repository root.
- Adapt imports, resource paths, tests, CI and usage documentation; no protocol, simulation, terrain or coverage algorithm changes. All 74 tests pass; all eight scenario outputs and the replay of traces 01/06 are byte-identical to the initial public package. No new feature version is introduced.

## v0.7 — initial public baseline preparation (2026-11-26)

Documentation-only packaging of the v0.7 working code from 2026-11-25. Bilingual README, consolidated design narrative, architecture, E220 research notes, Field Engineering plan, validation, MIT license, participation and publishing guidance. Generated reports are omitted and can be regenerated; original version notes are archived. Added a CI workflow for future cross-platform checks; it has not run on GitHub yet. No runtime or test source changes.

## Prototype milestones (2026-11-25)

- **v0.7:** single-source terrain coverage map, cached cell profiles, saved results, 74 tests.
- **v0.6:** configurable fields, provider boundaries, 63 tests.
- **v0.5:** map placement planner, 53 tests.
- **v0.4:** GSI DEM, terrain-aware path prediction, 43 tests.
- **v0.3:** independent node clocks, distributed recording and offline collector, 30 tests.
- **v0.2:** virtual UART radio, scenarios and Observatory, 15 tests.
- **v0.1:** minimal binary protocol and deterministic simulation, 3 tests.

See [design evolution](docs/design-evolution.md) and [historical notes](docs/history/README.md). These are prototype milestones, not claimed public Git tags or reconstructed commits.
