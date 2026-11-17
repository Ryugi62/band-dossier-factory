# Cost audit — stage 3, round 1

Commit audited: `0c9722c422e0c0ac67b95d50117cb46b0eb56cf2` (fresh clone, `docker build` of `stage-3/`,
`docker network create --internal`, mock `dossier-web` with the sample corpus as the only reachable host).
Previous round: stage 2 round 1, `factory/costs/stage-2-r1.md` (3e32ac8, 8.935 units per correct item).
Auditor: cost-auditor.

**Decision: ACCEPT.** Units per correct item 9.377 vs 8.935 (+4.9%, limit +10%); no build above the cap
(max 76 of 80); every value cites a served excerpt.

## Workload (same as stages 1 and 2)

12 sample companies x epochs 0 and 1 = 24 builds: mock reset to the epoch, service `/_test/reset`, login,
`POST /dossiers`, poll until not `building`, read `GET /_mock/log`. 24 of 24 `ready`; `spent_units` equalled the
log's cost sum in 24 of 24.

## Figures (stage 3 r1 / stage 2 r1)

| Measure | s3 r1 | s2 r1 |
|---|---|---|
| Units total | 1519 | 1233 |
| Provider calls | 577 (24.0 per build) | 359 |
| Units per build | mean 63.3, min 55, **max 76** (cap 80: 95%) | mean 51.4, max 59 |
| Known + contested fields = correct items | 162 / 162 (138 of the six fields + 24 `executives`) | 138 / 138 |
| Candidates | 261 (5.8 units per candidate) | 205 |
| **Units per correct item** | **9.377** | 8.935 |
| Units per correct item, six fields only (reference) | 11.007 | 8.935 |
| Duplicate successful calls | 0 | 0 |
| URLs rendered twice in a build | 0 | 0 |

| Kind | Calls | Units | Share |
|---|---|---|---|
| nimble research | 24 | 600 | 39.5% |
| nimble search `lite` (24 domain, 336 name/phrase) | 360 | 360 | 23.7% |
| nimble extract `render` (3 per URL) | 183 | 549 | 36.1% |
| nimble extract plain (1 per URL) | 10 | 10 | 0.7% |
| Tavily, Kernel, Browserbase, search `fast`/`deep` | 0 | 0 | 0% |

Per company, epoch 0 / epoch 1 (units): ashgrove 55/55, brightwater 65/68, corvid 58/58, ferncliff 64/61,
halvorsen 64/67, larkspur 70/70, mosaic 58/58, ostrava 61/64, pemberton 59/59, quillmate 64/67, tidemark 76/76,
windrush 61/61. These match the builder's handoff.

## Correctness of the items

For each of the 162 fields, against the rendered text the log shows and the verifier's oracles
(`appendix_a.py`, `oracle3.py`):

- each of the 261 candidates appears (whitespace collapsed) in the prose of the 3-unit rendered extract of its URL;
- it supports its value (the six fields by Appendix A; `executives` by `supported_title` with the title's phrases);
- its `true_from` equals `page_true_from(Effective, Published)` of the rendered header;
- its `learned_at` is the build time, and the field's value, `true_from`, `citations` and `status` equal what
  `select` / `select_exec` and the Status table give; exactly the rule's candidates are `selected`.

0 violations. For the 24 `unknown` fields: `value` null, `true_from` and `learned_at` null, no candidates.

## Why the increase (+286 units, +4.9% per item)

| Part | Units |
|---|---|
| 8 more lite searches per build: one with the title phrases, one with the shortest phrase for each of the six fields and for executives (360 - 168) | +192 |
| 34 more rendered extracts (183 - 149): the pages that name executives (the new `executives` field) | +102 |
| 8 fewer plain probes (10 - 18) | -8 |
| **Total** | **+286** |

The extra pages are forced by the new `executives` field (D31) and the 24 new correct items absorb most of the
cost per item. The units per item stay inside the 10% allowance without needing the explanation.

## Calls that bought nothing used

| Kind | Calls | Units | Note |
|---|---|---|---|
| render | 0 of 183 | 0 | every rendered page yielded a candidate |
| plain extract | 10 of 10 | 10 | probes of snippet-cut pages that supported nothing (0.7% of units) |
| research | no cited candidate in 8 of 24 builds | 200 | mandated by D2 (the six fields only) |
| search lite | see advisory | | no duplicate; each search has a distinct query |

## Other measurements

- **Refresh** (ashgrove, same epoch): second build 55 units (21 calls), `spent_units` 55 -> 110. Replay of the refresh,
  replay of the create, GET, list, export and POST for the existing domain: 0 provider calls. A refresh after the mock
  moved to epoch 1 (halvorsen): 67 units, 27 calls (total 131).
- **New reads** `?as_of=`, `/values?true_at=`, `/history`, `/changes`, `GET /dossiers`: 5 of 5 answered 200, 0 provider calls.
  The feed held 1 entry after the refresh that changed a value.
- **Restart** (`docker kill` + `docker start` of the service, mock untouched): dossier identical, feed identical, replay of the
  refresh key 200, 0 provider calls before and after (53 and 53).
- **Rate-limit weather on**, 12 companies, epoch 0: all `ready`, same units as without weather (55-76), 24 refused calls at cost 0,
  0 duplicates.
- **Fault modes**, halvorsen-robotics (spent == log cost in all; refused calls cost 0; 0 duplicates; every build < 80):

| Mode | State | Units | Refused (cost 0) | Domain searches answered | Seconds |
|---|---|---|---|---|---|
| 500 on search/extract/research | failed | 0 | 64 | 0 | 6.9 |
| permanent 429 | ready | 64 | 78 | 1 | 10.2 |
| throttle (first attempt 429) | ready | 64 | 26 | 1 | 3.7 |
| search 500 only | ready | 28 | 60 | 0 | 6.9 |
| research 500 only | ready | 36 | 4 | 1 | 3.5 |
| 0.8 s delay | ready | 64 | 0 | 1 | 2.6 |

## Advisory (not a finding)

1. **Margin to the cap.** tidemark-energy spends 76 of 80 units in both epochs (12 rendered pages). The reservation rule keeps it at
   or below 80, but a company with more supporting pages than this corpus would have its evidence cut at the cap, and any further
   per-build call added in stage 4 would start to do that on this workload.
2. **Search yield.** On this workload the 360 searches (15 per build) reached every candidate page, but a greedy minimal cover needs
   56 (about 2.3 per build) once the pages that research cites are set aside; the name/phrase queries were the only source of
   2 candidate pages (both from the `raised funding investment invested` query, in the six-field queries of stage 2).
   The builder reports that a narrower query set missed a supporting page of tidemark's pressline (S1-P07, EV2) on the stage-3
   corpus; by D23 completeness wins and I do not call this a finding. If units per item become a problem, trying "one name
   query, then only the queries of fields still unsupported" is the first thing to measure.
3. Research is 39.5% of units and mandated by D2.

Baseline for the next stage-3 round: 9.377 units per correct item (162 items), 1519 units on this workload, max 76 per build.
