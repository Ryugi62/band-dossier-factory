# Cost audit — stage 2, round 1

Commit audited: `3e32ac880a826539c69ab9c662f90c9588d19126` (fresh clone, `docker build` of `stage-2/`,
`docker network create --internal`, mock `dossier-web` with the sample corpus as the only reachable host).
Previous round: stage 1 round 2, `factory/costs/stage-1-r2.md` (9166a28, 5.591 units per correct item).
Auditor: cost-auditor.

**Decision: ACCEPT.** Units per correct item rose from 5.591 to 8.935 (+59.8%, over the 10% limit), and the
increase is explained by new requirements: see "Why the increase is forced".

## Workload (same as stage 1)

12 sample companies x epochs 0 and 1 = 24 builds; mock reset to the epoch, service `/_test/reset`, login,
`POST /dossiers`, poll until not `building`, read `GET /_mock/log`. 24 of 24 builds `ready`; `spent_units`
equalled the log's cost sum in 24 of 24.

## Figures (stage 2 r1 / stage 1 r2)

| Measure | s2 r1 | s1 r2 |
|---|---|---|
| Units total | 1233 | 766 |
| Provider calls | 359 (15.0 per build) | 190 |
| Units per build | mean 51.4, min 44, **max 59** (cap 80: 73.8%) | mean 31.9, max 34 |
| Known + contested fields / correct | 138 / 138 | 137 / 137 |
| Candidates | 205 (6.0 units per candidate) | n/a |
| **Units per correct item** | **8.935** | 5.591 |
| Duplicate successful calls | 0 | 0 |
| URLs rendered twice in a build | 0 | n/a |

| Kind | Calls | Units | Share |
|---|---|---|---|
| nimble research | 24 | 600 | 48.7% |
| nimble search `lite` (24 domain, 144 name/phrase) | 168 | 168 | 13.6% |
| nimble extract `render` (3 per URL) | 149 | 447 | 36.3% |
| nimble extract plain (1 per URL) | 18 | 18 | 1.5% |
| Tavily, Kernel, Browserbase, search `fast`/`deep` | 0 | 0 | 0% |

Per company, epoch 0 / epoch 1 (units): ashgrove 44/44, brightwater 54/57, corvid 48/48, ferncliff 51/48,
halvorsen 53/56, larkspur 56/56, mosaic 47/47, ostrava 47/50, pemberton 49/49, quillmate 54/57, tidemark 59/59,
windrush 50/50. These match the builder's handoff.

## Correctness of the items

Every candidate of every known or contested field (205) was checked against the rendered text the log shows:

- its excerpt appears (whitespace collapsed) in the prose of the 3-unit rendered extract of the same URL, 205 of 205;
- it supports its value under the verifier's `appendix_a.py`, 205 of 205;
- its `kind` equals the rendered header's `Kind` (or the host default), 205 of 205;
- the candidates of the 144 fields are in selection-rule order (authority, recency, URL, provider, value),
  the first is the only `selected`, `value` is the selected one and `citations` are the candidates of that value,
  in order; `status` is `known` exactly when all candidates agree: 0 violations.

## Why the increase is forced

1. Stage 2 makes every value that every supporting page states a candidate (once per page), so the build must read
   every supporting page, not only enough pages to support one value per field.
2. D13 / the spec ("a citation's excerpt must appear in the page's text", text = what a browser shows) requires the
   rendered text. I rendered and plainly extracted the same 167 URLs the builds rendered: **10 of 167 differ**
   (e.g. ferncliff-foods.test/team: plain text says "Ingrid Brennan is the chief executive", the rendered text says
   "Priya Castillo is the chief executive"; ferncliff-foods.test/about/leadership names a different CFO; larkspur
   `/about` differs too). A plain-text excerpt from such a page would not appear in the page's text, so rendering
   (3 units, not 1) cannot be replaced by the cheaper extract or by a snippet.
3. Floor on this workload: research + domain search 24 x 26 = 624, name/phrase searches 24 x 6 = 144, renders
   149 x 3 = 447, plain probes 18: **1233**, the measured total. (The handoff counts 153 renders and 6 plain
   units; the log shows 149 and 18, the same total.)

## Calls that bought nothing used

| Kind | Calls | Units | Note |
|---|---|---|---|
| render | 0 of 149 | 0 | every rendered page yielded a candidate |
| plain extract | 18 of 18 | 18 | probes of snippet-cut pages that supported nothing; plain first costs 1, a direct render 3, so it is the cheaper order while most such pages support nothing (0 of 18 here). 1.5% of units. |
| research | 8 of 24 runs | 200 | no candidate came from a research citation; mandated by D2 |
| search lite | 0 beyond the required domain search | 0 | |

Completeness check (so that "no waste" does not hide skipped evidence): I rendered the 637 distinct gathered pages
the builds did not render (search results and the 18 probed pages) and ran the oracle over their text: **0** support any
value, so no candidate was missed to save units.

## Other measurements

- **Refresh** (ashgrove): second build 44 units (12 calls), `spent_units` 44 -> 88; replay of the refresh, replay of the
  create, GET, list, export, POST for the existing domain written `www.ASHGROVE-SOLAR.TEST.`: 0 provider calls.
- **UI documents** (`Accept: text/html` for `/`, `/signup`, `/login`, `/contested`, `/dossiers/{d}`,
  `/dossiers/{d}/evidence` and an invalid domain): all 200, 0 provider calls.
- **Rate-limit weather on**, 12 companies epoch 0: all `ready`, same units as without weather (44-59), 24 refused calls at
  cost 0, 0 duplicates.
- **Fault modes**, halvorsen-robotics (spent == log cost in all; refused calls cost 0; 0 duplicates; every build < 80):

| Mode | State | Units | Refused (cost 0) | Domain searches answered | Seconds |
|---|---|---|---|---|---|
| 500 on search/extract/research | failed | 0 | 32 | 0 | 6.7 |
| permanent 429 | ready | 53 | 51 | 1 | 10.2 |
| throttle (first attempt 429) | ready | 53 | 17 | 1 | 3.5 |
| search 500 only | ready | 28 | 28 | 0 | 6.7 |
| research 500 only | ready | 25 | 4 | 1 | 3.5 |
| 0.8 s delay | ready | 53 | 0 | 1 | 2.7 |

  Permanent 429 takes 10.2 s: retries wait 1.1 s each, up to 4 attempts (D15), and the waiting does not count toward
  the 10 s bound of stage 1 §8.

## Advisory (not a finding)

- The 144 units of name/phrase searches (11.7%) are needed to reach supporting pages beyond the first ten of the
  domain search (the builder measured 7 of 167 missed without them). I did not test whether fewer than six queries
  reach the same pages; a next round could try one name query plus the fields still missing.
- Research is 48.7% of units and mandated by D2.

Baseline for the next stage-2 round: 8.935 units per correct item, 1233 units on this workload, max 59 per build.
