# Requirement ledger — dossier stage 3

Source: `sf-2026/challenges/dossier/spec/stage-3.md` (306 lines), with `stage-1.md` and
`stage-2.md` carried forward, plus planner decisions D24–D32 (`factory/decisions.md`). Written by
the verifier from the specifications only; the shipped checks were not opened.

## How to run every probe (one command)

```sh
factory/probes/stage-3/run_all.sh /path/to/result-repo-checkout
```

The script does the following:

1. **Checks the closed folders (D24).** `stage-1/` must be identical to `9166a28` and `stage-2/` to `3e32ac8`; otherwise it aborts.
2. **Builds** `<checkout>/stage-3` (the service under test), `<checkout>/stage-1` and `<checkout>/stage-2` (the closed services, used only to produce real exports for the upgrade probes), the mock web, and the probe runner (Python, Playwright Chromium, axe-core).
3. **Starts everything on one network.** All containers join a single `docker network create --internal` network with no outbound access. The services get PORT plus all the provider variables, and the stage-3 service runs with no volume. The mock serves the sample corpus plus the verifier corpora of stages 1–3 (`factory/probes/stage-3/corpus/lumen-atlas.test.json` is the change-over-time company, epochs 0–4).
4. **Runs, in order:**
   1. `run3.py --phase main`: every stage-1 probe (`S1-P*`) and stage-2 API probe (`S2-A*`, `S2-U01`) re-run with the stage-3 invariants (INV3); then C01–C05 (change over time, validation, concurrency, stage-3 export/import, feed paging); then U3 and U4 (upgrades from real stage-1 and stage-2 exports); then SERVED and G.
   2. Restarts:
      - `run3.py --phase pre-restart`
      - `docker kill` + `docker start` of the service container
      - `run3.py --phase post-restart`
      - `run3.py --phase pre-kill` (a build is running)
      - `docker kill` + `docker start`
      - `run3.py --phase post-kill`
   3. `browser3.py`: every stage-2 screen probe (B02–B12, U02) re-run with INV3, plus B13 (executives markup).

Each part prints one line per probe and `TOTAL: n passed, m failed`. The script exits non-zero on any failure.

Environment options: `PART=api|restart|browser|all`, `PROBE_ONLY=C01,B13` (applies to the main and browser parts), `KEEP=1`, `LOGDIR`.

## Columns

- **ID**: `T<section>-<nn>`, numbered by spec section:
  - T0 preamble
  - T1 Two times per value
  - T2 Executives
  - T3 Changes and corrections
  - T4 `?as_of=`
  - T5 `/values`
  - T6 `/history`
  - T7 `/changes`
  - T8 Concurrency
  - T9 Upgrades
  - T10 Restarts

  Other prefixes: `QX3-` stage-3 export state kinds; `TC-` stage-1/2 rows whose expected behaviour changes; `TD-` planner decisions.
- **★**: a row a quick reading would miss.
- **Probe**:
  - `C..` stage-3 API probes in `run3.py`; `U3`/`U4` upgrade probes; `R-*` restart phases; `B13` browser.
  - `S1-*`/`S2-*` the earlier probes re-run.
  - `INV3` the dossier invariant checker run on every read; `EV3` the corpus oracle (executives and true_from).
  - `HIST`/`FEED`/`ASOF`/`VALUES` the oracles in `run3.py`, computed from the recorded builds of the probe run and the mock call log (page versions).
  - `read` reading at verification time.

## Stage-1 and stage-2 rows

All rows of `factory/ledger/stage-1.md` (311) and `factory/ledger/stage-2.md` (184) stay binding, except where a TC row below changes them.

The earlier probes re-run as `S1-*`, `S2-*` and the B probes. In those re-runs, INV2 is applied to the six fields and INV3 adds the seventh field and the two times. The stage-1 cost window and the stage-2 render-cost and D13 checks apply to every build.

### Changed rows

