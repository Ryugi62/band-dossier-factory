
## Stage 1 report (dossier) — closed

- Start: 2026-11-17T04:58Z. End: 2026-11-17T06:17Z (UTC). Elapsed about 1 h 19 min.
- Review rounds: 2 (one rejection, one acceptance).
- Rejections:
  - Round 1, verifier REJECT of f72df40: F1 (R8-12) the build could run past 300 s against live providers. Answered by builder commit 46680d2 (whole-build deadline below 300 s, per-call end-by-290 s, 10 s bound under refusals) and 9166a28 (live-path relevance and unit tests). The cost auditor ACCEPTED f72df40 in the same round.
- Final review of 9166a28: verifier ACCEPT (stage-1-r2.md), cost auditor ACCEPT (costs/stage-1-r2.md).
- Ledger rows: 311 total (302 from the specification, 9 from decisions D1-D9). 277 are covered by a passing probe or the probe runner, 12 are checked by reading the diff or Dockerfile only, 22 are definitions, unit-tested rules or delivery rows with no HTTP probe. Known gaps: 0. Probes 20 passed / 0 failed, unit tests 42/42, shipped checks stage 1 isolated 122/122 (stage 2 fails as expected; highest contiguous stage 1, claimed stage 1).
- Cost auditor final figure: 5.591 units per correct output item (766 units, 137 of 137 known fields correct, 24 builds of 12 sample companies x 2 epochs); largest build 34 units against the cap of 80; 0 duplicate calls.
- Accepted commit: 9166a2805e9c6481c7225b4eafc53f2758d464a8 (stage-1/ unchanged since; later commits touch factory/ only).
- Non-blocking notes: all owned or waived (decisions D9-D11). Carry-over for the next stage: revisit the late-retry rule under rate limits.
- Not done by design: the live-web `dossier-runway.com.json` needs a real Nimble key and spends real credit; it is made once the folder is final and is not part of this stage's dispatch.

## Stage 2 report (dossier) — closed

- Start: 2026-11-17T07:01Z. End: 2026-11-17T08:03Z (UTC). Elapsed about 1 h 02 min.
- Review rounds: 1 (accepted first time; no rejections).
- Accepted commit: 3e32ac880a826539c69ab9c662f90c9588d19126 (stage-2/; later commits touch factory/ only). `git diff 9166a28 -- stage-1` is empty.
- Verifier ACCEPT (factory/reviews/stage-2-r1.md) and cost auditor ACCEPT (factory/costs/stage-2-r1.md).
- Ledger rows: 184 for stage 2 (157 spec, 5 export/import state, 11 changed stage-1 rows, 11 decisions), on top of the 311 binding stage-1 rows. 173 rows are covered by a passing probe (API oracle, call-log check or browser probe), 2 by reading only, 9 are definition or permission rows with no probe. Known gaps: 0.
- Checks on 3e32ac8 (verifier, fresh clone, no network): unit tests 58 OK (2 skipped); API probes 28/28 passed; browser probes (headless Chromium + axe, 375 px and 1280 px) 13/13 passed; shipped checks isolated: stage 1 122/122, stage 2 12/12, leaks 0, fabrications 0, highest contiguous stage 2, claimed stage 2 (stage 3 fails as expected).
- Cost auditor final figure: 8.935 units per correct output item (1233 units, 138 of 138 known or contested fields correct, 205 of 205 candidates verified in rendered text), against 5.591 at stage 1. Largest build 59 units against the cap of 80; 0 duplicate calls; 0 URLs rendered twice. The increase was accepted as forced by the new requirements (rendered extract 3 units, one candidate per supporting page; 10 of 167 rendered texts differ from the plain text).
- Non-blocking notes: all waived with reasons (decision D23).
- Not done by design: `dossier-runway.com.json` (needs a live Nimble key and real credit); it is made once the final stage folder is final.

## Stage 3 report (dossier) — closed

- Start: 2026-11-17T08:03Z. End: 2026-11-17T09:03Z (UTC). Elapsed about 1 h 00 min.
- Review rounds: 1 (accepted first time; no rejections).
- Accepted commit: 0c9722c422e0c0ac67b95d50117cb46b0eb56cf2 (stage-3/; later commits touch factory/ only). `git diff 9166a28 -- stage-1` and `git diff 3e32ac8 -- stage-2` are empty.
- Verifier ACCEPT (factory/reviews/stage-3-r1.md) and cost auditor ACCEPT (factory/costs/stage-3-r1.md).
- Ledger rows: 123 for stage 3 (97 spec, 6 export state, 10 changed earlier rows, 10 decisions incl. D33), on top of the 311 stage-1 and 184 stage-2 rows that stay binding. 117 are covered by a passing probe, 6 are definition or permission rows with no probe. Known gaps: 0.
- Checks on 0c9722c (verifier, fresh clone, no network, no volume): unit tests 72 OK (2 skipped); API probes 35/35; restart probes (docker kill and start, also during a build) 4/4 phases; browser probes 14/14; shipped checks isolated: stage 1 122/122, stage 2 12/12, stage 3 9/9, leaks 0, fabrications 0, highest contiguous stage 3, claimed stage 3 (stage 4 fails as expected).
- Cost auditor final figure: 9.377 units per correct output item (1519 units, 162 of 162 known or contested fields correct incl. 24 executives, 261 candidates verified in rendered text), against 8.935 at stage 2 (+4.9%, under the 10% rule). Largest build 76 units against the cap of 80; 0 duplicate calls.
- Planner decisions during the stage: D24-D32 before the builder started; D33 (null `true_from` page versions hold on no date) answered the verifier's ledger question T5-05 before the builder reached T4 was reviewed.
- Non-blocking notes: all waived with reasons (D34). Carry-over: the margin to the cap is thin (76 of 80 on one company).
- Not done by design: `dossier-runway.com.json` (needs a live Nimble key and real credit); it is made once the final stage folder is final.
