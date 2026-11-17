# Cost audit — stage 4, round 1

Commit audited: `97cc83ad042382c1c48b17d88fa22bf7cfc9ec2b` (fresh clone, `docker build` of `stage-4/`,
`docker network create --internal`, mock `dossier-web` with the sample corpus as the only reachable host).
Previous round: stage 3 round 1, `factory/costs/stage-3-r1.md` (0c9722c, 9.377 units per correct item).
Auditor: cost-auditor.

**Decision: ACCEPT.** No build above the cap (max 77 of 80), no batch above its budget, every value cites a
served excerpt, units per correct item 8.210 vs 9.377 (-12.4%). One non-blocking finding (F1, batches under a
tight budget) is reported below for the planner to decide.

## Workload (same as stages 1-3)

12 sample companies x epochs 0 and 1 = 24 builds: mock reset to the epoch, service `/_test/reset`, login,
`POST /dossiers`, poll until not `building`, read `GET /_mock/log`. 24 of 24 `ready`; `spent_units` equalled the
log's cost sum in 24 of 24.

## Figures (stage 4 r1 / stage 3 r1)

| Measure | s4 r1 | s3 r1 |
|---|---|---|
| Units total | 1527 | 1519 |
| Provider calls | 549 (22.9 per build) | 577 |
| Units per build | mean 63.6, min 56, **max 77** (cap 80: 96%) | mean 63.3, max 76 |
| Known + contested fields = correct items | 186 / 186 (138 of the six fields, 24 `executives`, 24 `investors`) | 162 / 162 |
| Candidates | 311 (4.9 units per candidate) | 261 |
| **Units per correct item** | **8.210** | 9.377 |
| Duplicate successful calls | 0 | 0 |
| URL rendered twice, or extracted plain and rendered, in a build | 0 | 0 |

| Kind | Calls | Units | Share |
|---|---|---|---|
| nimble research | 24 | 600 | 39.3% |
| nimble search `lite` (24 domain, 288 name/phrase) | 312 | 312 | 20.4% |
| nimble extract `render` (3 per URL) | 201 | 603 | 39.5% |
| nimble extract plain (1 per URL) | 12 | 12 | 0.8% |
| Tavily, Kernel, Browserbase, search `fast`/`deep` | 0 | 0 | 0% |

Per company, epoch 0 / epoch 1 (units): ashgrove 56/56, brightwater 69/72, corvid 56/56, ferncliff 71/68,
halvorsen 62/65, larkspur 69/72, mosaic 56/56, ostrava 65/68, pemberton 57/57, quillmate 62/65, tidemark 74/77,
windrush 59/59. These match the builder's handoff.

## Correctness of the items

For each of the 186 fields, against the rendered text the log shows and the verifier's oracles (`appendix_a.py`,
`oracle3.py`, `oracle4.py`):

- each of the 311 candidates appears (whitespace collapsed) in the prose of the 3-unit rendered extract of its URL;
- it supports its value (six fields by Appendix A, `executives` by title, `investors` by `investor_names`);
- its `true_from`, `kind` (registrant rule) and `origin` (rules 1-4, up to three `Canonical` hops, looked up in the
  texts the log shows) equal what the oracle derives from the rendered header;
- value, `true_from`, `citations`, `status`, order and `selected` follow from `select`, `select_exec` and
  `derive_investors`; `origins`, `corroborated` and `corroborated_since` follow from the candidates (each build is
  the first, so `corroborated_since` is the build time or null).

0 violations; the 24 x 0 `unknown` fields have empty `origins`, `corroborated` false, `corroborated_since` null.

## Why the units per item fell (+8 units, +24 items)

| Part | Units |
|---|---|
| Name/phrase searches 12 per build instead of 14 (312 vs 360) | -48 |
| 18 more renders (201 vs 183): investor pages | +54 |
| 2 more plain probes (12 vs 10) | +2 |
| **Total** | **+8** |

`investors` adds 24 items for 54 units of renders. The 2 fewer searches per build are the D46 re-measurement; I did
not re-test completeness (the builder reports 0 of 301 supporting pages missed; on this workload every candidate page
the oracle accepts is rendered, see below).

## Calls that bought nothing used

| Kind | Calls | Units | Note |
|---|---|---|---|
| render | 0 of 201 | 0 | every rendered page yielded a candidate |
| plain extract | 12 of 12 | 12 | probes of snippet-cut pages that supported nothing (0.8% of units); no original needed a separate fetch on this corpus (rendered pages were reused) |
| research | no cited candidate in 8 of 24 builds | 200 | mandated by D2 |

## Batches (spec §Batches, D40-D41; new in stage 4)

Fresh service, same mock. `batch.spent` is `GET /batches/{id}`; "log cost" is the mock's call log for the batch.