| ID | ★ | Earlier row | Change in stage 3 (quoted) | Kind | Probe |
|---|---|---|---|---|---|
| TC-01 | ★ | R4-14 "A dossier has exactly these six fields" / R8-23 "`fields` always holds all six fields" | "A dossier has a seventh field, `executives`. The `fields` of every response that lists a dossier's fields hold it, after the six fields of §4." | format | INV3 |
| TC-02 | ★ | Q5-06 candidate keys | "Candidates gain `true_from` and `learned_at`." | format | INV3 |
| TC-03 | ★ | R2-26 "Disk — ephemeral; state need not survive a container restart" and R10-26 | "Disk — the container's filesystem; it survives a container restart" and "The sentence \"State need not survive an abrupt container restart\" in `stage-1.md` §10 no longer applies." | state | R-* |
| TC-04 | ★ | Q16-* stage-1 upgrade (stage 2) | a stage-3 service must also accept stage-2 exports and keep their builds (T9-*) | export-state | U3, U4 |
| TC-05 | ★ | Q14-03 "`empty-contested` — Shown instead of the list when no field is contested" | "On `/contested`, \"no field is contested\" means none of those six fields is." | ui | B13 |
| TC-06 | ★ | Q12-05 / Q13-01 six `field-*` / `evidence-*` testids | "`executives` takes none of them, and a screen that shows it does so with other markup." | ui | B06, B13 |
| TC-07 | | R9-18 research names the six fields | "A research run (§4) still asks for the six fields of §4 only." | cost | LOG (research `fields` == six) |
| TC-08 | ★ | R8-21 GET field shape | "Each field of `GET /dossiers/{domain}` also carries the selected value's `true_from` and `learned_at`." | format | INV3 |
| TC-09 | ★ | R10-11..R10-19 export state kinds | builds, page versions, history, feed (with seq) and first-seen times are new state that leaves the service: see QX3 rows | export-state | C04 |
| TC-10 | | R8-13 reads make no provider call | holds for `?as_of=`, `/values`, `/history`, `/changes` too | cost | C02 (LOG) |

## T0 Preamble

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T0-01 | | intro | "The requirements from stages 1 and 2 continue to apply, with the additions below." | behaviour | S1-*, S2-*, B* |
| T0-02 | ★ | intro | "4. Every change to a selected value appears exactly once in the change feed, at the time this stage assigns to it." | behaviour | FEED (C01, C03) |

## T1 Two times per value

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T1-01 | | times | "Every candidate and every selected value now has two times" | format | INV3 |
| T1-02 | ★ | times | "**`true_from`**: the date from which the evidence says the value holds. A page states it in the header line `Effective: <YYYY-MM-DD>`. A page with no valid `Effective` line takes the date part, in UTC, of its `published_at`; with neither, `true_from` is null." | format | EV3 (lumen: Effective; invalid `2025-13-40` with Published `2024-03-05T23:30:00-02:00` → `2024-03-06`; Published only; neither → null) |
| T1-03 | ★ | times | "**`learned_at`**: when this service first had the value. For a candidate, it is the time (§8, Builds) of the first build that gathered a candidate with the same field, value, URL and provider." | format | INV3 (≤ retrieved_at), C01 |
| T1-04 | ★ | times | "For a selected value, it is the time of the build that made it the selected value." | format | HIST (field learned_at == its latest history entry; D32) |
| T1-05 | | times | "Candidates gain `true_from` and `learned_at`." | format | INV3 |
| T1-06 | ★ | times | "`retrieved_at` (stage 2) stays the time of the build that gathered the candidate in the current candidate set." | format | INV2/INV3 (retrieved_at == researched_at) |
| T1-07 | ★ | times | "A selected value's `true_from` is that of its selected candidate." | format | INV3 |
| T1-08 | | times | "Each field of `GET /dossiers/{domain}` also carries the selected value's `true_from` and `learned_at`." | format | INV3 |
| T1-09 | ★ | times | "Both are null when the field is `unknown`." | format | INV3 |
| T1-10 | ★ | times | "In an `as_of` response these describe the selected value at that snapshot, using no later history." | format | ASOF (C01) |
| T1-11 | | times | "The selection rule in `stage-2.md` is unchanged." | selection | INV2 |

