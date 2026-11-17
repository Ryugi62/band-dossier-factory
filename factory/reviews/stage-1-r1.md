# Verification — dossier stage 1, round 1

- Commit checked: `f72df407766174680d78a792ea83081f7ba24041` (builder W1..W7, `a3f0b42..f72df40`).
- Ledger: `factory/ledger/stage-1.md` @ `6c1e2e5`. Blind re-derivation: `factory/reviews/stage-1-blind.md` (committed with the ledger).
- **Decision: REJECT.** There is one blocking finding, from reading the code. Every check and probe passed.

## 1. Fresh clone, clean build

```sh
git clone /Users/ryugi62/band-work/result-s1 scratch/verifier/r1-clone
git -C scratch/verifier/r1-clone checkout f72df407766174680d78a792ea83081f7ba24041
```

- `docker build` of `stage-1/` (the RUN.md command) succeeded.
- The service ran from `factory/probes/stage-1/run_all.sh` on a `docker network create --internal` network (no outbound access), with `--cpus 2 --memory 3g`. It was given only `PORT` and the `NIMBLE_*`/`TAVILY_*` variables.
- It started: `/health` answered 200 within 3 s.
- The builder's commits touch only `stage-1/`; `factory/` is unchanged since `6c1e2e5`.

## 2. Checks (all on the clone)

| Check | Command | Result |
|---|---|---|
| Unit tests | `cd stage-1 && python -m unittest discover -s tests -t .` (Python 3.12) | 33 run, 33 OK |
| Verifier probes | `factory/probes/stage-1/run_all.sh scratch/verifier/r1-clone` | **20 passed, 0 failed** (P00–P15, P17, P18, SERVED with 92 citations, G); no notes |
| Shipped checks, stage 1, isolated | `python -m harness run --track dossier --repo scratch/verifier/r1-clone --stage 1 --mode isolated --out checks/verifier-s1-r1-f72df40` | stage 1: **pass, 122/122**, fabrications 0, leaks 0; stage 2: fail (expected); highest contiguous stage 1; claimed stage 1 |

The service log contains no tracebacks. Its error lines all come from faults the probes injected on purpose.

## 3. Reading

I read `pipeline.py`, `provider.py`, `service.py`, `store.py`, `exchange.py`, `http_app.py`, `pages.py`, `clock.py`, `domains.py` and `accounts.py`, and spot-checked `support.py` against the oracle with 22 extra edge cases.

What the reading confirmed:

- **No special-casing.** There is no fixture data, corpus domain, check name or mock admin route anywhere in `dossier/`.
- **One provider route.** The only network client is `web_router.AsyncWebRouter` with `provider="nimble"` (R2-08..R2-12). The manifest lists `webrouter[search,extract,research]>=0.12.0`, and the Dockerfile installs it.
- **No write races.**
  - Every store mutation runs on the event loop with no `await` between check and set.
  - Signup re-checks the email after hashing.
  - The idempotency claim and the operation happen in the same synchronous call.
- **Reset and import cannot be overwritten by an old build.** Each bumps `generation` and cancels running builds; a build writes nothing, not even spending, unless it is still current (R3-13).
- **No state is dropped on export.** The export holds users with their password hashes, tokens, dossiers (settled state and spending while a build runs), and idempotent requests and responses (R10-11..R10-19, R10-27).
- **Password storage:** scrypt, n=2^14 (R6-13).
- **Port:** defaults to 8080 (R3-02).
- **Provider timeouts:** 45 s per call, 60 s to start a research run (R8-10).
- **Spending:** a lost call (timeout or connection failure) is charged whatever the build's outcome (R8-44, R9-13).
- **Size and structure:** files are 21–435 lines and the modules are cohesive.

## Blocking findings

### F1 — R8-12: a build against the live provider can run past 300 s

- **Requirement (§8 Builds):** "Against the live providers (`NIMBLE_BASE_URL` unset, or its host `sdk.nimbleway.com`) … a build does not give up on a call that has been waiting less than 30 seconds, nor stop gathering because of the time it has run in its first 120 seconds. **It still ends `ready` or `failed` within 300 seconds.**"
- **Observed (`stage-1/dossier/pipeline.py` `run_build`, `stage-1/dossier/provider.py`):** the build has no overall deadline, and its phases run one after another:
  1. `claims = await research` waits for `submit_research` (bounded only by `RESEARCH_START_TIMEOUT = 60`) and then `job.aresult(timeout=RESEARCH_RESULT_TIMEOUT = 200)`. That is up to 260 s.
  2. Only afterwards does `_extract_needed` run, with extracts bounded by `CALL_TIMEOUT = 45`. On the live endpoint every page needs an extract, because snippets are not treated as prose there. A refused extract is also retried up to 3 more times, with `RETRY_GAP = 1.1` s between attempts.
- **Worst case:** 60 + 200 + 45 s ≈ **305 s**, and ≈ 308 s with refusals, before the build can end `ready` or `failed`.
- **Reproduction (by reading; the live branch is not reachable offline):**
  1. With `NIMBLE_BASE_URL` unset, suppose the research run is accepted after about 60 s and its result never arrives, so `aresult` times out at 200 s.
  2. At t ≈ 260 s, `_extract_needed` starts extracts for every relevant page.
  3. One extract that takes 45 s keeps the build `building` until t ≈ 305 s.
- **What a fix needs to do:** bound the whole build by a deadline below 300 s while respecting the 30 s and 120 s floors. For example, stop starting new calls after about 240 s, or shorten the research result wait so that start + result + extract + retries stays under 300 s.

## Non-blocking notes

1. **The live path is not tested offline.** When `NIMBLE_BASE_URL` points at the mock, lite snippets are treated as the first 300 characters of prose (taken from the mock README), so complete snippets are never extracted. The live path (extract every relevant page, plus per-field searches) is not covered by any offline check, including my probes.
2. **Evidence beyond the domain search.** Extra searches are made only when the domain search returns 10 results or fails. I confirmed that the mock returns every page of the company for a domain query, including pages whose text lacks the domain, so this is complete for a company's own pages. Pages of other companies that name the company are only reached when the domain search is full.
3. **An unclear amount format:** `Acme Robotics raised USD12m.` The service finds no amount here; my oracle finds 12000000. The amount form ("USD, an optional space, a number") conflicts with the number rule ("digits directly next to a letter … are not a number"). This is ambiguous in the spec, not a finding.
4. **The 10 s bound under refusals.** Each refused call is retried up to 3 times, 1.1 s apart, and the search, research and extract phases run one after another. If several phases each get three refusals in a row, the 10 s bound (R8-09) could be approached. P18 (throttled search) finished in about 6 s.

## Earlier folders

None: stage 1 is the first stage.
