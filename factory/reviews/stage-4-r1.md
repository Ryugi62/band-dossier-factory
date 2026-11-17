# Verification — dossier stage 4 (last stage), round 1

- Commit checked: `97cc83ad042382c1c48b17d88fa22bf7cfc9ec2b`. The builder's commits are U0 `48866f9` through U8 `97cc83a`.
- Ledgers: `factory/ledger/stage-4.md` (110 rows) with stages 1–3 binding.
- Probes run from `factory/` at `e473fe8`: the stage-4 probes with the builder-reported fixes `fb51977` and `e473fe8`.
- **Decision: ACCEPT.**

## 1. Fresh clone, clean build

- Cloned into the new directory `scratch/verifier/s4r1-clone` and checked out `97cc83a`.
- D35 holds: `git diff` against `9166a28 -- stage-1`, `3e32ac8 -- stage-2` and `0c9722c -- stage-3` is empty in each case.
- The builder changed nothing under `factory/`; the only factory commits in the range are mine.
- `stage-4/` built from its Dockerfile; the webrouter install line is unchanged.
- The service ran on an `--internal` docker network (no outbound access), with `--cpus 2 --memory 3g` and no volume.
- The closed stage-1, stage-2 and stage-3 services ran beside it to produce real exports for the upgrade probes.

## 2. Checks (all on the clone)

| Check | Command | Result |
|---|---|---|
| Unit tests | `cd stage-4 && python -m unittest discover -s tests -t .` | 80 run, OK (2 skipped) |
| Verifier API probes | `factory/probes/stage-4/run_all.sh <clone>` → `run4.py main` | **44 passed, 0 failed** (S1-P00..P18, S2-A01..A08, S2-U01, S3-C01..C05, S3-U3, S3-U4, D01..D03, E01..E03, F01, U5, X1, SERVED with 216 excerpts, G) |
| Verifier restart probes | the same run: idle `docker kill`/`start` (stage-3 guarantees); a batch of three builds killed mid-build | **4/4 phases pass** |
| Verifier browser probes | the same run → `browser4.py` | **15 passed, 0 failed** (B02..B14, U02, G-UI) |
| Shipped checks, isolated | `python -m harness run --track dossier --repo <clone> --stage 4 --mode isolated --out checks/verifier-s4-r1-97cc83a` | stage 1 **122/122**, stage 2 **12/12**, stage 3 **9/9**, stage 4 **10/10**; leaks 0, fabrications 0; highest contiguous stage 4; claimed stage 4 |

The service log has no tracebacks.

## 3. Reading

- **Provider access** is unchanged.
- **No special-casing:** there are no corpus or fixture names in `dossier/`.
- **`lineage.py`** (pure) matches the rules:
  - registrant: valid normalised Registrant, else the URL host;
  - the own-page rule and lookalikes;
  - `resolve_origin` with at most three Canonical hops from the page whose origin is sought;
  - a fourth hop, an unreachable original or a cycle takes the host of that URL;
  - Canonical comparison is trimmed, with scheme and host lower-cased and the fragment ignored (D36, D37).
- **Originals** are fetched once per build, and the call log shows unreachable originals being requested (D01).
- **Corroboration** comes from the build log, per value or per member, since it last became selected (D38). The D03 timeline confirms the standing-origin semantics.
- **Investors** follow D39. My oracle and the service agree on every sentence (the builder also cross-checked all 800 corpus sentences).
- **Batches:**
  - one atomic reservation against both the 80-unit cap and the batch budget (D41);
  - E02 confirms the mock log total never exceeds the budget and equals the batch's spent_units.
- **Restarts:**
  - reservations are written durably before each call (D43);
  - at start-up, before `/health`, dossiers stored as building are closed `failed`, with in-flight reservations counted;
  - R-post-kill confirms billed ≤ spent ≤ budget and that the batch is `done` within the bound.
- **Upgrades** from four export shapes follow D44.
- **UI:** investors appear in separate markup, with an origins and corroboration line on every field card (D45). The orbit-forge screenshot is consistent with the visual system of the earlier stages.
- **File size:** `support.py` is 505 lines (Appendix A plus the executives and investors variants), just over the ~500-line guideline; the rest are under 350.

## Blocking findings

None.

## Non-blocking notes

1. **`support.py` size.** At 505 lines it could split its executives and investors variants into their own module for maintainability. This is cosmetic.