## T2 Executives

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T2-01 | ★ | exec | "A dossier has a seventh field, `executives`. The `fields` of every response that lists a dossier's fields hold it, after the six fields of §4." | format | INV3 (GET, as_of), C01 (values, history) |
| T2-02 | ★ | exec | "A research run (§4) still asks for the six fields of §4 only." | cost | LOG (S1 window: research fields == six) |
| T2-03 | ★ | exec | "Its value is an array with one object `{ \"title\": T, \"name\": N }` for each title below that has a selected person, in the order `cfo`, `coo`, `cto`. These objects are the field's **members**." | format | INV3, C01 |
| T2-04 | ★ | exec | "When no title has a selected person, the value is null and the field is `unknown`." | format | INV3, U3/U4 |
| T2-05 | ★ | exec | "For Appendix A, each title is a field with these statement phrases and with the format and normalisation of `ceo` (A.4, A.5), the title's own statement phrases taking the place of those for `ceo`: `cfo` — `chief financial officer`, `CFO`; `coo` — `chief operating officer`, `COO`; `cto` — `chief technology officer`, `CTO`" | support | oracle3 `supported_title`, INV3, EV3 |
| T2-06 | ★ | exec | "A candidate of `executives` is a candidate of one title: it carries `title` beside `value`, and its `value` is the person's name." | format | INV3, EV3 |
| T2-07 | ★ | exec | "A research claim is never a candidate of `executives`." | support | INV3 (excerpt supports title by Appendix A); read |
| T2-08 | ★ | exec | "The selection rule in `stage-2.md` runs separately over the candidates of each title." / "`selected` is true on the highest-ranked candidate of each title that has candidates, and false on the others." | selection | INV3 (lumen cto: own Bruno Costa over aggregator Rui Pinto) |
| T2-09 | ★ | exec | "`candidates` lists every candidate by title, in the order above, then in rank order." | selection | INV3 |
| T2-10 | ★ | exec | "`citations` are, for each member in order, the `url`, `excerpt` and `provider` of every candidate with the member's title and name, in rank order." | selection | INV3 |
| T2-11 | ★ | exec | "`status` is `unknown` when the value is null, `contested` when the candidates of some title carry two or more different names, and `known` otherwise." | format | INV3, C01 (lumen executives contested by two CTO names) |
| T2-12 | ★ | exec | "A candidate's `learned_at` is the time of the first build that gathered a candidate with the same title, name, URL and provider." | format | INV3, C01 |
| T2-13 | ★ | exec | "A member's `true_from` is that of its title's selected candidate. The field's `true_from` is the latest of its members' `true_from`, or null when any member's is null." | format | INV3, C01 (e2: latest of 2021-01-01, 2026-01-15, 2021-01-01 = 2026-01-15) |
| T2-14 | ★ | exec | "`GET /dossiers/{domain}/values` chooses each title's person from the candidates at `true_at` and gives the value, `true_from` and `citations` from them by these rules." | format | VALUES (C01) |
| T2-15 | ★ | exec | "A history and feed entry for `executives` is typed by title, in place of the table in Changes and corrections. A title **differs** between the earlier and the new value when exactly one of them has a member with that title, or both have one and their names differ." | behaviour | HIST, FEED (C01: e1 coo appears → change) |
| T2-16 | ★ | exec | "A differing title counts as a correction when both values have a member with that title, both members' `true_from` are not null, and the new member's is on or before the earlier member's. The entry is `correction` when every differing title counts as a correction, and `change` otherwise." | behaviour | HIST, FEED (C01: e2 cto Bruno→Bruna with 2021-01-01 ≤ 2026-02-01 → correction) |
| T2-17 | ★ | exec screens | "The `data-testid` attributes of the screens in `stage-2.md` name only the six fields of §4: `executives` takes none of them, and a screen that shows it does so with other markup." | ui | B13, B06 |
| T2-18 | ★ | exec screens | "On `/contested`, \"no field is contested\" means none of those six fields is." | ui | B13 (only executives contested → empty-contested) |

## T3 Changes and corrections

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T3-01 | ★ | changes | "When a build completes `ready`, each field whose selected value differs from its selected value before the build gets one history entry, and one feed entry, of one of two types" | behaviour | HIST, FEED (C01) |
| T3-02 | ★ | changes | "`correction` — Both the earlier and the new value are not null, and the new value's `true_from` is on or before the earlier value's `true_from`" | behaviour | C01 (funding 8M→9M, 2025-06-01 ≤ 2025-06-10; ceo Tiago→Rita) |
| T3-03 | ★ | changes | "`change` — Every other difference, including a value appearing where there was none, a value disappearing, and either `true_from` being null" | behaviour | C01 (headcount disappears; ceo Rita→Tiago with a later date) |
| T3-04 | ★ | changes | "A field's first selected value, set by the dossier's first build that completes `ready`, gets a history entry of type `initial` and no feed entry." | behaviour | C01, C02 (empty feed after a first build) |
| T3-05 | ★ | changes | "A field that is `unknown` after that build gets its first entry when it first gets a value, and that entry is a `change`." | behaviour | HIST; U3/U4 (executives after upgrade) |
| T3-06 | ★ | changes | "A build that completes with the same selected value for a field adds nothing for it, even when its candidates, citations or `true_from` differ." | behaviour | C01 (e3: legal_name true_from 2020-05-01 → 2026-03-01, no entry; e4: no entries) |
| T3-07 | ★ | changes | "A `failed` build adds nothing." | behaviour | R-post-kill (abandoned build), S1-P09 |
| T3-08 | ★ | changes | "Concurrent refreshes of one dossier run one build (§8) and so add each entry once." | concurrency | C03 |

