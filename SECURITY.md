# Security policy

This repository contains research instrumentation, not a supported production
service. Run it only in the isolated environment described by the protocol.
The current `main` branch is the maintained research version. Captured source/data snapshots preserve evidence; they are not maintained services.

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/Alien6-Studio/research-rag-evidence/security/advisories/new)
or [contact@alien6.com](mailto:contact@alien6.com). Include the affected commit,
reproduction steps, and impact. Exclude active credentials and customer data.
Do not open a public issue containing an unpatched vulnerability or a secret.

Methodological disagreements and reproducibility problems belong in the public
research issue forms when they contain no sensitive information.

## Recorded historical environment

The original 12 November 2026 experiment used pyarrow 21.0.0 and ujson 5.11.0.
Concrete advisories were discovered after repository scanning was enabled:
[Arrow IPC pre-buffering](https://github.com/advisories/GHSA-rgxp-2hwp-jwgg) and
[UltraJSON parsing/serialization issues](https://github.com/advisories/GHSA-3j69-69wj-xqx2).
The maintenance security floor is pyarrow 23.0.1 and ujson 5.13.0;
current requirements may be newer. The Linux audit
with those versions produces the same question-level metric digest.

The historical environment is retained as provenance in
`environments/2026-11-12-original.json` and the original protected protocol tag.
It is not the maintained installation recommendation. Input checksums and an
isolated reproduction environment remain part of reproducing an old campaign.
