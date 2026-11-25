# Dark factory entry: a four-seat band that built the Dossier track

Team: one person (Taegeol Kim) who configured the factory and dispatched each stage, plus four
Claude Code seats in one Band Desktop room. Track: `dossier`, stages 1 to 4.
The person wrote no code under `stage-N/`; each stage's only human input was one dispatch message.

## Run it in three minutes (mock web, no key)

```sh
git clone https://github.com/Ryugi62/band-dossier-factory && sh band-dossier-factory/demo.sh   # prints "ready: http://localhost:8080"
```

`demo.sh` clones the organizer's repository next to this one, builds the mock web and stage 4, starts both and waits for
`/health` (measured 2026-11-18: 39 s for both image builds without layer cache, 2 s to healthy; `sh demo.sh stop` cleans up).

## Try it with your own company (live API, not a stored screen)

After `demo.sh` prints "ready", open http://localhost:8080/ in a browser (sign up, enter a domain; the same page shows the empty, building, error, ready and contested states, see "The service on screen" below), or send the same input as an HTTP request and read the result
(measured 2026-11-19 on a fresh clone: `corvid-security.test` gave 8 fields, 56 of 80 units; a batch with `"budget_units": 30` ended at `spent_units` 30, never above):

```sh
TOKEN=$(curl -s -X POST localhost:8080/auth/signup -H 'content-type: application/json' -d '{"email":"you@example.com","password":"correct horse","display_name":"You"}' | sed 's/.*"token": *"\([^"]*\)".*/\1/')
curl -s -X POST localhost:8080/batches -H "Authorization: Bearer $TOKEN" -H 'Idempotency-Key: b1' -H 'content-type: application/json' -d '{"domains":["ostrava-mobility.test","halvorsen-robotics.test"],"budget_units":30}'   # then GET /batches/<batch_id>: spent_units stops at 30
curl -s -X POST localhost:8080/dossiers -H "Authorization: Bearer $TOKEN" -H 'Idempotency-Key: d1' -H 'content-type: application/json' -d '{"domain":"corvid-security.test"}'   # wait 10 s, GET /dossiers/corvid-security.test: fields, citations, spent_units <= 80
```

The mock web knows only the organizer's sample companies (`ashgrove-solar`, `brightwater-labs`, `corvid-security`, `ferncliff-foods`,
`halvorsen-robotics`, `larkspur-health`, `mosaic-freight`, `ostrava-mobility`, `pemberton-analytics`, all `.test`); any other domain returns all 8 fields
`unknown`. If your shell already sets `PORT`, run `PORT=8080 sh band-dossier-factory/demo.sh` (demo.sh reads it).

### The same startup by hand (without demo.sh)

The factory's four stages were built and checked against the organizer's mock web, so this is the path
that reproduces. Needs Docker and Python 3.12 (the harness needs `pip install -r harness/requirements.txt`).

```sh
git clone https://github.com/Ryugi62/band-dossier-factory
git clone https://github.com/band-ai/sf-buildathon-2026            # organizer's harness and mock web
(cd sf-buildathon-2026 && python -m harness check ../band-dossier-factory --track dossier)   # exit 0
cd band-dossier-factory
docker build -t dossier-web ../sf-buildathon-2026/challenges/dossier/web && docker network create dossier
docker run --rm -d --name web --network dossier -e MOCK_ADMIN_TOKEN=local-admin \
  -v "$PWD/../sf-buildathon-2026/challenges/dossier/web/corpus/sample:/data/corpus:ro" dossier-web
docker build -t dossier-s4 stage-4 && docker run --rm -d --name dossier-s4 --network dossier -p 8080:8080 \
  -e PORT=8080 -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily dossier-s4
curl -s localhost:8080/health                                        # {"status": "ok"}
```

`RUN.md` (repository root) has the same commands, plus signing up, researching a sample domain and cleaning up. It passes
`NIMBLE_BASE_URL` only when it is set and non-empty: an empty value counts as set and fails every provider call.
`harness check` prints one warning (the live-web file below) and exits 0.

## Limit on the live web

On the live web the service did **not** fill the fields. `dossier-runway.com.json` (stage 4, own Nimble trial
key, run twice) is `ready` with all 8 fields `unknown` (value `null`) at 79 of the 80-unit per-build cap. Re-measured on 18 November
by rebuilding the unchanged stage 4 with one extra log line per call: `runway.com` and `stripe.com` both end `ready`, 80 units,
all 8 fields unknown. The 80 units of the runway.com run were 25 for the research run, 13 searches, 32 successful plain page probes (1 unit each) and
10 probes that timed out or were refused but billed; the 3-unit rendered reads were skipped for lack of units, and only
rendered text becomes a candidate (`FACTORY.md`, "What did not work"). The cause is the budget split, not only provider
blocking (the 403s and 45 s timeouts took 10 of the 80 units). All unit figures below are on the mock web's
sample providers. We did not edit the stage folder or the response file after the run.

