# Cost audit — stage 4, round 2 (rework of F1)

Commit audited: `7a3a10c148d085f9b25658d0c175e13a7ce450de` (fresh clone, `docker build` of `stage-4/`,
`docker network create --internal`, mock `dossier-web` with the sample corpus as the only reachable host).
Previous round: stage 4 round 1, `factory/costs/stage-4-r1.md` (97cc83a, 8.210 units per correct item).
Auditor: cost-auditor. Changes since 97cc83a: f7bc09f (support.py split) and 7a3a10c (batch admission, D47).

**Decision: ACCEPT.** Units per correct item 8.210 vs 8.210 (+0.0%, limit +10%); max build 77 of 80; F1 is fixed.

## Fixed workload (same as every round)

12 sample companies x epochs 0 and 1 = 24 builds, same method as stage-4 round 1. 24 of 24 `ready`; `spent_units` equalled
the log's cost sum in 24 of 24.

| Measure | r2 (7a3a10c) | r1 (97cc83a) |
|---|---|---|
| Units total | 1527 | 1527 |
| Provider calls | 549 | 549 |
| Units per build | mean 63.6, min 56, max 77 | same |
| Correct items | 186 / 186 | 186 / 186 |
| **Units per correct item** | **8.210** | 8.210 |
| Duplicate successful calls | 0 | 0 |
| Kinds (units) | research 600, search 312, render 603, plain 12 | same |

Every candidate (311) was re-verified as in round 1 (rendered text, Appendix A and the title/investor oracles, `true_from`, `kind`,
`origin`, selection, `origins` / `corroborated` / `corroborated_since`): 0 violations. The per-build call sequences are identical
to round 1, so the admission change costs nothing on a single build; the 0 wasted renders and the 12 plain probes are unchanged.

## F1 re-check: the batch table

Same method as round 1 (fresh `/_test/reset`, mock log cleared per batch). "Known" = fields not `unknown` over all dossiers
of the batch; "max build" = the largest `spent_units` of a new dossier.

| Budget | Domains | r1 spent / known | r2 spent / known | r2 log cost | r2 max build | State |
|---|---|---|---|---|---|---|
| 300 | 3 | n/m | 181 / 23 | 181 | 69 | done |
| 300 | 4 | 252 / 30 | 252 / 30 | 252 | 71 | done |
| 300 | 5 | 299 / 33 | 300 / **35** | 300 | 71 | done |
| 300 | 6 | 298 / 26 | 300 / **35** | 300 | 71 | done |
| 300 | 8 | 300 / **0** | 300 / **35** | 300 | 71 | done |
| 300 | 10 | 300 / **0** | 300 / **35** | 300 | 71 | done |
| 300 | 12 | 300 / **0** | 300 / **35** | 300 | 71 | done |
| 75 | 3 | 75 / **0** | 56 / **7** | 56 | 56 | done |
| 75 | 6 | n/m | 56 / 7 | 56 | 56 | done |
| 30 | 3 | 30 / 0 | 30 / 0 | 30 | 30 | done |
| 30 | 5 | n/m | 30 / 0 | 30 | 30 | done |
| 200 | 2 | 125 / 15 | 125 / 15 | 125 | 69 | done |
| 1000 | 4 (2 pre-existing) | 127 / 30 | 127 / 30 | 127 | 71 | done |
| 1000 | 12 | n/m | 756 / 93 | 756 | 74 | done |
| 1 | 2 | 1 / 0 | 0 / 0 | 0 | 0 | done |

- F1 is fixed: the 300-unit batch now gives 35 known fields for 5 to 12 domains (8.6 units per known field, close to the
  8.2 of unconstrained builds) where it gave 0 for 8 or more.
- `batch.spent` equalled the mock log cost in 15 of 15 batches and never exceeded `budget_units`; every build ended `ready` and
  spent at most 80; the batches covering their builds (budget 1000, 12 domains: 756 units, 0.9 s) still run concurrently.
- Replay of `POST /batches`: 200 with 0 provider calls (15 of 15). Another user's batch: 404 (15 of 15). Dossiers that already
  existed cost the batch nothing.
- Under a budget that covers one build only (75 units, 3 or 6 domains) the first domain gets 56 units and the rest are not
  admitted: 19 units are left unspent, fewer than the 26 (research + domain search) a further build needs. No unit
  is spent without a chance of an item.
- Budget 1 now spends 0 units (round 1: 1 unit for a domain search that could not produce a field), also within the budget.
- Budget 30 still spends 30 units (research 25 + 5 searches) for 0 fields: see the advisory.

## Restart mid-batch (D43, D47)

8 domains, budget 300, nimble delayed 0.6 s so builds are in flight and some are still queued; `docker kill` + `docker start` at 2.5 s
(after 204 units, 74 calls):

- Health 200 after 0.1 s; no dossier `building` when first read; batch `done`.
- `batch.spent` 231 = the sum of the dossiers' `spent_units` (62 + 69 + 74 + 26 + 0 + 0 + 0 + 0); the mock billed no more than that
  (billed <= batch spent <= budget 300); no provider call after the restart; every build at most 80.
- Two builds ended `ready` (halvorsen, tidemark), larkspur `failed` after 69, ashgrove `failed` after 26, and the four queued builds
  `failed` with 0 units: the queue costs nothing at a restart. A refresh afterwards returned 202.

## Other measurements (unchanged from round 1)

- Refresh: 56 units (20 calls), `spent_units` 56 -> 112; replay of the refresh, replay of the create, GET, list, export and POST for
  an existing domain: 0 provider calls.
- Rate-limit weather on: all 12 `ready`, same units (56-74), 24 refused calls at cost 0, 0 duplicates.
- Provider failure, halvorsen-robotics (spent == log cost; refused calls cost 0; 0 duplicates; every build < 80):

| Mode | State | Units | Refused (cost 0) | Seconds |
|---|---|---|---|---|
| 500 on search/extract/research | failed | 0 | 56 | 6.9 |
| permanent 429 | ready | 62 | 72 | 10.5 |
| throttle | ready | 62 | 24 | 3.7 |
| search 500 only | ready | 28 | 52 | 7.0 |
| research 500 only | ready | 34 | 4 | 3.5 |
| 0.8 s delay | ready | 62 | 0 | 2.7 |

## Advisory (not a finding)

1. With a budget between 26 and about 45 units (30 here) a build is admitted and spends the whole budget on the 25-unit research run
   and a few searches, with no unit left for a 3-unit render, so it yields nothing. Starting no build below the cost of research plus
   the domain search plus one render (about 30 to 35 units) would leave the units unspent instead of wasted; the effect is small
   and depends on D2, so I do not call it a finding.
2. tidemark-energy epoch 1 spends 77 of 80 units (the D34 carry-over): the reservation rule keeps it at or below 80.

Baseline for any later round: 8.210 units per correct item (186 items), 1527 units on this workload, max 77 per build; batch table
above.
