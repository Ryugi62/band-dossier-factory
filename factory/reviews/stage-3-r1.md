# Verification — dossier stage 3, round 1

- Commit checked: `0c9722c422e0c0ac67b95d50117cb46b0eb56cf2`. The builder's commits are T0 `a30cb6e` through T7 `0c9722c`.
- Ledgers: `factory/ledger/stage-3.md` (123 rows, including TD-33), with stage-1 and stage-2 binding.
- Probes run from `factory/` at `758c049`: stage-3 probes with my C01 fixes and the D33 reading.
- **Decision: ACCEPT.**

## 1. Fresh clone, clean build

- Cloned into the new directory `scratch/verifier/s3r1-clone` and checked out `0c9722c`.
- D24 holds: `git diff 9166a28 -- stage-1` and `git diff 3e32ac8 -- stage-2` are both empty.
- `stage-3/` built from its Dockerfile; the webrouter install line is unchanged and no volume is declared.
- The service ran on an `--internal` docker network (no outbound access), with `--cpus 2 --memory 3g` and no volume.
- The closed stage-1 and stage-2 services ran beside it to produce real exports for the upgrade probes.

## 2. Checks (all on the clone)

| Check | Command | Result |
|---|---|---|
| Unit tests | `cd stage-3 && python -m unittest discover -s tests -t .` | 72 run, OK (2 skipped) |
| Verifier API probes | `factory/probes/stage-3/run_all.sh <clone>` → `run3.py main` | **35 passed, 0 failed** (S1-P00..P18, S2-A01..A08, S2-U01, C01..C05, U3, U4, SERVED with 170 excerpts, G) |
| Verifier restart probes | the same run: pre-restart → `docker kill`/`start` → post-restart; pre-kill (build running) → `docker kill`/`start` → post-kill | **4/4 phases pass**, plus G |
| Verifier browser probes | the same run → `browser3.py` | **14 passed, 0 failed** (B02..B13, U02, G-UI) |
| Shipped checks, isolated | `python -m harness run --track dossier --repo <clone> --stage 3 --mode isolated --out checks/verifier-s3-r1-0c9722c` | stage 1 **122/122**, stage 2 **12/12**, stage 3 **9/9**; leaks 0, fabrications 0; stage 4: fail (expected); highest contiguous stage 3; claimed stage 3 |

The service log has no tracebacks.

## 3. Reading

- **Provider access** is unchanged: web_router's nimble provider, with render through `provider_options`.
- **No special-casing:** there are no corpus or fixture names in `dossier/`.
- **`timeline.py`** holds pure functions:
  - history and feed entries, with executives typed by title;
  - the snapshot for `as_of`: the last ready build at or before the given instant, last in build order;
  - spending up to an `as_of`;
  - page versions with the replacement and end rules. Null-dated versions hold on no date (D33). A dated version that follows a null-dated one can only end the null-dated one, because a null-dated version clears every earlier version of its URL; so D33's "never stops another version" holds automatically.
- **Durable state (`persistence.py`):**
  - SQLite in WAL mode with `synchronous=FULL` at `/var/lib/dossier/state.db` on the container filesystem.
  - Each write is committed before its response.
  - At start-up, a dossier left building is restored to its last completed state, with its spending kept.
  - The clock is persisted frozen (D27).
- **Upgrades:**
  - Stage-1 and stage-2 exports become one ready build per dossier, as D25 describes.
  - Stage-3 exports restore builds, history, feed and the next seq (D26, D28).
- **Executives:**
  - Each title is an Appendix A field; candidates come only from rendered text (D31).
  - The UI shows executives in separate markup, and `/contested` considers the six fields only (D30).
  - In the screenshot of lumen-atlas.test the executives panel sits below the six field cards. It shows status, members, "holds from" and "learned" dates, and quoted citations, in the same visual system as the rest.

## Blocking findings

None.

## Non-blocking notes

1. **Discovery cost.** When the domain search comes back full, discovery now runs 14 name searches (two per field plus executives). The builder measured that this misses 0 of 231 supporting pages. Whether the extra units are justified is the cost auditor's call (D31).
