# Plan — stage 2 (track dossier)

Started 2026-11-17T07:01Z. Result folder: `/Users/ryugi62/band-work/result-s1/stage-2/` (copy of the closed, unchanged `stage-1/` at 9166a28, extended).
Specification: `/Users/ryugi62/band-work/sf-2026/challenges/dossier/spec/stage-2.md` (pasted in full into every handoff, with the carried-forward stage-1 text).

| # | Item | Scope |
|---|---|---|
| S0 | Copy | `cp -R stage-1 stage-2` as its own commit (no change), rename image tag in RUN.md. `stage-1/` must stay byte-identical to 9166a28. |
| S1 | Pages | Kind (header, default own/aggregator by host), Published (RFC 3339 or none), browser text via Nimble extract `render: true` (3 units/URL), citations only from that text. |
| S2 | Candidates and selection | One candidate per (page, value) supported by the evidence incl. pages cited by research claims; selection rule (authority, recency, URL, provider, value); status known/contested/unknown; `candidates` in API shape; list endpoint unchanged. |
| S3 | Rate limits | 429 handling (retry after >= 1 s, up to 3 refusals then success; waiting does not count in the 10 s bound), no late-retry cutoff; still <= 80 units per build. |
| S4 | Export / import | Stage-2 state carries candidates; import accepts an unchanged stage-1 export (candidates rebuilt from the exported citations), tokens/idempotency retained. |
| S5 | UI shell and auth screens | `Accept: text/html` content negotiation on `/dossiers/{domain}`, routes `/`, `/signup`, `/login`, static assets in the image, design system, 375 px and desktop. |
| S6 | UI screens | `/` list/search/research, dossier screen (polling while building, latest read wins, refresh, reload, not found), evidence, contested; uncertain-outcome retry with the same key and body. |
| S7 | Delivery | Dockerfile, RUN.md, unit-test command, shipped checks stage 2 (and stage 1 suite on stage-2/ stays green). |

Sequence: verifier ledger + probes (delta ledger `factory/ledger/stage-2.md`) -> builder S0..S7 -> verifier and cost-auditor -> rework (max 4 rounds).
