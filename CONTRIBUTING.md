# Contributing

Use the pinned Python 3.12 environment and the single [reproduction entry point](README.md#reproduce-without-a-model).
Run `python -m unittest discover -s tests -v` and `python reproduce.py verify` before proposing changes.

The files indexed by `provenance/layout-map.json` are immutable experimental records.
Changes to scientific methods, data or measurements require a separate, explicitly documented study; a presentation cleanup must preserve their bytes.

Sign off contributions with your real author identity and report security concerns through [SECURITY.md](SECURITY.md).
