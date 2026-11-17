# Plan — stage 1 (track dossier)

Started 2026-11-17T04:58Z. Result folder: `/Users/ryugi62/band-work/result-s1/stage-1/`.
Specification: `/Users/ryugi62/band-work/sf-2026/challenges/dossier/spec/stage-1.md` (pasted in full into every handoff).

Work items (one commit each, builder, in this order; ledger row IDs are assigned by the verifier):

| # | Item | Scope |
|---|---|---|
| W1 | Service skeleton and control endpoints | HTTP server on `PORT`, `/health`, `POST /_test/reset`, `POST /_test/clock` (clock only moved by reset / clock calls), error envelope and status mapping (§3, §5), JSON conventions, bearer-token middleware. |
| W2 | Accounts | `/auth/signup`, `/auth/login`, password hashing, seeded users, multiple tokens per user, 401 rules (§6). |
| W3 | Domain and support rules | Domain normalisation and validation (§4); page header / prose split, sentence splitting, value formats, normalisation and the "supports" decision of Appendix A as a pure module with unit tests. |
| W4 | Dossier API and idempotency | `POST /dossiers`, `GET /dossiers/{domain}`, `POST .../refresh`, `GET /dossiers`, idempotency (§7) incl. concurrent identical requests, one build per dossier, reset-safe builds (§8, §11). |
| W5 | Research pipeline | Provider access through `web_router` only (Python in-process or helper), budgeted build under 80 units per build, research run, gathering, field decision with locally verified citations, failure handling (§4, §8, §9). |
| W6 | Export / import | `GET /_test/export`, `POST /_test/import` (§10). |
| W7 | Delivery | `Dockerfile` (webrouter install in build), `RUN.md`, unit-test command, shipped checks run clean. |

Sequence: verifier ledger + probes (stage ledger) → builder W1..W7 → verifier and cost-auditor in parallel → rework rounds (max 4).
