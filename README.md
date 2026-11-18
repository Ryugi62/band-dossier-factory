# Dark factory entry: a four-seat band that built the Dossier track

Team: one person (Taegeol Kim) who configured the factory and dispatched each stage, plus four
Claude Code seats in one Band Desktop room. Track: `dossier`, stages 1 to 4.
The person wrote no code under `stage-N/`; each stage's only human input was one dispatch message.

## Run it in three minutes (mock web, no key)

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
key, run twice) is `ready` with all 8 fields `unknown` (value `null`): the search step spent 79 of the 80-unit per-build cap
and extraction was skipped (`FACTORY.md`, "What did not work"). All unit figures below are on the mock web's
sample providers. We did not edit the stage folder or the response file after the run.

## Model spend (measured from the seats' session logs)

Four Claude Code sessions, 750 assistant messages, 287,781,523 tokens in total, of which **1,069,632 are output
tokens**; 283,731,532 are cache reads. Priced at public list prices (Opus 5.5 $4 in / $20 out, Sonnet 5.5 $2 / $10,
cache read $0.20, 1-hour cache write 2x input) this is an estimated **$96.94**. Per seat in `FACTORY.md`; the
method and per-seat output are in `docs/model-spend.txt`. The session logs live on the
operator's machine and are not in this repository, so these figures cannot be re-run from the clone.
The demo video is the 18 November 07:20 version, recorded before this was measured, and says spend was not measured:
the video was not changed, and the cost figures in this repository are the source of truth.

## How this differs from similar work

| Similar work | What it is | What it does not have that this entry has |
|---|---|---|
| [Verifier Factory](https://hackersquad.io/events/band-dark-factory-buildathon-san-francisco) (first entry listed for this event) | Five seats: plan, research, verify, budget, record; its Budget Keeper holds one shared allowance. As of 18 November 2026 its listing says the submitted run paused on a provider account limit and "the staged build continues to the Nov 20 deadline" (still in progress) | Spend is audited per call: units per correct field are measured for every stage (5.591 to 9.377), and the cost auditor can reject a commit; the planner's mandate has a resume-and-blocker rule for provider limits (`mandates/planner.md`, lines 71 to 75) |
| [GeekForge](https://github.com/jacedeno/geekforge-dark-factory) (entry of the October edition of the same event, 3 seats) | Plan, build, verify; reports 89 minutes and 110 M tokens in total | Totals only, no cost per correct output; here a fourth seat prices every call from the call log |
| [Nimble web search agents](https://docs.nimbleway.com/nimble-sdk/web-search-agents/best-practices/evaluating-results.md) (the research vendor of this track) | One 25-unit research run per company; its guide grades results, it does not verify them | On the same sample companies one research run alone costs at least 30.0 units per field (24 runs, 600 units, 20 cited fields, counting every cited field as correct); this service costs 5.591 to 9.377 and a verifier checks every cited excerpt |
| [Onsen](https://hackersquad.io/events/band-dark-factory-buildathon-san-francisco) (second entry listed for this event, 18 November 2026) | Six agents; "The Examiner writes hidden acceptance scenarios from the spec and posts only their SHA-256"; a Scout answers factual questions from the live web with Nimble; a Nap Guard wakes the human once | Its listing names no cost seat and gives no spend figure; here a fourth seat prices every call and the model tokens are measured from the session logs (below). It has what this entry lacks: a sealed hidden exam and a live-web research agent |
| [Organizer sample mandate](https://github.com/band-ai/sf-buildathon-2026) | Toy seat instructions for the track | No cost seat and no ledger; this entry's mandates are domain-free and reused for all four stages |

Patents: KIPRIS (506 hits for a Korean query on agent cost audit and code-generation verification) and Google
Patents (1,336 hits for a multi-agent verifier and cost-audit query), 18 November 2026; no top-ranked hit
describes a per-call cost auditor seat for a code factory. This is a title-level look at the first results, not a
proof that none exists.

## The measure

**Units per correct field** = metered units charged in the mock web's call log over a fixed workload of 24 builds
(12 sample companies, 2 epochs), divided by the number of correct fields those builds returned. One unit is one
cost unit of the mock web's price table (search 1, 5 or 15, extract 1 per URL, research 25).
**Baseline:** one 25-unit research run per company and nothing else: 600 units for 20 cited fields = **30.0 units per field at best**
(8 of 24 runs return no field; every cited field is counted as correct, so the true baseline is not lower). Stage 1 to 4 here: 5.591, 8.935, 9.377, 8.210, which is at least 3.2 to 5.4 times cheaper per field than this baseline. The baseline is our own simple one, not the organizer's benchmark (its definition is not public). Stage 1 counts 6 fields per company; stages 3 and 4 count 8 (executives and investors added), so the four figures are not like for like.

## Result in numbers

| Measure | Value | Source |
|---|---|---|
| Stages claimed on the shipped checks | 1, 2, 3, 4 (highest contiguous 4) | verifier's isolated run of revision `7a3a10c1` (report.json outside this repository), summarised in `factory/run-log.md` |
| Shipped checks, isolated | 122/122, 12/12, 9/9, 10/10; leaks 0, fabrications 0 | `factory/run-log.md`, stage 4 report |
| Work time per stage | 1 h 19, 1 h 02, 1 h 00, 1 h 27 | `factory/run-log.md` |
| Review rounds | 2, 1, 1, 2 (one rejection, at stage 1) | `factory/reviews/` |
| Research spend per correct field (units) | 5.591, 8.935, 9.377, 8.210 | `factory/costs/stage-N-*.md` |

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
- `docs/ui/` holds screenshots of stage 4 taken by the person after the run (not seat output); the stage folders are unchanged.
- Git history is the seats' own commits, not rewritten.

## The service on screen (375 px and 1280 px)

Captured from stage 4 built from this repository in Docker against the mock web (`docs/ui/`). The same four states at both widths.

| State | 375 px | 1280 px |
|---|---|---|
| Empty list | `docs/ui/375-1-empty.png` | `docs/ui/1280-1-empty.png` |
| Building | `docs/ui/375-2-building.png` | `docs/ui/1280-2-building.png` |
| Error (invalid domain) | `docs/ui/375-3-error.png` | `docs/ui/1280-3-error.png` |
| Ready, fields with sources | `docs/ui/375-4-ready.png` | `docs/ui/1280-4-ready.png` |
| Contested fields | `docs/ui/375-5-contested.png` | `docs/ui/1280-5-contested.png` |

Code size of stage 4 (excluding tests): 4,380 lines in all, the largest module is `dossier/support.py` with 440 lines.
Unit tests: 83, all passing (`docker run --rm dossier-s4 python -m unittest discover -s tests -t .`, 18 November 2026).

