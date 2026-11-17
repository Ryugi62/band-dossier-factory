# Verification — dossier stage 2, round 1

- Commit checked: `3e32ac880a826539c69ab9c662f90c9588d19126`. The builder's commits are S0 `7cfb92e` through S7 `3e32ac8`.
- Ledgers: `factory/ledger/stage-2.md` (184 rows) and `factory/ledger/stage-1.md` (311 rows, binding except where QC rows change them).
- **Decision: ACCEPT.**

## 1. Fresh clone, clean build

- Cloned into the new directory `scratch/verifier/s2r1-clone` and checked out `3e32ac8`.
- D22 holds: `git diff 9166a28 -- stage-1` is empty.
- The builder changed nothing under `factory/` apart from my own B07 fix (`71ef292`).
- `stage-2/` built from its Dockerfile.
- The service ran from `factory/probes/stage-2/run_all.sh` on a `docker network create --internal` network (no outbound access), with `--cpus 2 --memory 3g`. It was given PORT and the NIMBLE, TAVILY, KERNEL and BROWSERBASE variables.
- The closed stage-1 service, built from `stage-1/` at the same commit, ran beside it for the upgrade probes.

## 2. Checks (all on the clone)

| Check | Command | Result |
|---|---|---|
| Unit tests | `cd stage-2 && python -m unittest discover -s tests -t .` | 58 run, OK (2 skipped) |
| Verifier API probes | `run_all.sh` → `run2.py` | **28 passed, 0 failed** (S1-P00..S1-P18, A01, A02, A04..A08, U01, SERVED with 127 excerpts, G); no notes |
| Verifier browser probes | `run_all.sh` → `browser.py` (headless Chromium + axe) | **13 passed, 0 failed** (B02..B12, U02, G-UI); no notes |
| Shipped checks, isolated | `python -m harness run --track dossier --repo scratch/verifier/s2r1-clone --stage 2 --mode isolated --out checks/verifier-s2-r1-3e32ac8` | stage 1: **pass, 122/122**; stage 2: **pass, 12/12**; leaks 0, fabrications 0; stage 3: fail (expected); highest contiguous stage 2; claimed stage 2 |

The service log has no tracebacks and no hard-limit or crash entries.

## 3. Reading

### Provider route

- `provider.py` is still the only provider route: `web_router.AsyncWebRouter` with `provider="nimble"`. Rendering goes through `provider_options={"render": True}` at 3 units.
- Tavily, Kernel and Browserbase are never called (D1, D14).
- The Dockerfile and manifest install `webrouter[search,extract,research]>=0.12.0` (R2-08..R2-12, Q3-05, Q3-10).

### Pipeline

- Each build does:
  - one research run;
  - one search whose query is exactly the domain;
  - six name-based field searches when that search comes back full;
  - a render of each page whose known text supports a value;
  - for each page cut short in its snippet, a plain extract and then a render if the page supports a value;
  - a read of every page a research claim cites (Q5-03).
- Candidates come only from rendered text, one per (url, provider, value), using the first supporting sentence (D13, D19).
- Kind and Published come from the rendered header, with the spec's defaults.

### Selection and import

- `selection.py` holds pure functions matching the rule: authority with null kind ranked as aggregator, recency, URL, provider order, value. Status and citations are derived there too.
- `exchange.py` rebuilds stage-1 exports per D16 and restores stage-2 exports with their candidates (D17).

### Retries and deadline

- Refused calls are retried after 1.1 s, up to four attempts, with no late cutoff (D15).
- The stage-1 deadline guard still bounds every call, renders included, to end by 290 s, so R8-12 still holds.

### UI

- The UI is vanilla ES modules served from the image, with no external URL. The token is kept in localStorage (D18, D21).
- Reads carry sequence numbers, so the latest read wins.
- Writes: a 4xx is shown as an error. No response, a 5xx or a 15 s timeout is shown as uncertain, and the retry reuses the same key and body (D20).

### Screens reviewed by eye

I looked at the screenshots of the list, the dossier (known, contested, unknown, failed), evidence, contested, the 375 px views, and the error and uncertain states. They form a coherent, calm product:

- Values and statuses are prominent, and each citation is beside its value as quoted text with a link.
- States are colour-coded.
- Kind, publication date and provider read as text for people.
- Money, years and timestamps are formatted for people.
- Primary actions are clear, the navigation is consistent, and nothing scrolls horizontally at 375 px (Q9-01..Q9-15).

### Code size

The largest file is `support.py` at 435 lines, carried over from stage 1. All modules are cohesive.

## Blocking findings

None.

## Non-blocking notes

1. **Failed-build banner layout.** On a dossier whose build failed, the banner sits in the field grid as if it were a seventh card. A full-width banner above the grid would read more clearly. This is cosmetic.
2. **Mock-specific snippet shortcut.** Against the mock, a lite snippet shorter than 300 characters is treated as the page's whole prose when choosing what to render; this is carried over from stage 1. On the live endpoint every relevant page is extracted, then rendered if it supports a value. That live branch is still not exercised offline.
