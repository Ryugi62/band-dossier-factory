# Cost audit — stage 1, round 2

Commit audited: `9166a2805e9c6481c7225b4eafc53f2758d464a8` (fresh clone, `docker build` of `stage-1/`,
`docker network create --internal`, mock `dossier-web` with the sample corpus as the only reachable host).
Previous round: `factory/costs/stage-1-r1.md` (f72df40). Auditor: cost-auditor.

**Decision: ACCEPT** (units per correct item 5.591 vs 5.591 in round 1: +0.0%, limit +10%).

## Workload (same as round 1)

12 sample companies x epochs 0 and 1 = 24 builds; per build: mock reset to the epoch, service `/_test/reset`,
login, `POST /dossiers`, poll to not `building`, read `GET /_mock/log`. `spent_units` equalled the log's cost
sum in 24 of 24 builds.

## Figures (round 2 / round 1)

| Measure | r2 | r1 |
|---|---|---|
| Builds `ready` | 24 / 24 | 24 / 24 |
| Units total | 766 | 766 |
| Provider calls | 190 | 190 |
| Units per build | 31.9 (min 27, max **34**, cap 80) | 31.9 (27-34) |
| Known / correct known fields | 137 / 137 | 137 / 137 |
| **Units per correct item** | **5.591** | 5.591 |
| Duplicate successful calls | 0 | 0 |
| Wall time per build | 0.20-0.46 s | 0.20-0.44 s |

| Kind | Calls | Units |
|---|---|---|
| nimble research | 24 | 600 |
| nimble search `lite` (24 domain, 90 field) | 114 | 114 |
| nimble extract | 52 | 52 |
| Tavily, `fast`/`deep`, `render` | 0 | 0 |

Per-build call sequences are identical to round 1 (the call logs of every company and epoch have the same
units, call counts, field searches and extracts: ashgrove 32/32, brightwater 33/33, corvid 32/32, ferncliff 34/34,
halvorsen 34/34, larkspur 34/34, mosaic 27/27, ostrava 32/32, pemberton 33/33, quillmate 32/32, tidemark 28/30,
windrush 31/31). The deadline and retry changes (46680d2, 9166a28) cost nothing on the mock.

Largest single unit of work: 34 units (42.5% of the cap).

## Calls that bought nothing used

Same as round 1: 18 of 52 extracts (18 units), 8 of 90 field searches (8 units), the domain search of larkspur (2,
required by §4), and 8 of 24 research runs with no cited excerpt (200 units, mandated by D2). Non-research waste
28 units of 766 (3.7%).

## Support check

All 137 known fields: every cited excerpt appears (whitespace collapsed) in text a logged call returned for the same
URL, and supports its value under the verifier's `appendix_a.py`: 0 not served, 0 not supporting. Re-confirmed by one
1-unit nimble extract each through `web_router` (12 values, 6 in epoch 0 and 6 in epoch 1, covering all six fields): 12 of 12
excerpts inside the page prose.

## Other measurements

- Refresh (ashgrove): 32 more units in 8 calls, `spent_units` 32 -> 64. Replay of the refresh, replay of
  the create, GET, list, export and POST for `www.ASHGROVE-SOLAR.TEST.` (existing dossier): 0 provider calls.
- Rate-limit weather on, 12 companies: all `ready`, identical spend and known fields as without weather, 20 refused calls
  at cost 0 across 10 builds, 0 duplicates.
- Fault modes, halvorsen-robotics (units spent == log cost in all):

| Mode | State | Units | Refused calls (cost 0) | Domain searches answered | Known | Seconds |
|---|---|---|---|---|---|---|
| nimble search/extract/research 500 | failed | 0 | 26 | 0 | 0 | 5.8 |
| same, 429 permanently | ready | 26 | 20 | 1 | 3 | 5.8 |
| throttle (first attempt of each call 429) | ready | 34 | 10 | 1 | 6 | 3.5 |
| search 500 only | ready | 26 | 22 | 0 | 1 | 5.8 |
| research 500 only | ready | 8 | 4 | 1 | 5 | 3.5 |
| 0.8 s delay on all methods | ready | 34 | 0 | 1 | 6 | 2.5 |

  Every mode stays far under the cap, nothing is spent on a refused call, and no identical successful call is
  repeated. The retry limit (3 retries, then give up) keeps refused calls bounded (26 attempts in the worst case
  above).

## Advisory (unchanged, not a finding)

The type (b) extracts were uncited 18 of 52 times; the 25-unit research run is 78% of all units (D2).
The live branch (every relevant page extracted, 1 unit each, still under 80 for at most 10 pages after the
reservation rule) cannot be measured offline; the 80-unit reservation guarantees the cap there.
