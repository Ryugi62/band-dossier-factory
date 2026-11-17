# Verification — dossier stage 1, round 2

- Commit checked: `9166a2805e9c6481c7225b4eafc53f2758d464a8`. The rework since round 1 (`f72df40`) is `46680d2` and `9166a28`.
- Ledger: `factory/ledger/stage-1.md` (311 rows; RD-09 added for D9).
- **Decision: ACCEPT.**

## 1. Fresh clone, clean build

- Cloned into the new directory `scratch/verifier/r2-clone` and checked out `9166a28`.
- `stage-1/` built from its Dockerfile.
- The service ran from `factory/probes/stage-1/run_all.sh` on a `docker network create --internal` network (no outbound access), with `--cpus 2 --memory 3g`. It was given only `PORT` and the `NIMBLE_*`/`TAVILY_*` variables. `/health` answered 200 within 3 s.
- Since round 1 the builder changed only `stage-1/`. The probes in the clone are byte-identical to `6c1e2e5`.

## 2. Checks (all on the clone)

| Check | Command | Result |
|---|---|---|
| Unit tests | `cd stage-1 && python -m unittest discover -s tests -t .` | 42 run, 42 OK |
| Verifier probes | `factory/probes/stage-1/run_all.sh scratch/verifier/r2-clone` | **20 passed, 0 failed** (P00–P15, P17, P18, SERVED with 92 citations, G); no notes |
| Shipped checks, stage 1, isolated | `python -m harness run --track dossier --repo scratch/verifier/r2-clone --stage 1 --mode isolated --out checks/verifier-s1-r2-9166a28` | stage 1: **pass, 122/122** (auth 51/51, dossiers 60/60, sample 11/11), fabrications 0, leaks 0; stage 2: fail (expected); highest contiguous stage 1; claimed stage 1 |

The service log contains no tracebacks and no hard-limit or crash entries.

## 3. Reading of the rework

### Round 1 F1 (R8-12, the 300 s bound against live providers): fixed

`provider.Deadline` measures time from the start of the build (`46680d2`).

- **Calls end by 290 s.** No call starts unless its own timeout ends by `BUILD_DEADLINE = 290` s. A refused call is retried only if the retry can also end by then.
- **The research wait leaves room for one last round of calls.** It is `min(200, 290 − 50 − elapsed)`, and `aresult` is additionally wrapped in `asyncio.wait_for(wait + 1)`.
- **Worst case:** research is accepted at 60 s and then waits up to 180 s, ending at 240 s. A final round of 45 s extracts follows and ends by 285–290 s.
- **Backstop:** `service.BUILD_HARD_LIMIT = 298` s ends the build `failed` if anything still overruns.

The two floors in the same requirement still hold:

- **R8-10:** every call keeps a timeout of at least 45 s, which is over the 30 s floor.
- **R8-11:** no call is skipped for time before 245 s, which is over the 120 s floor.

### Round 1 note 4 (R8-09 under refusals): addressed

Off the live endpoint, a refused call is retried only while the retry can still answer within 7 s of the build's start. The new unit test models consecutive refusals in every phase and ends at about 8.2 s. P18 (throttled search) still produces exactly one successful domain search.

### Round 1 note 1 (live path): addressed

- When deciding which pages to extract, the relevance check now also reads the search snippet.
- On the live branch, snippets are never used as evidence.
- New unit tests cover the live branch.

### Nothing else changed

No other logic changed. My round 1 reading of the rest of the code (no special-casing, web_router as the only provider route, no write races, state kept on export) still applies.

## Blocking findings

None.

## Non-blocking notes

1. **The hard limit's outcome.** `BUILD_HARD_LIMIT` marks a build `failed` even when some of its calls succeeded. R8-06 reserves `failed` for builds in which no provider call succeeded. With the per-call deadline in place this backstop should never fire; I mention it only for completeness.
2. **A concern for later stages.** Off the live endpoint, refused calls are no longer retried after about 4.9 s into a build. In stage 1 this is harmless: the shipped checks and P18 pass. Under stage-2 rate limits, a call refused late in a build would not be retried, and the builder should revisit this rule then.

## Earlier folders

None: stage 1 is the first stage.