## T4 `GET /dossiers/{domain}?as_of=`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T4-01 | ★ | as_of | "Returns the dossier as this service had it at `as_of`: the fields, candidates and `researched_at` of the latest build that completed `ready` and whose time is at or before `as_of`, decided by `learned_at`, never by `true_from`. `state` is `ready`. `spent_units` is the total of the builds whose time is at or before `as_of`." | behaviour | ASOF (C01) |
| T4-02 | ★ | as_of | "When several ready builds have the same time, return the last of them in build order. This also applies when equivalent RFC 3339 timestamps use different offsets. The clock need not advance between builds." | behaviour | ASOF (C01: e2 and e3 at the same clock time; as_of written with a −05:00 offset) |
| T4-03 | ★ | as_of | "No build of the dossier completed `ready` with a time at or before `as_of` — 404 `not_found`" | error | ASOF (T0 − 1 s), U3 (null researched_at) |
| T4-04 | | as_of | "`as_of` is not an RFC 3339 timestamp with an explicit offset — 422 `validation_failed`" | error | C02 |
| T4-05 | | as_of | "No dossier for the domain — 404 `not_found`" | error | C02 |
| T4-06 | | as_of | "Without `as_of`, `GET /dossiers/{domain}` is unchanged." | behaviour | S1-*, S2-* |

## T5 `GET /dossiers/{domain}/values?true_at=`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T5-01 | | values | "Returns, for each field, the value that the evidence this service had at `as_of` says held on the date `true_at`." | behaviour | VALUES |
| T5-02 | ★ | values | "A **page version** is what one ready build gathered from one URL: its candidates and its `true_from`. The versions of a URL known at `as_of` are those gathered by ready builds whose time is at or before `as_of`, taken in build order. Each version holds from its `true_from`." | behaviour | VALUES (C01: 2026-02-15 as of T1 → Tiago Neves) |
| T5-03 | ★ | values | "When a later version of the same URL is gathered, it replaces every earlier version of that URL whose `true_from` is on or after its own." | behaviour | VALUES (C01: the e2 team version dated 2021-01-01 replaces the e1 version dated 2026-02-01 → 2026-02-15 now gives Rita Gomes; funding 9M replaces 8M) |
| T5-04 | ★ | values | "The latest earlier version that it does not replace stops holding on the later version's `true_from`." | behaviour | VALUES (C01: about page dated 2020-05-01 stops on 2026-03-01) |
| T5-05 | ★ | values | "A version whose `true_from` is null holds from no date, and a later version with a null `true_from` replaces every earlier version of its URL." | behaviour | VALUES (both readings of "holds from no date" accepted, see note) |
| T5-06 | ★ | values | "A gathered version with no candidates still replaces or ends earlier versions by this rule." | behaviour | VALUES (rendered pages without candidates from the call log) |
| T5-07 | ★ | values | "The candidates **at `true_at`** are those of every version that holds on that date. Each field's value is chosen from them by the selection rule in `stage-2.md`, and its `true_from` is that of the chosen candidate." | selection | VALUES |
| T5-08 | | values | response `{ "domain", "true_at", "as_of", "fields": { f: { "value", "true_from", "citations" } } }` | format | VALUES |
| T5-09 | ★ | values | "`as_of` defaults to the current time (§8)." | behaviour | C01 (echoed as_of == clock) |
| T5-10 | ★ | values | "A field with no candidate at `true_at` has `\"value\": null`, `\"true_from\": null`, `\"citations\": []`. Citations are those of the candidates at `true_at` with the chosen value." | format | VALUES |
| T5-11 | ★ | values | "`true_at` missing or not a `YYYY-MM-DD` date, or `as_of` not an RFC 3339 timestamp with an explicit offset — 422 `validation_failed`" | error | C02 |
| T5-12 | ★ | values | "No dossier for the domain, or no build of it completed `ready` with a time at or before `as_of` — 404 `not_found`" | error | C02, U3, U4 |
| T5-13 | ★ | values | "For state imported from an export, the builds and versions are those Upgrades gives." | export-state | U4 |