After the run, a diagnostic outside the factory (`docs/live-diag/`, human operator, patch stored there, stage folders unchanged) confirmed the cause: with at most 6 probes in flight, the same two domains at 79 and 80 units end with 4 and 6 of 8 fields filled (known or contested) instead of 0. The filled values are not checked against ground truth and at least one is wrong (`docs/live-diag/README.md`); it is not a factory result and not part of any figure below.

## Model spend (measured from the seats' session logs)

Four Claude Code sessions, 750 assistant messages, 287,781,523 tokens in total, of which **1,069,632 are output
tokens**; 283,731,532 are cache reads. Priced at public list prices (Opus 5.5 $4 in / $20 out, Sonnet 5.5 $2 / $10,
cache read $0.20 Opus / $0.10 Sonnet, 1-hour cache write 2x input) this is an estimated **$93.53**
(corrected 18 November from $96.94, which had priced Sonnet cache reads at the Opus rate). Per seat in `FACTORY.md`; the
method and per-seat output are in `docs/model-spend.txt`. The session logs live on the
operator's machine; their usage fields (no text) are in `docs/model-spend/usage.jsonl`, and `python3 docs/model-spend/aggregate.py` re-runs the sum from the clone.
The demo video is the 18 November 07:20 version, recorded before this was measured, and says spend was not measured:
the video was not changed, and the cost figures in this repository are the source of truth.

## How this differs from similar work

