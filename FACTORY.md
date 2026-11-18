# FACTORY.md

A software factory of four Claude Code seats in one Band Desktop room. A planner splits and
routes the work, a builder writes the code, a verifier and a cost auditor check it independently.
The mandates in `mandates/` say nothing about the problem being solved; the task and the
specification come in the human's dispatch message and are pasted in full by the planner into
every handoff.

## How this differs from similar work (same table as the README)

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

## The measure (same definition as the README and the deck)

**Units per correct field** = metered units charged in the mock web's call log over a fixed workload of 24 builds
(12 sample companies, 2 epochs), divided by the number of correct fields those builds returned. One unit is one
cost unit of the mock web's price table (search 1, 5 or 15, extract 1 per URL, research 25).
**Baseline:** one 25-unit research run per company and nothing else: 600 units for 20 cited fields = **30.0 units per field at best**
(8 of 24 runs return no field; every cited field is counted as correct, so the true baseline is not lower). Stage 1 to 4 here: 5.591, 8.935, 9.377, 8.210, which is at least 3.2 to 5.4 times cheaper per field than this baseline. The baseline is our own simple one, not the organizer's benchmark (its definition is not public). Stage 1 counts 6 fields per company; stages 3 and 4 count 8 (executives and investors added), so the four figures are not like for like.

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
"Units" (all figures in this table are on the sample providers of the local mock web, not the live web) are the mock web's metered cost units (research, search, render, plain fetch); the
largest single build used 34, 59, 76 and 77 of the 80-unit cap in stages 1 to 4.
Model spend was not captured by the factory itself while it ran, but each seat is a Claude Code session whose log
records the usage of every assistant message. Summing those logs afterwards (de-duplicated by message id;
method and output in `docs/model-spend.txt`, re-runnable from `docs/model-spend/usage.jsonl` with `aggregate.py`) gives, for the four seats:

| Seat | Model | Messages | Input | Output | Cache write | Cache read | Total tokens | Est. USD |
|---|---|---|---|---|---|---|---|---|
| builder | claude-opus-5-5 | 301 | 644 | 377,923 | 1,161,129 | 142,456,094 | 143,995,790 | 45.34 |
| verifier | claude-opus-5-5 | 249 | 570 | 489,504 | 1,063,757 | 107,175,017 | 108,728,848 | 39.74 |
| cost-auditor | claude-sonnet-5-5 | 82 | 186 | 100,799 | 485,233 | 15,847,924 | 16,434,142 | 6.12 |
| planner | claude-sonnet-5-5 | 118 | 252 | 101,406 | 268,588 | 18,252,497 | 18,622,743 | 5.74 |
| **all four** | | 750 | 1,652 | **1,069,632** | 2,978,707 | 283,731,532 | **287,781,523** | **96.94** |

Read the total with care: almost all of it (283,731,532 tokens) is cache reads, which the model re-reads on every turn; the output
the seats wrote is 1,069,632 tokens. Dollars are an estimate at public list prices (Opus 5.5 $4 per million input and
$20 output, Sonnet 5.5 $2 and $10, cache read $0.20, every cache write was the 1-hour kind at 2x input). They are not a
bill: what was actually charged depends on the operator's Claude plan, and an unofficial sum of logs can double-count a retried turn.
The session logs are on the operator's machine, not in this repository, so the method header and the
output in that file are the record. What the room log itself measures (`room.json`, 2,366 entries, 04:57 to 10:29 UTC):

| Seat | Tool calls | Messages to the room | Room-visible characters | Share of characters |
|---|---|---|---|---|
| builder | 352 | 127 | 1,637,282 | 52.2% |
| planner | 130 | 81 | 758,959 | 24.2% |
| verifier | 334 | 16 | 530,385 | 16.9% |
| cost-auditor | 118 | 6 | 201,448 | 6.4% |
| human | 0 | 4 (the four stage dispatches) | 8,866 | 0.3% |

The 3.14 million room-visible characters are only what the seats echoed to the room; the session logs above hold the full
token counts. The four human messages are the stage dispatches at `room.json` `messages[4]`, `[748]`, `[1216]` and `[1652]`;
nothing else from the human reaches the room. (Commit `4bcdaa0` replaced local paths in the `factory/` notes with placeholders and `ebe9a6d` restored the seats' original
text, so `factory/` is what the seats wrote; both are in the history, which was not rewritten.)

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
- Not measured: a billed amount (the dollar figure above is a list-price estimate), seat idle time, and any live-web accuracy beyond the single
  `dossier-runway.com.json` build.
- The live build of `runway.com` (stage-4, own Nimble trial key, run twice with the same outcome) finished
  `ready` with every field `unknown`. The build log shows the search step spending the whole per-build cap
  (80 and 79 units), so the extraction step was skipped with "build cap"; live Nimble calls also returned 403
  and took up to about 45 s, and results mixed in other companies named "Runway". The sample providers never
  showed this because they answer fast and unambiguously. We left the stage folder as the factory delivered it
  and did not edit the response file; the gap is the factory's budget split under live latency.

## Reuse

To use the factory on another problem, keep `mandates/` and change only the dispatch message and the
specification path. The mandates name no domain, file layout or language; every problem-specific
fact reaches the seats through the dispatch. A dispatch for a different problem has the same shape
as the four used here, for example:

```
@planner Build stage 1 of the track below as a dark-factory run. Do the whole stage with
@builder, @verifier and @cost-auditor. Track: invoice-parser. Specification: specs/stage-1.md.
Rules: docs/rules.md. Result repository: ~/work/invoice-result (branch main). Build only in
stage-1/. Shipped checks: `make check STAGE=1`. This message is the only human input for the stage.
```

The cost auditor's workload is defined by the task or by the verifier's ledger, not by its mandate
(`mandates/cost-auditor.md`, step 2), so nothing in `mandates/` changes. If the new problem has no
metered cost, the dispatch names what to meter instead (calls, time or bytes). The `factory/` folder shows the artifacts to expect per stage: plan, ledger,
probes, blind re-derivation, review, cost audit, decisions and a stage report.