## T6 `GET /dossiers/{domain}/history`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T6-01 | | history | response `{ "domain", "fields": { f: [ { "type", "value", "true_from", "learned_at", "citations" } ] } }` | format | HIST |
| T6-02 | ★ | history | "`fields` holds all seven fields. Each list is in the order the entries were added, oldest first." | format | HIST |
| T6-03 | ★ | history | "An entry's `value`, `true_from`, `learned_at` and `citations` are those of the selected value it records. An entry whose value is null has `\"true_from\": null` and `\"citations\": []`." | format | HIST (C01 headcount → null) |
| T6-04 | | history | "No dossier for the domain is 404 `not_found`." | error | C02 |

## T7 `GET /changes`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T7-01 | | changes | "The feed holds every `change` and `correction` entry of every dossier." Entry keys `seq`, `domain`, `field`, `type`, `from`, `to`, `true_from`, `learned_at` | format | FEED, C05 |
| T7-02 | ★ | changes | "`seq` is a positive integer, unique across the feed, and larger for every later entry." | format | FEED, C04, R-post-restart |
| T7-03 | ★ | changes | "Entries added by one build are numbered in the order of the fields in `stage-1.md` §4, then `executives`." | format | FEED (C01: ceo, headcount_range, funding_total, executives) |
| T7-04 | ★ | changes | "`from` and `to` are the earlier and the new selected value, either of which may be null. `true_from` is the new value's. `learned_at` is the time of the build that added the entry." | format | FEED |
| T7-05 | ★ | changes | "`since` defaults to 0 and lists only entries whose `seq` is greater than it." | behaviour | C05 |
| T7-06 | ★ | changes | "It is an integer, 0 or more." | error | C02 (−1, `abc`, `1e2` → 422) |
| T7-07 | | changes | "Entries are ordered by `seq` ascending." | behaviour | FEED |
| T7-08 | ★ | changes | "`limit` defaults to 50, range 1 to 200." | limit | C02, C05 |
| T7-09 | ★ | changes | "`has_more` is true when entries exist beyond the last one returned." | behaviour | C05 |

## T8 Concurrency

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T8-01 | ★ | conc | "Concurrent refreshes and reads must produce the same results as executing them one at a time in some order." | concurrency | C03 (12 concurrent refreshes → one research run) |
| T8-02 | ★ | conc | "No change appears twice in the feed, and none is missing from it." | concurrency | C03, FEED |

