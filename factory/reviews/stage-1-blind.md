# Blind re-derivation — dossier stage 1

The two longest sections of `spec/stage-1.md` are §8 API (118 lines) and §4 Model (111 lines).
Their normative statements were listed again from the specification text, without the ledger
open, and then compared with `factory/ledger/stage-1.md`. Statements the ledger did not
already have as their own row are marked **NEW**; they are appended to the ledger as R4-50..R4-53
and R8-43..R8-46.

## §4 Model

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| B4-01 | Users sign up and log in (§6). | **NEW** → R4-53 |
| B4-02 | Every authenticated user sees the same dossiers. | R4-01 |
| B4-03 | A company is identified by its domain. | R4-02 |
| B4-04 | Every domain in a body or a path is normalised: whitespace trimmed, lowercased, one trailing `.` removed, one leading `www.` removed. | R4-03..R4-06 |
| B4-05 | Normalised domain: ≥ 2 labels; each label 1–63 chars of `a-z0-9-`; not starting/ending with `-`; ≤ 253 chars. | R4-07..R4-10 |
| B4-06 | Anything else, incl. a URL with scheme or path, is 422 `validation_failed`. | R4-11 |
| B4-07 | `Acme-Robotics.TEST.`, `www.acme-robotics.test`, `acme-robotics.test` are one company and one dossier. | R4-12 |
| B4-08 | Responses always carry the normalised domain. | R4-13 |
| B4-09 | Exactly six fields. | R4-14 |
| B4-10 | Field types: `legal_name`, `hq_city`, `ceo` strings; `founded_year`, `funding_total` integers; `headcount_range` one of 8 ranges. | R4-15..R4-20 |
| B4-11 | A string value is written as the excerpt writes it, without surrounding whitespace. | R4-21 |
| B4-12 | A headcount stated as a number, or as a range inside one bucket, takes the containing range. | R4-22 |
| B4-13 | Field shape `{value, status, citations:[{url, excerpt, provider}]}`. | **NEW** → R4-50 |
| B4-14 | `status` known iff value not null. | R4-23 |
| B4-15 | Known ⇒ ≥ 1 citation; unknown ⇒ `value: null`, `citations: []`. | R4-24, R4-25 |
| B4-16 | `url` is the page the excerpt was served for; `provider` is the provider that served it (`nimble`/`tavily`). | R4-26, R4-27 |
| B4-17 | Evidence = every page some search naming the company returns (full text) + every claim of a nimble research run asking for all six fields. | R4-28 |
| B4-18 | Of successful searches, exactly one per build has query exactly the normalised domain; others use other queries. | R4-29, R4-30 |
| B4-19 | A search answered with an error does not count. | R4-31 |
| B4-20 | Gathered pages = pages whose text a build obtains. | R4-32 |
| B4-21 | A citation's excerpt is copied character for character (whitespace runs may become one space), 1–500 chars, from prose not header. | R4-33..R4-35 |
| B4-22 | Support is decided by Appendix A, reading the excerpt on its own. | R4-36 |
| B4-23 | Examples: `$12M` and `12 million dollars` support 12000000; `employs about 120 people` supports 51-200. | **NEW** → R4-51 (R4-37 only had the general rule) |
| B4-24 | A research claim is asserted only when its citation supports it. | R4-38 |
| B4-25 | A field is unknown when no evidence supports a value, even when research claims one. | R4-39 |
| B4-26 | Several supported values: hold one, cite only excerpts supporting it. | R4-40 |
| B4-27 | Pages have URL, title, text; header lines `Name: value` (capitalised word(s) joined by `-`). | R4-42 |
| B4-28 | Header ends at the first empty line; the rest is prose. | R4-43 |
| B4-29 | First line not a header line ⇒ no header, all prose. | R4-44 |
| B4-30 | `Facts:` carries a JSON object; informative only; citations from prose; support by Appendix A alone. | R4-45 |
| B4-31 | Other header lines may be ignored. | R4-46 |
| B4-32 | Fixture shape: `now`, `users[{id, email, password, display_name}]`. | **NEW** → R4-52 |
| B4-33 | `now` is required and sets the clock. | R4-47 |
| B4-34 | Seeded users log in immediately with the given password. | R4-48 |
| B4-35 | Two users sharing an email ⇒ 422 `validation_failed`, changing nothing. | R4-49 |

