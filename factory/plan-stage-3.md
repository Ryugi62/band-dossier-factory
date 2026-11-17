# Plan — stage 3 (track dossier)

Started 2026-11-17T08:03Z. Result folder: `/Users/ryugi62/band-work/result-s1/stage-3/` (copy of the closed, unchanged `stage-2/` at 3e32ac8, extended). `stage-1/` (9166a28) and `stage-2/` (3e32ac8) must stay byte-identical.
Specification: `/Users/ryugi62/band-work/sf-2026/challenges/dossier/spec/stage-3.md` (pasted in full into every handoff, with the carried-forward stage-1 and stage-2 text).

| # | Item | Scope |
|---|---|---|
| T0 | Copy | `cp -R stage-2 stage-3` as its own commit, rename image tag in RUN.md. |
| T1 | Two times | `true_from` (Effective line, else UTC date of Published, else null) and `learned_at` on candidates (first build that gathered the same field/value/URL/provider) and on selected values; fields in `GET /dossiers/{domain}` carry both. |
| T2 | Executives | Seventh field `executives`: Appendix A titles cfo/coo/cto, candidates by title, selection per title, value array, status, citations, true_from rule; evidence gathering for these titles within 80 units; UI shows it with non-testid markup; `/contested` ignores it. |
| T3 | History and feed | Entry types initial/change/correction (executives typed by title), `GET /dossiers/{domain}/history`, `GET /changes` (`seq`, `since`, `limit`, `has_more`), exactly-once under concurrent refreshes. |
| T4 | Build log, as_of, values | Persist every build (time, outcome, spending, candidates, page versions); `GET /dossiers/{domain}?as_of=`; `GET /dossiers/{domain}/values?true_at=&as_of=` with the page-version rules. |
| T5 | Restarts | Durable state on the container filesystem (survives an abrupt stop and start), including accounts, tokens, dossiers, builds, history, feed seq, idempotency records, clock. |
| T6 | Upgrades | Import of stage-1, stage-2 and stage-3 exports as the spec's Upgrades; stage-3 export/import keeps history, feed, builds. |
| T7 | Delivery | Dockerfile, RUN.md, unit tests, shipped checks stages 1-3; stage-1 and stage-2 suites on stage-3/ stay green. |

Sequence: verifier ledger + probes (`factory/ledger/stage-3.md`) -> builder T0..T7 -> verifier and cost-auditor -> rework (max 4 rounds).
