# Verification — dossier stage 4 (last stage), round 2 (D47 rework)

- Commit checked: `7a3a10c148d085f9b25658d0c175e13a7ce450de`. The builder's new commits since round 1 (`97cc83a`) are `f7bc09f` (N1 support.py split) and `7a3a10c` (F1 batch admission per D47).
- Ledgers: `factory/ledger/stage-4.md` (111 rows, including TD-47) with stages 1–3 binding.
- Probes run from `factory/` at `acd3028`, which adds E04 for D47.
- **Decision: ACCEPT.**

## 1. Fresh clone, clean build

- Cloned into the new directory `scratch/verifier/s4r2-clone` and checked out `7a3a10c`.
- D35 holds: `git diff` against `9166a28 -- stage-1`, `3e32ac8 -- stage-2` and `0c9722c -- stage-3` is empty in each case.
- The builder changed nothing under `factory/`; the factory commits in the range are planner, cost-auditor and verifier.
- `stage-4/` built from its Dockerfile.
- The service ran on an `--internal` docker network (no outbound access), with `--cpus 2 --memory 3g` and no volume.
- The closed stage-1, stage-2 and stage-3 services ran beside it to produce real exports for the upgrade probes.

## 2. Checks (all on the clone)

| Check | Command | Result |
|---|---|---|
| Unit tests | `cd stage-4 && python -m unittest discover -s tests -t .` | 83 run, OK (2 skipped) |
| Verifier API probes | `factory/probes/stage-4/run_all.sh <clone>` → `run4.py --phase main` | **45 passed, 0 failed** (including E04 for D47; SERVED checked 216 excerpts) |
| Verifier restart probes | the same run: idle `docker kill`/`start`, then a batch killed mid-build | **4/4 phases pass** |
| Verifier browser probes | the same run → `browser4.py` | **15 passed, 0 failed** (B02..B14, U02, G-UI) |
| Shipped checks, isolated | `python -m harness run --track dossier --repo <clone> --stage 4 --mode isolated --out checks/verifier-s4-r2-7a3a10c` | stage 1 **122/122**, stage 2 **12/12**, stage 3 **9/9**, stage 4 **10/10**; leaks 0, fabrications 0; highest contiguous stage 4; claimed stage 4 |

The service logs contain no tracebacks.

The killed batch in the restart probes has budget 120 over 3 domains, which does not cover every build. Under the new admission rule, one build ran and two were queued when the container was killed. After the restart:

- all three dossiers and the batch were settled within 10 s of health;
- billed ≤ spent ≤ budget;
- each dossier spent ≤ 80;
- a refresh started a new build.

So the queued-build path of D43 is covered too.

## 3. Reading (diff `97cc83a..7a3a10c`)

- **N1:** `roles.py` is a pure move. The lines removed from `support.py` and the lines in `roles.py` match exactly, apart from the new module docstring and imports. Three callers switched imports. `support.py` is now 440 lines and the largest file is `support.py`; `service.py` is 398.
- **F1 / D47, budget covers every build** (`budget ≥ 80 × new builds`): all builds start at once as before. E04 timed 3 builds at budget 1000 and they finished within 10.5 s of the batch request.
- **F1 / D47, budget cannot cover every build:** new dossiers are created `building` and queued in the order of `domains`. `Service.admit_batch_builds` then decides, as follows:
  - **While other builds of the batch run:** it starts the next build only when the budget not yet spent and not needed by those builds covers a whole build. A build's need is its 80-unit cap minus what it has spent; a build whose meter is not registered yet counts as 80.
  - **When none runs:** it starts the next build when the budget covers the research run plus the domain search (26 units). These are the pipeline's first calls, so the threshold is consistent with it.
  - **Otherwise:** the remaining builds complete `ready` with nothing (D41). Each records a ready build with no candidates, at the batch request time.
  - **After every finished build:** admission runs again.

  E04 confirms this on the mock:
  - budget 300 over 8 domains and budget 75 over 3: mock log total ≤ budget and equal to the batch's `spent_units`;
  - every build ≤ 80;
  - the first domain reaches known fields;
  - the domains with known fields form a prefix of `domains`.
- **Unchanged:** the atomic reservation against both the 80-unit cap and the batch budget, and the call set.
- **Queued dossiers:**
  - they are `building`, so a refresh starts nothing (D41);
  - the batch stays `running` while any are queued;
  - the build time stays the batch request time;
  - `queued` is persisted (cleared in a settled export) and closed at start-up like a running build (D43), with 0 spending.
- **Reset:** a reset during admission stops it (generation check).
- No corpus or fixture names appear in `dossier/`.

## Blocking findings

None.

## Non-blocking notes

1. Under a budget that cannot cover every build, a queued build starts only after earlier builds hand back budget. Its batch can therefore finish more than 10 s after the request even when every call answers within a second. D47 states the §8 bound for the covered case only, and the build time stays the batch request time. This is recorded for information only.