## §8 API

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| B8-01 | A build calls the providers, decides each field, and replaces the fields when it completes. | R8-01 |
| B8-02 | First build via `POST /dossiers`, later ones via refresh. | R8-02 |
| B8-03 | A build's time is the clock's time when its request was received. | R8-03 |
| B8-04 | At most one build per dossier at a time. | R8-04 |
| B8-05 | Ends `ready` when completed, `failed` when none of its provider calls succeeded. | R8-05, R8-06 |
| B8-06 | A failed build leaves the fields as they were. | R8-07 |
| B8-07 | ★ Consequence of B8-05/B8-06 with the `state` rule: after a failed refresh the dossier reads `state: failed` while still showing the fields (and `researched_at`) of the last ready build. | **NEW** → R8-43 |
| B8-08 | Ready ⇒ each field known exactly when the evidence supports a value. | R8-08 |
| B8-09 | Calls answering within 1 s ⇒ build ends within 10 s of its request. | R8-09 |
| B8-10 | Live providers: no give-up on a call waiting < 30 s; no time-based stop in the first 120 s; ends within 300 s. | R8-10..R8-12 |
| B8-11 | Reads, lists and every other request except the two write paths make no provider call. | R8-13 |
| B8-12 | `POST /dossiers` requires `Idempotency-Key`. | R8-14 |
| B8-13 | 202 body `{dossier_id, domain, state: building}`. | R8-15 |
| B8-14 | No dossier ⇒ create, start first build, 202. | R8-16 |
| B8-15 | Existing dossier ⇒ no build, 200 with `dossier_id`, `domain`, current `state`. | R8-17 |
| B8-16 | Concurrent requests for one domain ⇒ one dossier, one build, whatever their keys. | R8-18 |
| B8-17 | `domain` missing / invalid ⇒ 422. | R8-19, R8-20 |
| B8-18 | GET shape. | R8-21 |
| B8-19 | `state` building while a build runs, else outcome of the latest build. | R8-22 |
| B8-20 | `fields` always all six; all unknown before the first ready build; during a later build, the last ready build's fields. | R8-23..R8-25 |
| B8-21 | `researched_at` = time of the last ready build, or null. | R8-26 |
| B8-22 | `spent_units` = total cost of every provider call for this dossier by every build since creation. | R8-27 |
| B8-23 | ★ Consequence of B8-22: spending of builds that end `failed` (e.g. calls that timed out, which cost their units) is included too. | **NEW** → R8-44 |
| B8-24 | Path domain normalised; absent ⇒ 404. | R8-28 |
| B8-25 | ★ Consequence: the refresh path's domain is normalised too, so `/dossiers/WWW.Acme.TEST/refresh` refreshes `acme.test` (while being a different request for idempotency, R7-05). | **NEW** → R8-45 |
| B8-26 | Refresh requires a key, takes no body, starts a build, 202 `{dossier_id, domain, state: building}`. | R8-29, R8-30 |
| B8-27 | Refresh during a running build ⇒ no second build, 202 same body. | R8-31 |
| B8-28 | A refresh researches again; its spending counts. | R8-32 |
| B8-29 | Refresh of an absent dossier ⇒ 404. | R8-33 |
| B8-30 | List shape; `legal_name` = the field's value or null. | R8-35, R8-36 |
| B8-31 | `q` optional; substring of domain or legal_name, case-insensitive; empty `q` lists all. | R8-37, R8-38 |
| B8-32 | Ordered by domain ascending. | R8-39 |
| B8-33 | `limit` default 50, 1..200; `offset` default 0; `has_more`. | R8-40..R8-42 |
| B8-34 | ★ Consequence of B8-20 and B8-30: while a refresh runs, a list item shows `state: building` and the `legal_name` / `researched_at` of the last ready build. | **NEW** → R8-46 |

## Result

8 statements added to the ledger (R4-50..R4-53, R8-43..R8-46). No statement in the ledger was
found to contradict the re-derived list.
