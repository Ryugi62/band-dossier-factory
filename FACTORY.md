# FACTORY.md

A software factory of four Claude Code seats in one Band Desktop room. A planner splits and
routes the work, a builder writes the code, a verifier and a cost auditor check it independently.
The mandates in `mandates/` say nothing about the problem being solved; the task and the
specification come in the human's dispatch message and are pasted in full by the planner into
every handoff.

## Seats

| Seat | Harness / model | Owns | Never does |
|---|---|---|---|
| planner | Claude Code, claude-sonnet-5-5 | dispatch, sequencing, decisions log (`factory/decisions.md`), stage reports | writes product code, accepts work itself |
| builder | Claude Code, claude-opus-5-5 | product code, build file, run instructions, unit tests; one commit per work item, inside the stage folder only | edits other seats' files, writes outside its stage folder |
| verifier | Claude Code, claude-opus-5-5 | requirement ledger written from the specification only, blind re-derivation, fresh-clone no-network verification, accept or reject on correctness | edits product code |
| cost-auditor | Claude Code, claude-sonnet-5-5 | metered-call accounting per correct output item, accept or reject on spend | edits product code |

Accepting a stage needs both the verifier and the cost auditor. Mandate files give each seat's
harness and model on the first lines; `Effort:` is not set in any mandate.

## Stand it up

1. Install Band Desktop and sign in; start the local Band daemon. Install Docker (the run used
   colima on Apple silicon: 4 CPU, 6 GiB, 40 GB disk, `--vm-type vz`).
2. Create four headless Claude Code seats named `planner`, `builder`, `verifier`, `cost-auditor`
   (`band agent create --transport claude-code-cli --runtime-model <model> --instructions-file mandates/<seat>.md ...`,
   each with its own working directory), then add all four to one room.
3. Create an empty result repository (branch `main`), commit `mandates/`, and place a read-only
   checkout of the event kickoff package next to it.
4. Send one message per stage, addressed `@planner`: the track and stage, the path of that stage's
   specification, the rules document, the result repository, the stage folder to build, the
   command that runs the shipped checks, and the rule that this message is the only human input.
   Send the next stage only after the planner's close commit for the previous one.
5. Do not message the room in between. A stage ends with a `planner: stage-N close` commit and
   a stage report appended to `factory/run-log.md`.

## Design choices and what they cost

- **Four seats, split by authority, not by file.** Writing, checking correctness and checking spend
  are three different seats, so a builder cannot accept its own work. Cost: handoffs take time
  (each stage waits for a verification that runs a clean build and a no-network container).
- **Ledger before code.** The verifier writes a requirement ledger from the specification while the
  builder works, then re-derives the normative statements blind (`factory/reviews/stage-N-blind.md`)
  and adds what the ledger missed. The reviewer owns the question "what do the shipped checks never
  ask". Cost: stage 1 produced 311 ledger rows before acceptance.
- **Spend is a pass/fail criterion.** The cost auditor repeats a fixed workload of 24 builds and
  rejects on cost per correct item that rises more than 10% without a requirement that forces it.
  Cost: one more full run per round.
- **Copy forward, never edit back.** Each stage folder is a copy of the accepted previous one,
  extended; earlier folders must stay byte-identical (`git diff <accepted> -- stage-N` empty,
  checked in every stage report). Cost: duplicated source across folders.
- **Decisions are written down by the planner** (`factory/decisions.md`, D1 to D48) instead of asked
  of the human, as the dark-factory rule needs.
- **Silence rule.** The planner does not nudge or steer seats after a handoff except to relay a
  seat's own finding to another seat.

## Measured time and spend

Times are from the stage reports in `factory/run-log.md` (UTC, 2026-11-17).

| Stage | Start | End | Elapsed | Review rounds | Units per correct item |
|---|---|---|---|---|---|
| 1 | 04:58 | 06:17 | 1 h 19 | 2 | 5.591 |
| 2 | 07:01 | 08:03 | 1 h 02 | 1 | 8.935 |
| 3 | 08:03 | 09:03 | 1 h 00 | 1 | 9.377 |
| 4 | 09:03 | 10:30 | 1 h 27 | 2 | 8.210 |

Stage 1 to 2 has a gap of 44 minutes: the local container VM had stopped after the host
restarted and had to be started again before the stage-2 dispatch. Work time summed over the
stages is about 4 h 48 min; wall clock from first dispatch to the stage-4 close is about 5 h 32 min.
"Units" are the mock web's metered cost units (research, search, render, plain fetch); the
largest single build used 34, 59, 76 and 77 of the 80-unit cap in stages 1 to 4.
**Model spend in money or tokens was not captured by the factory**; the room log holds every
seat's calls but no price, so no figure is claimed here.

## How the factory catches bad work

- **Stage 1, round 1: REJECT of `f72df40`** by the verifier: a build could run past 300 s against
  slow live providers (ledger rows R8-12). The cost auditor had accepted the same commit, so spend
  review alone would have shipped it. The builder answered with `46680d2` and `9166a28` (whole-build
  deadline, per-call end-by-290 s, a bound under refusals, unit tests); round 2 accepted.
- **Stage 4, round 1 accepted but reopened.** After `97cc83a` was accepted, the cost auditor's
  non-blocking finding F1 (a batch whose budget could not cover every build spent it on the first
  phases of all builds and learned nothing: 8-12 domains with budget 300 gave 0 known fields) and the
  verifier's note on a 505-line file made the planner open a rework round (D47). After `7a3a10c` the same
  batches give 35 known fields; both seats accepted again.
- **Seat-to-seat corrections** without the human: for example the verifier fixing a probe after the
  builder's message about route handlers (stage 2) and a ledger question answered by decision D33
  while the builder was working (stage 3).
- **Recovery rule.** A rejected commit returns to the builder with the ledger ID, the quoted
  requirement, the observed behaviour and a reproduction; every new commit is rechecked from the
  fresh-clone step.

## What did not work or was left out

- The first stage-4 acceptance was premature relative to its own cost finding, and the rework round fixed it
  at the price of a second review round (stage 4 took 1 h 27 min against about 1 h for stages 2 and 3).
- The margin to the per-build cap is thin on one company (77 of 80 units at stage 4).
- Not measured: money or token spend, seat idle time, and any live-web accuracy beyond the single
  `dossier-runway.com.json` build.
- The live build of `runway.com` (stage-4, own Nimble trial key, run twice with the same outcome) finished
  `ready` with every field `unknown`. The build log shows the search step spending the whole per-build cap
  (80 and 79 units), so the extraction step was skipped with "build cap"; live Nimble calls also returned 403
  and took up to about 45 s, and results mixed in other companies named "Runway". The sample providers never
  showed this because they answer fast and unambiguously. We left the stage folder as the factory delivered it
  and did not edit the response file; the gap is the factory's budget split under live latency.

## Reuse

To use the factory on another problem, keep `mandates/` and change only the dispatch message and the
specification path. The `factory/` folder shows the artifacts to expect per stage: plan, ledger,
probes, blind re-derivation, review, cost audit, decisions and a stage report.
