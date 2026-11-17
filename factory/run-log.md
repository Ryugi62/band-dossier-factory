
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