| Similar work | What it is | What it does not have that this entry has |
|---|---|---|
| [Verifier Factory](https://hackersquad.io/events/band-dark-factory-buildathon-san-francisco) (one of the two entries listed for this event on 18 November 2026) | Five seats: plan, research, verify, budget, record; its Budget Keeper holds one shared allowance. As of 18 November 2026 its listing says the submitted run paused on a provider account limit and "the staged build continues to the Nov 20 deadline" (still in progress) | Spend is audited per call: units per correct field are measured for every stage (5.591 to 9.377), and the cost auditor can reject a commit; the planner's mandate has a resume-and-blocker rule for provider limits (`mandates/planner.md`, lines 71 to 75) |
| [GeekForge](https://github.com/jacedeno/geekforge-dark-factory) (entry of the earlier WeAreDevelopers x BAND "Dark Factory" hackathon, 3 seats) | Plan, build, verify; reports 89 minutes and 110 M tokens in total | Totals only, no cost per correct output; here a fourth seat prices every call from the call log |
| The other four public winners of that hackathon (six winners of 167 submissions, announced 15 October 2026): [Midnight Workshop](https://github.com/PatriciaCR/tablekeeper-dark-factory), [Nightshift](https://github.com/vibhortayal/nightshift-pocketful), [gheware](https://github.com/ghewaredevopsai/pocketful-dark-factory-v2), [The Felt Five](https://github.com/kosesena/dark-factory-pocketful) (the sixth, Coord, has no public repository we could find) | Three to six seats with an independent verifier, sealed suites or planted faults (gheware 36 of 36, The Felt Five 81 seeded); they report totals: 120.8 min and about USD 82, 2 h 27 min and USD 59, 8 h 46 min and USD 74.88, 5 h 06 min and USD 202.59 | None of the five reports a cost per correct output (their READMEs and FACTORY.md read on 26 November 2026); here the cost auditor prices every call and the judged stage-4 figure is 8.210 units per correct field |
| [Nimble web search agents](https://docs.nimbleway.com/nimble-sdk/web-search-agents/best-practices/evaluating-results.md) (the research vendor of this track) | One 25-unit research run per company; its guide grades results, it does not verify them | On the same sample companies one research run alone costs at least 30.0 units per field (24 runs, 600 units, 20 cited fields, counting every cited field as correct); this service costs 8.210 at stage 4 (5.591 to 9.377 over stages 1 to 3) and a verifier checks every cited excerpt |
| [Onsen](https://hackersquad.io/events/band-dark-factory-buildathon-san-francisco) (the other entry listed for this event, 18 November 2026) | Six agents; "The Examiner writes hidden acceptance scenarios from the spec and posts only their SHA-256"; a Scout answers factual questions from the live web with Nimble; a Nap Guard wakes the human once | Its listing names no cost seat and gives no spend figure; here a fourth seat prices every call and the model tokens are measured from the session logs (below). It has what this entry lacks: a sealed hidden exam and a live-web research agent |
| [Organizer sample mandate](https://github.com/band-ai/sf-buildathon-2026) | Toy seat instructions for the track | No cost seat and no ledger; this entry's mandates are domain-free and reused for all four stages |

Patents: a KIPRIS search (Korean query on agent cost audit and code-generation verification) and a Google
Patents search (multi-agent verifier and cost-audit query) on 18 November 2026, result lists not archived; no top-ranked hit
describes a per-call cost auditor seat for a code factory. This is a title-level look at the first results, not a
proof that none exists.

## The measure

**Units per correct field** = metered units charged in the mock web's call log over a fixed workload of 24 builds
(12 sample companies, 2 epochs), divided by the number of correct fields those builds returned. One unit is one
cost unit of the mock web's price table (search 1, 5 or 15, extract 1 per URL, research 25).
**Judged figure, stage 4** (the organizer scores Research economy on a stage-4 workload): **8.210 units per correct field**, 1,527 units for 186 correct fields over the 24 builds (`factory/costs/stage-4-r2.md`), 3.65 times cheaper than the baseline below.
**Baseline:** one 25-unit research run per company and nothing else: 600 units for 20 cited fields = **30.0 units per field at best**
(8 of 24 runs return no field; every cited field is counted as correct, so the true baseline is not lower; the 8 cited fields the stage-4 key covers are all correct). Recompute it with `python3 factory/baseline/research_only.py <organizer repo>/challenges/dossier/web/corpus/sample` (reads the corpus files only; added by the operator after the run). A research run answers only the six stage-1 fields, so on the stage-4 workload it fills no executives or investors and the baseline stays 30.0. The baseline is our own simple one, not the organizer's benchmark (its definition is not public). Earlier stages, for reference only: 5.591 (stage 1), 8.935 (stage 2), 9.377 (stage 3). Stage 1 counts 6 fields per company; stage 3 counts 7 (executives added) and stage 4 counts 8 (investors added), so the four figures are not like for like; on the six original fields only, stage 3 costs 11.007 units per field (`factory/costs/stage-3-r1.md`, 'six fields only (reference)'), so the like-for-like figure at stage 3 is above the 8.935 of stage 2 and still 2.7 times below the baseline.

## Result in numbers

| Measure | Value | Source |
|---|---|---|
| Stages claimed on the shipped checks | 1, 2, 3, 4 (highest contiguous 4) | verifier's isolated run of revision `7a3a10c1` (report.json outside this repository), summarised in `factory/run-log.md` |
| Shipped checks, isolated | 122/122, 12/12, 9/9, 10/10; leaks 0, fabrications 0 | `factory/run-log.md`, stage 4 report |
| Work time per stage | 1 h 19, 1 h 02, 1 h 00, 1 h 27 | `factory/run-log.md` |
| Review rounds | 2, 1, 1, 2 (one rejection, at stage 1) | `factory/reviews/` |
| Research spend per correct field (units) | 8.210 at stage 4 (judged workload); 5.591, 8.935, 9.377 at stages 1 to 3 | `factory/costs/stage-N-*.md` |

## How to read this repository

- `FACTORY.md` is the factory: seats, how to stand it up, design choices and their cost, a bad
  result it caught, and what is not measured.
- `mandates/` holds one file per seat, named after the seat, each starting with its harness and model.
- `stage-1/` to `stage-4/` are the services the band built; each is a complete, buildable folder
  (see its `RUN.md`), and `stage-N/` is `stage-(N-1)/` carried forward and extended.
- `factory/` is what the seats wrote while working: plans, decision log (`decisions.md`),
  requirement ledgers, probes, reviews, cost audits and the stage reports in `run-log.md`.
- `RUN.md` stands the service up (mock web or your own Nimble key); `docs/model-spend.txt` is the model-spend sum with its method.
- `room.json` is the room downloaded from Band, unedited.
- `dossier-runway.com.json` is the `GET /dossiers/runway.com` response of the highest stage,
  built against the live web.
- `docs/ui/` holds screenshots of stage 4 taken after the run by `docs/ui/capture.py` (Docker + headless Chromium, no hand editing; not seat output); the stage folders are unchanged.
- `docs/model-spend/` holds the raw usage fields (`usage.jsonl`: seat, model, time, token counts per message; no text, paths or keys), `aggregate.py` that re-sums them to the figures below, and `test_aggregate.py` (`python3 -m unittest docs/model-spend/test_aggregate.py` reproduces 287,781,523 tokens and USD 93.53).
- Git history is the seats' own commits, not rewritten.

## The service on screen (375 px and 1280 px)

Captured by `python3 docs/ui/capture.py` from stage 4 built from this repository in Docker against the mock web (`docs/ui/`). The same four states at both widths.

| State | 375 px | 1280 px |
|---|---|---|
| Empty list | `docs/ui/375-1-empty.png` | `docs/ui/1280-1-empty.png` |
| Building | `docs/ui/375-2-building.png` | `docs/ui/1280-2-building.png` |
| Error (invalid domain) | `docs/ui/375-3-error.png` | `docs/ui/1280-3-error.png` |
| Ready, fields with sources | `docs/ui/375-4-ready.png` | `docs/ui/1280-4-ready.png` |
| Contested fields | `docs/ui/375-5-contested.png` | `docs/ui/1280-5-contested.png` |

Code size of stage 4 (excluding tests): 4,380 lines in all, the largest module is `dossier/support.py` with 440 lines.
Unit tests: 83, all passing (`docker run --rm dossier-s4 python -m unittest discover -s tests -t .`, 18 November 2026).

