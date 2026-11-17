# Plan — stage 4 (track dossier, last stage)

Started 2026-11-17T09:03Z. Result folder: `<workdir>/result-s1/stage-4/` (copy of the closed, unchanged `stage-3/` at 0c9722c, extended). `stage-1/` (9166a28), `stage-2/` (3e32ac8) and `stage-3/` (0c9722c) stay byte-identical.
Specification: `<workdir>/sf-2026/challenges/dossier/spec/stage-4.md` (pasted in full into every handoff, with the carried-forward stage-1, stage-2 and stage-3 text).

| # | Item | Scope |
|---|---|---|
| U0 | Copy | `cp -R stage-3 stage-4` as its own commit, rename image tag in RUN.md. |
| U1 | Lineage, own pages, origins | `Registrant`, `Canonical`, `First-Published-By` lines; kind `own` only for the company's registrant; lookalikes; origin of every page incl. obtaining originals (<= 3 canonical hops, host fallback); `origin` on candidates; imported candidates take the host of their URL. |
| U2 | Corroboration | `origins`, `corroborated`, `corroborated_since` on every field (six fields, members of executives/investors), standing origins tracked across ready builds, in `as_of` snapshots, in exports. |
| U3 | Investors | Eighth field `investors`: Appendix A phrases and investor-name rules, members (own/filing or two origins), value array, citations, true_from, history/feed typing by name, `/values`, UI markup separate from the six-field testids. |
| U4 | Batches | `POST /batches` (idempotent), `GET /batches/{id}`, ownership 404, shared budget with atomic reservation, each build <= 80, exhausted budget completes remaining builds, persistence/export of batches. |
| U5 | Provider failure | 5xx/429 retried, builds `ready` when nimble answers or searches/extracts answer without research, `failed` when every call fails, within the time bound; errors cost nothing. |
| U6 | Restarts | Builds running at an abrupt stop: write-ahead spend, closed after restart within 10 s of /health, one build across the restart, billed units counted in dossier and batch spent_units, refresh afterwards. |
| U7 | Upgrades | Import of stage-1, stage-2, stage-3 and stage-4 exports; investors unknown in imported state and in kept builds; standing origins of imported candidates. |
| U8 | Delivery | Dockerfile, RUN.md, unit tests, shipped checks stages 1-4; stages 1-3 suites on stage-4/ stay green. |

Sequence: verifier ledger + probes (`factory/ledger/stage-4.md`) -> builder U0..U8 -> verifier and cost-auditor -> rework (max 4 rounds).
