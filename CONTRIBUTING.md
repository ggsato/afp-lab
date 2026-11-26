# Contributing / 参加ガイド

Start with what you want to know. You do not need to adopt AFP to contribute. Reports from M5Stack E220 users, LoRaWAN/Meshtastic practitioners, sensor developers, field engineers and others are welcome in English or Japanese.

## Where to discuss

- GitHub Discussions (once enabled): questions, experiment plans, design trade-offs and field observations. Use Issues for specific reproducible defects and bounded improvements. Pull requests should state the question, changed assumption, evidence, and limits.
- For E220 investigations, identify whether an observation is in the host library, module behavior, radio environment, or our model. Include firmware/library versions and actual data; label hypotheses as hypotheses. Avoid publishing private coordinates, personal identifiers or credentials.
- For simulations, include the scenario, Python/OS version, command, observation window, expected and observed behavior. For field tests, include approved hardware/antenna/configuration, timing, denominators, weather/environment and measurement uncertainty. Do not invent RF events from absent logs.

## Development

Run `python -m unittest -v` and `python -m afp_lab.lab --out experiments/regression` before submitting changes. Preserve host/radio/field boundaries; use fixtures for online providers, avoid dependence on live GSI in automated tests, and add deterministic regression tests for a changed model. Do not hand-edit generated output to make a test pass. If changing a schema or wire format, explain compatibility and add test vectors. No unnecessary framework or dependency additions. Keep operational guidance within certification and safety constraints.

Contributions to original code/documentation are intended to be under the repository's MIT license. Only submit material you have permission to share; identify third-party licenses and sources. Be respectful, evidence-driven and open to corrections. 日本語での質問・実験報告も歓迎します。
