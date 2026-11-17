# Dark factory entry: a four-seat band that built the Dossier track

Team: one person (Taegeol Kim) who configured the factory and dispatched each stage, plus four
Claude Code seats in one Band Desktop room. Track: `dossier`, stages 1 to 4.
The person wrote no code under `stage-N/`; each stage's only human input was one dispatch message.

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
- Git history is the seats' own commits, not rewritten.
