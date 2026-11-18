# Dark factory entry: a four-seat band that built the Dossier track

Team: one person (Taegeol Kim) who configured the factory and dispatched each stage, plus four
Claude Code seats in one Band Desktop room. Track: `dossier`, stages 1 to 4.
The person wrote no code under `stage-N/`; each stage's only human input was one dispatch message.

## How this differs from similar work

| Similar work | What it is | What it does not have that this entry has |
|---|---|---|
| [Verifier Factory](https://hackersquad.io/events/band-dark-factory-buildathon-san-francisco) (first entry listed for this event) | Five seats: plan, research, verify, budget, record; its submitted run stopped at a model-provider limit | Spend is audited per call: units per correct field are measured for every stage (5.591 to 9.377), and the cost auditor can reject a commit; the planner's mandate has a resume-and-blocker rule for provider limits (`mandates/planner.md`, lines 71 to 75) |
| [GeekForge](https://github.com/jacedeno/geekforge-dark-factory) (entry of the October edition of the same event, 3 seats) | Plan, build, verify; reports 89 minutes and 110 M tokens in total | Totals only, no cost per correct output; here a fourth seat prices every call from the call log |
| [Nimble web search agents](https://docs.nimbleway.com/nimble-sdk/web-search-agents/best-practices/evaluating-results.md) (the research vendor of this track) | One 25-unit research run per company; its guide grades results, it does not verify them | On the same sample companies one research run alone costs at least 30.0 units per field (24 runs, 600 units, 20 cited fields, counting every cited field as correct); this service costs 5.591 to 9.377 and a verifier checks every cited excerpt |
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
(8 of 24 runs return no field; every cited field is counted as correct, so the true baseline is not lower). Stage 1 to 4 here: 5.591, 8.935, 9.377, 8.210, which is at least 3.2 to 5.4 times cheaper per field.

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