| Budget | Domains (pre-existing) | State | batch.spent | Log cost | Calls | Max build | Fields not `unknown` |
|---|---|---|---|---|---|---|---|
| 200 | 2 | done | 125 | 125 | 45 | 69 | 15 |
| 1000 | 4 (2) | done | 127 | 127 | 45 | 71 | 30 |
| 300 | 4 | done | 252 | 252 | 90 | 71 | 30 |
| 300 | 5 | done | 299 | 299 | 109 | 68 | 33 |
| 300 | 6 | done | 298 | 298 | 110 | 62 | 26 |
| 300 | 8 | done | 300 | 300 | 108 | 38 | **0** |
| 300 | 10 | done | 300 | 300 | 60 | 38 | **0** |
| 300 | 12 | done | 300 | 300 | 36 | 38 | **0** |
| 75 | 3 | done | 75 | 75 | 27 | 38 | **0** |
| 30 | 3 | done | 30 | 30 | 6 | 28 | **0** |
| 1 | 2 | done | 1 | 1 | 1 | 1 | 0 |

- Budget never exceeded; `batch.spent` equals the log cost in 11 of 11 batches; every build ended `ready` and
  spent at most 80; the two pre-existing dossiers of the 1000 batch cost it nothing (127 units for 2 new builds).
- Replay of `POST /batches`: 200, 0 provider calls (6 of 6). Another user's batch: 404 (6 of 6).
- **Restart mid-batch** (3 companies, budget 150, nimble delayed 0.6 s so builds are in flight, `docker kill` + `docker start`
  at 2 s): health 200 after 0.2 s; no dossier `building` when first read; batch `done` with `spent_units` 150 = budget;
  the dossiers' `spent_units` sum to 150 (62 + 50 + 38); the mock billed 150 in all, none after the restart; every build at
  most 80; a refresh after the restart returned 202 and started a new build.

### F1 (non-blocking finding): a batch whose budget cannot finish all its builds spends it and learns nothing

- **Call kinds and counts:** with 8, 10 or 12 domains and a budget of 300, the batch spends the whole 300 units on research
  (25 per build) and name/phrase searches (13 per build), 38 units per build, and no build reaches its renders. Result: 300
  units, 0 fields known. The same holds for 3 domains at budgets 75 and 30. The other half of the table shows the same 300
  units give 30 known fields for 4 domains (252 units), 33 for 5 and 26 for 6.
- **Why:** the builds run concurrently and reserve their calls in the order they come, so every build is still in its
  research-and-search phase when the budget is gone (8 x 38 = 304 > 300). Renders, which are the only calls that produce
  candidates (D13), come last in a build.
- **Cheaper alternative:** let a batch's builds take the budget one after the other (in the order of `domains`), or admit a new
  build only while the unspent budget still covers about one build (about 65 units on this corpus). The same 300 units then
  finish 4 or 5 dossiers (30 to 33 fields, measured above) instead of none. The spec's wording is met either way, so this does not
  change the verdict; I did not use the REJECT rules of my brief because none of them applies (no cap or budget exceeded,
  every value served, units per item fell).

## Other measurements

- **Refresh** (ashgrove, same epoch): second build 56 units (20 calls), `spent_units` 56 -> 112. Replay of the refresh,
  replay of the create, GET, list, export and POST for the existing domain: 0 provider calls.
- **Rate-limit weather on**, 12 companies, epoch 0: all `ready`, same units as without weather (56-74), 24 refused calls at
  cost 0, 0 duplicates.
- **Provider failure**, halvorsen-robotics (spent == log cost in all; refused calls cost 0; 0 duplicates; every build < 80):

| Mode | State | Units | Refused (cost 0) | Domain searches answered | Seconds |
|---|---|---|---|---|---|
| 500 on search/extract/research | failed | 0 | 56 | 0 | 6.9 |
| permanent 429 | ready | 62 | 72 | 1 | 10.4 |
| throttle (first attempt 429) | ready | 62 | 24 | 1 | 3.6 |
| search 500 only | ready | 28 | 52 | 0 | 6.9 |
| research 500 only | ready | 34 | 4 | 1 | 3.4 |
| 0.8 s delay | ready | 62 | 0 | 1 | 2.7 |

## Advisory (not a finding)

1. **Margin to the cap.** tidemark-energy epoch 1 spends 77 of 80 units (13 renders), epoch 0 spends 74. This is the
   carry-over of D34. The reservation rule keeps every build at or below 80 but a company with more supporting pages
   than this corpus would have its evidence cut at the cap.
2. Research is 39.3% of units and mandated by D2.

Baseline for any later round of stage 4: 8.210 units per correct item (186 items), 1527 units on this workload, max 77
per build.