## T9 Upgrades

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T9-01 | ★ | upgrade | "A stage-3 service must accept an export produced by the same team's stage-1 or stage-2 service." | export-state | U3, U4 |
| T9-02 | ★ | upgrade | "Every imported field that has a value gets one history entry of type `initial`, with `learned_at` the dossier's `researched_at` and `true_from` null unless the exported state records the dates that give it." | export-state | U3 (null), U4 (D25: UTC date of the selected candidate's published_at) |
| T9-03 | ★ | upgrade | "The feed starts empty; the first build after import compares its selected values with the imported ones." | export-state | U3, U4 (first post-import build: only executives → `change`, seq 1) |
| T9-04 | ★ | upgrade | "Existing tokens, dossiers and completed idempotent responses survive the import as in `stage-1.md` §10" | export-state | U3, U4 |
| T9-05 | ★ | upgrade | "and the history and feed of a stage-3 export survive a stage-3 import unchanged. So do its builds: after a stage-3 import, `?as_of=` and `/values` answer as they did in the exporting service." | export-state | C04 |
| T9-06 | ★ | upgrade | "State imported from a stage-1 export counts as one build that completed `ready` at the dossier's `researched_at`, and each imported candidate's URL as one version gathered by it; imported candidates have `learned_at` equal to their `retrieved_at`. An `as_of` at or after that time and before the next build returns the imported fields, and an earlier `as_of` is 404 `not_found`." | export-state | U3 |
| T9-07 | ★ | upgrade | "An imported dossier whose `researched_at` is null answers every `as_of` with 404 `not_found` until a build completes." | export-state | U3 (failed-only dossier) |
| T9-08 | ★ | upgrade | "State imported from a stage-2 export keeps the builds that the stage-2 service made, each with its time, its outcome and its spending. Each of them that completed `ready` keeps the candidates it gathered and, for each URL it gathered, one page version whose `true_from` follows from that page's `Effective` and `Published` lines as that build gathered them" | export-state | U4 (per D25) |
| T9-09 | ★ | upgrade | "State that the stage-2 service had itself imported counts as one build that completed `ready` at the dossier's `researched_at`. `?as_of=`, `/values` and each candidate's `learned_at` then answer as if this service had made those builds." | export-state | U4 |
| T9-10 | ★ | upgrade | "History is still one `initial` entry per field that has a value, as above, and an `as_of` response takes each field's `learned_at` and `true_from` from that history (Two times per value)." | export-state | U4 |
| T9-11 | ★ | upgrade | "An export of a stage-1 or stage-2 service has no `executives` candidates. After its import, `executives` is `unknown`, in the imported state and in every build kept from the export, and has no history entry; the first build that completes `ready` with a value for it adds a `change`, or an `initial` entry when it is the dossier's first build that completes `ready`." | export-state | U3, U4 |

## T10 Restarts

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T10-01 | ★ | restart | "Disk — the container's filesystem; it survives a container restart" (replaces the Disk row of `stage-1.md` §2) | state | R-* (no volume) |
| T10-02 | ★ | restart | "The container may be stopped abruptly at any time, with no warning and no time to finish what the service is doing, and then started again." | state | run_all (`docker kill`) |
| T10-03 | ★ | restart | "When no build is running at the stop, the service answers after the restart exactly as it did before the stop: Every account signs in with its password, and every bearer token is valid." | state | R-post-restart |
| T10-04 | ★ | restart | "Every dossier answers `GET /dossiers/{domain}`, with and without `as_of`, `GET /dossiers/{domain}/values` and `GET /dossiers/{domain}/history` as before, and `GET /dossiers` lists the same dossiers." | state | R-post-restart (byte-equal JSON) |
| T10-05 | ★ | restart | "The change feed holds the same entries with the same `seq`. An entry added after the restart has a larger `seq` than every entry before it." | state | R-post-restart |
| T10-06 | ★ | restart | "A replay of a completed idempotent request answers as §7 requires." | retry | R-post-restart |
| T10-07 | ★ | restart | "The clock reads the time it read before the stop until reset or `POST /_test/clock` moves it." | timing | R-post-restart (next build's time == clock before the stop) |
| T10-08 | ★ | restart | (consequence with D27) a stop during a build leaves the dossier in its last completed state, adding no history or feed entries, and later builds work | state | R-pre-kill / R-post-kill |
| T10-09 | | restart | (§3.2) after a start the service answers `/health` within 60 s | timing | R-* (health wait) |

## QX3 Export / import — state kinds that leave the service in stage 3

| ID | ★ | Requirement | Kind | Probe |
|---|---|---|---|---|
| QX3-01 | ★ | every build (time, outcome, spending) survives: `?as_of=` and `spent_units` at each as_of identical after import | export-state | C04 |
| QX3-02 | ★ | page versions survive: `/values` identical after import | export-state | C04 |
| QX3-03 | ★ | history survives unchanged | export-state | C04 |
| QX3-04 | ★ | feed entries and their `seq` survive; new entries continue after the last `seq` (D28) | export-state | C04 |
| QX3-05 | ★ | candidates' `learned_at` (first-seen times) survive | export-state | C04 (GET identical) |
| QX3-06 | | users, tokens, idempotency records as in stage 1 | export-state | S1-P15, S2-A07 |

## TD Planner decisions

| ID | ★ | Decision | Text (from decisions.md) | Kind | Probe |
|---|---|---|---|---|---|
| TD-24 | | D24 | "D1, D2, D4, D5, D6, D9-D15, D18-D22 continue … Stage-1 and stage-2 folders stay byte-identical" | delivery | run_all (D24 check), S1-*, S2-* |
| TD-25 | ★ | D25 | stage-2 export → one ready build at `researched_at` (spending = exported spent_units), candidates `learned_at` = `retrieved_at`, one page version per candidate URL with `true_from` = UTC date of the candidate's `published_at` (null if null); history one `initial` per field with value, `learned_at` = `researched_at`, `true_from` = the selected candidate's version `true_from`; stage-1 export: D16 + spec (true_from null); null `researched_at`: no build | export-state | U3, U4 |
| TD-26 | ★ | D26 | "`format_version` stays 1, `track` \"dossier\"; the state holds … every build …, history, feed entries with their `seq` and the next `seq`, first-seen map …; Import accepts the three shapes … `executives` is `unknown` in imported state from stage-1/2 exports … with no history entry." | export-state | C04, U3, U4 |
| TD-27 | ★ | D27 | "State lives in a durable store on the container's own filesystem … every write committed … before its HTTP response … The clock's set time … is persisted … A build found running after restart is closed as abandoned: the dossier returns to its last completed state …, the spending recorded before the stop stays in `spent_units`, and it adds no history, no feed entry and no build log entry." | state | R-* |
| TD-28 | ★ | D28 | "`seq` starts at 1 after reset and after an import of a stage-1/2 export (empty feed); a stage-3 import restores the feed and continues from its next `seq`." | format | U3, U4 (seq 1), C04 |
| TD-29 | ★ | D29 | "Auth (401) first; then parameter validation (422) before existence (404) … `true_at` must be a real calendar date." | error | C02 |
| TD-30 | ★ | D30 | "The dossier and evidence screens keep exactly the six `field-*`/`evidence-*` testids of stage 2 and additionally show `executives` … in separate markup … `/contested` considers the six fields only." | ui | B13, B06, B11 |
| TD-31 | ★ | D31 | "Executives candidates come only from rendered page text (D13) via Appendix A with the title phrases; research claims are never executives candidates. The 80-unit cap per build is unchanged" | cost | EV3 (D13 check for executives), LOG |
| TD-32 | ★ | D32 | "When a build keeps the same selected value as the build before, `learned_at` stays the time of the build that first made it selected in the current run of that value … History entries are added only on a differing selected value" | format | HIST (C01: legal_name learned_at stays T0 through e4) |

## Rows added by the blind re-derivation

From `factory/reviews/stage-3-blind.md`.

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| T2-19 | ★ | exec | "The selection rule in `stage-2.md` runs separately over the candidates of each title." (one title's candidates never affect another's selection) | selection | INV3 |
| T2-20 | | exec | field shape `{ "value": [...], "status", "true_from", "learned_at", "citations", "candidates" }` (example) | format | INV3 |
| T2-21 | ★ | exec | (consequence of "the title's own statement phrases taking the place of those for `ceo`") only the company name and that title's phrases are taken out before finding a name | support | oracle3, EV3 |
| T5-14 | ★ | values | (consequence of the replacement and end rules) a version is replaced or ended only by a later version of the same URL; a dated version of a page later builds no longer gather keeps holding | behaviour | C01 (headcount page gone after e1; `/values` at 2026-02-15 still 11-50) |

## Probe index

| Probe | Covers |
|---|---|
| S1-P00..S1-P18, S2-A01..S2-A08, S2-U01, SERVED, G | earlier API probes re-run with INV3 |
| C01 | lumen-atlas.test epochs 0–4: two times, executives, history, feed (types, order, seq), as_of (equal times, offsets, 404), values (page versions) |
| C02 | validation and errors (as_of, true_at, since, limit; 401 → 422 → 404 order); no provider calls on the new reads |
| C03 | 12 concurrent refreshes: one build, each change exactly once |
| C04 | stage-3 export/import round trip; seq continues |
| C05 | feed paging |
| U3 / U4 | upgrades from real stage-1 / stage-2 exports (closed services) |
| R-pre-restart / R-post-restart | everything answers identically after `docker kill` + `docker start`; clock; replay; seq continues |
| R-pre-kill / R-post-kill | stop during a build: last completed state, no history/feed entries, later builds work |
| B02..B12, U02 | stage-2 screen probes re-run against stage 3 |
| B13 | executives in separate markup, six field testids, `/contested` ignores executives |

## Note on one ambiguity (accepted both ways by the probes)

T5-05: "A version whose `true_from` is null holds from no date" can be read two ways: the version holds on every date (no start), or it holds on no date. VALUES accepts a field when its answer matches either reading. A planner decision would let the probes assert one reading.

## Row count

122 rows: 97 new stage-3 specification rows, 6 export state rows, 10 changed earlier rows, 9 planner-decision rows; 102 marked ★. The 311 stage-1 and 184 stage-2 rows remain binding except as changed by TC-01..TC-10.
