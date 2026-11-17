# Requirement ledger — dossier stage 4 (last stage)

Source: `sf-2026/challenges/dossier/spec/stage-4.md` (255 lines), with `stage-1.md`, `stage-2.md` and
`stage-3.md` carried forward, plus planner decisions D35–D46 (`factory/decisions.md`). Written by the
verifier from the specifications only; the shipped checks were not opened.

## How to run every probe (one command)

```sh
factory/probes/stage-4/run_all.sh /path/to/result-repo-checkout
```

The script does the following:

1. **Checks the closed folders (D35).** `stage-1/`, `stage-2/` and `stage-3/` must be identical to `9166a28`, `3e32ac8` and `0c9722c`; otherwise it aborts.
2. **Builds** `<checkout>/stage-4` (the service under test), the closed services `stage-1/`, `stage-2/` and `stage-3/` (these produce real exports for the upgrade probes), the mock web, and the probe runner (Python, Playwright Chromium, axe-core).
3. **Starts everything on one network.** All containers join a single `docker network create --internal` network with no outbound access. The services get PORT plus every provider variable, and the stage-4 service runs with no volume.
4. **Serves the corpora.** The mock serves the sample corpus plus the verifier corpora of stages 1–4. The stage-4 corpora are:
   - `orbit-forge.test` (corroboration, investors, syndication, a lookalike, an unreachable original, epochs 0–2)
   - `lattice-lineage.test` (canonical chains of 3 hops and of 4+ hops, a cycle, invalid lineage lines)
5. **Runs, in order:**
   1. `run4.py --phase main`:
      - every stage-1, stage-2 and stage-3 API probe (`S1-*`, `S2-*`, `S3-*`) with the stage-4 invariants (INV4);
      - D01–D03 (origins, corroboration, investors);
      - E01–E03 (batches);
      - F01 (provider failure);
      - U5 (upgrades from real stage-1/2/3 exports);
      - X1 (stage-4 export/import);
      - SERVED and G.
   2. Restarts:
      - `run4.py --phase s3-pre-restart`, then `docker kill` + `docker start` (idle), then `run4.py --phase s3-post-restart`
      - `run4.py --phase pre-kill` (a batch of three builds running), then `docker kill` + `docker start`, then `run4.py --phase post-kill`
   3. `browser4.py`: every stage-2/3 screen probe (B02–B13, U02) re-run with INV4, plus B14 (investors markup).

Each part prints one line per probe and `TOTAL: n passed, m failed`. The script exits non-zero on any failure.

Environment options: `PART=api|restart|browser|all`, `PROBE_ONLY=D01,E02` (applies to the main and browser parts), `KEEP=1`, `LOGDIR`.

## Columns

- **ID**: `<prefix>-<nn>`, by spec section:
  - I5 preamble invariant
  - O1 Lineage header lines
  - O2 Own pages
  - O3 Origins
  - O4 origin keys of fields
  - V1 Investors
  - V2 Investors on the screens
  - B1 `POST /batches`
  - B2 `GET /batches/{id}`
  - P1 Provider failure
  - R4 Restarts
  - U4 Upgrades

  Other prefixes: `QX4-` export state kinds; `TC4-` earlier rows that change; `TD-` decisions D35–D46.
- **★**: a row a quick reading would miss.
- **Probe**:
  - `D..`, `E..`, `F01`, `U5`, `X1` in `run4.py`; `R-*` restart phases; `B14` browser.
  - `S1-*`/`S2-*`/`S3-*`/`B*` the earlier probes re-run.
  - `INV4` the invariant checker run on every read; `EV4` the corpus oracle (`oracle4.py`: kinds, origins, originals obtained, investor candidates).
  - `LOG` the mock call log used as the oracle of spending; `read` reading at verification time.

## Earlier rows

All rows of `factory/ledger/stage-1.md` (311), `stage-2.md` (184) and `stage-3.md` (123) stay binding, except where a TC4 row below changes them. The earlier probes re-run with INV4.

### Changed rows

| ID | ★ | Earlier row | Change in stage 4 (quoted) | Kind | Probe |
|---|---|---|---|---|---|
| TC4-01 | ★ | T2-01 / TC-01 seven fields | "A dossier has an eighth field, `investors`. The `fields` of every response that lists a dossier's fields hold it, after `executives`" | format | INV4 |
| TC4-02 | ★ | T7-03 feed order within a build | "the feed entries one build adds are numbered with `investors` last" | format | D03 |
| TC4-03 | ★ | Q1-01..Q1-04 kind (stage 2) | "A page counts as kind `own` for a company only when its registrant is the company's domain. Any other page that states `Kind: own` has kind `aggregator`" | format | EV4 (S2 EV2 patched to this rule) |
| TC4-04 | ★ | Q5-06, TC-02 candidate keys | "Candidates gain `origin`" and fields gain `origins`, `corroborated`, `corroborated_since` | format | INV4 |
| TC4-05 | ★ | R7-01 two idempotent paths | "There are three idempotent write paths: stage 1's two and `POST /batches`." | retry | E01, E03 |
| TC4-06 | ★ | R8-13 only two requests make provider calls | "`POST /batches` starts builds, and so joins `POST /dossiers` and `POST /dossiers/{domain}/refresh` as a request that makes provider calls" | cost | E01 (LOG) |
| TC4-07 | ★ | T10-* restarts with no build running; D27 (abandoned builds) | "When builds are running at the stop … each build that was running: Does not stay `building` …" (D43 supersedes D27) | state | R-pre-kill / R-post-kill |
| TC4-08 | ★ | Q14-03, T2-18 `/contested` | "\"no field is contested\" on `/contested` means none of the six fields of §4 is" (also for investors) | ui | B14, B11 |
| TC4-09 | ★ | T9-* upgrades (stage 3) | a stage-4 service accepts stage-1, stage-2 and stage-3 exports (U4-*) | export-state | U5 |
| TC4-10 | ★ | R1-07 80 units per build | invariant 5 adds batch budgets (I5-01, B1-09) | cost | E02, R-post-kill |

## I5 Preamble

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| I5-01 | ★ | intro | "5. Spending never exceeds a budget that this specification or the caller sets." | cost | E02, E03, R-post-kill (LOG), S1 windows (80) |
| I5-02 | | intro | "All requirements from stages 1–3 continue to apply, with the additions below." | behaviour | S1-*, S2-*, S3-*, B* |

## O1 Lineage header lines

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| O1-01 | | lineage | "`Registrant: <domain>` — The domain whose owner publishes the page" | format | EV4 |
| O1-02 | | lineage | "`Canonical: <URL>` — The page is a copy; the URL is the original" | format | EV4, D02 |
| O1-03 | | lineage | "`First-Published-By: <domain>` — The page republishes material first published by that domain" | format | EV4, D01 |
| O1-04 | ★ | lineage | "Domains in these lines, and the host of a `Canonical` URL, are normalised as in §4." | format | D01 (`WWW.Wire.TEST.` → `wire.test`), D02 |
| O1-05 | ★ | lineage | "A page with no valid `Registrant` line has the host of its own URL, normalised, as its registrant." | format | D02 (`Registrant: not a domain!` → oddlines.test) |

## O2 Own pages

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| O2-01 | ★ | own | "A page counts as kind `own` for a company only when its registrant is the company's domain." | format | EV4 |
| O2-02 | ★ | own | "Any other page that states `Kind: own` has kind `aggregator` for the selection rule in `stage-2.md`, and its candidates report `\"kind\": \"aggregator\"`." | format | EV4, D01 (lookalike), D02 (fan site) |
| O2-03 | ★ | own | "A page that states `Kind: own` and whose registrant is not the host of its own URL, normalised, is a **lookalike**: a site presenting itself as a company it is not registered to." | format | D01 (orbitforge.test, registrant orbit-forge-holdings.test) |

## O3 Origins

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| O3-01 | ★ | origins | "Every page has one **origin**, a domain, taken from the first of these that applies" / "Candidates gain `origin`, the origin of their page." | format | INV4, EV4 |
| O3-02 | ★ | origins | "1. Its `First-Published-By` domain." | format | D01 (two syndicated copies → wire.test), D02 (chain end) |
| O3-03 | ★ | origins | "2. When its `Canonical` URL is not the page's own URL, the origin of the page at that URL (its **original**), by these same rules." | format | D01 (mirror → own team page), D02 (3-hop chain → final-origin.test), D01 (self-canonical press page ignored) |
| O3-04 | ★ | origins | "3. The company's domain, when the page is a lookalike." | format | D01 |
| O3-05 | ★ | origins | "4. Its registrant." | format | EV4 |
| O3-06 | ★ | origins | "From the page whose origin is sought, rule 2 follows at most three `Canonical` URLs in a row. Where it would follow a fourth, or where no provider serves a page at the URL, the host of that URL takes the place of the original's origin." | format | D02 (4-hop chain → chain-e.test, not deep-origin.test; 2-cycle → host of the revisited URL), D01 (unreachable gone.test) |
| O3-07 | ★ | origins | "A build obtains from a provider each original that rule 2 needs." | cost | EV4 (each needed original appears in an extract of the build window; gone.test requested) |
| O3-08 | ★ | origins | "Pages with the same origin are one source, however many URLs, providers or kinds they have." | format | D01 (Ember Fund on two URLs of one origin: not a member; founded_year not corroborated) |

## O4 Origin keys of fields

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| O4-01 | | keys | "Each field gains three keys" `origins`, `corroborated`, `corroborated_since` | format | INV4 |
| O4-02 | ★ | keys | "`origins` lists the distinct origins of the candidates whose value is the selected value, sorted ascending. It is `[]` for an `unknown` field." | format | INV4, D01 |
| O4-03 | ★ | keys | "`corroborated` is true when `origins` has two or more entries, otherwise false." | format | INV4, D01 |
| O4-04 | ★ | keys | "`corroborated_since` is the time (§8) of the earliest ready build after which the selected value has had two or more **standing origins**, or null while it has fewer." | format | D03 (ceo since T1), INV4 (corroborated ⇒ not null) |
| O4-05 | ★ | keys | "The standing origins of a selected value are the origins of every candidate with that value that any ready build has gathered since the value became the selected value (the `learned_at` of its latest history entry, stage 3), whether or not a later build gathered it again." | format | D03 (e1: dailyorbit page gone, hq corroborated false but corroborated_since stays T0) |
| O4-06 | ★ | keys | "A new selected value starts with none." | format | D03 (e2: hq Grenoble → corroborated_since null) |
| O4-07 | ★ | keys | "Imported candidates count as gathered at the imported `researched_at`. When a stage-3 export is imported, the candidates of each of its builds count as gathered at that build's time." | export-state | U5 |
| O4-08 | ★ | keys | "Imported candidates whose export records no origin take the host of their URL, normalised, as their origin." | export-state | U5 |
| O4-09 | ★ | keys members | "For `executives` … and `investors` …, these keys follow the field's members. A member's candidates are those with its title and name (`executives`) or with its name (`investors`). `origins` lists the distinct origins of the candidates of all members, sorted ascending. It is `[]` for an `unknown` field." | format | INV4, D01 |
| O4-10 | ★ | keys members | "`corroborated` is true when the candidates of every member have two or more distinct origins, and false otherwise, including for an `unknown` field." | format | INV4, D01 (investors false: Northwind has one origin), D02 (Cobalt Equity: true) |
| O4-11 | ★ | keys members | "`corroborated_since` is the time of the earliest ready build after which every member has had two or more standing origins, or null while some member has fewer or the field is `unknown`. A member's standing origins are the origins of every candidate of that member that the build after which it last became a member, or any later ready build, has gathered, whether or not a later build gathered it again." | format | D02, INV4 |

## V1 Investors

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| V1-01 | ★ | investors | "A dossier has an eighth field, `investors`. The `fields` of every response that lists a dossier's fields hold it, after `executives`" | format | INV4, D03 (history, values) |
| V1-02 | ★ | investors | "and the feed entries one build adds are numbered with `investors` last." | format | D03 |
| V1-03 | ★ | investors | "For Appendix A, `investors` is a field with the statement phrases `investor`, `investors`, `led by`, `backed by` and `participated`. Occurrences of the company's name and of these statement phrases are first taken out of the sentence and separate the words around them." | support | oracle4, INV4, EV4 |
| V1-04 | ★ | investors | "Of the runs of capitalised words (A.4) joined by single spaces that remain, each not part of a longer such run, a run of two or more words whose last word is `Ventures`, `Capital`, `Partners`, `Fund`, `Investments`, `Holdings` or `Equity` is an **investor name**." | support | D01 (Northwind Ventures, Ember Fund, Redwood Partners), D02 (Cobalt Equity, Quarry Capital) |
| V1-05 | ★ | investors | "In an excerpt that contains an amount (A.4), the run that starts directly after `led by` or `backed by` and one space is an investor name too, whatever its length and last word" (`General Atlantic`; `Acme Robotics is led by Dana Ruiz.` names none) | support | D01 (General Atlantic; "Orbit Forge is led by Dana Ruiz." no candidate) |
| V1-06 | ★ | investors | "An investor name normalises to the text as the excerpt writes it. Rules 1 to 4 of A.2 apply; in place of rule 5, an excerpt supports each investor name it contains." | support | D01 (negated "might be backed by Sequoia Holdings" → none), INV4 |
| V1-07 | ★ | investors | "The `value` of a candidate of `investors` is one investor name. A research claim is never a candidate of `investors`." | support | INV4, EV4 |
| V1-08 | ★ | investors | "An investor name is a **member** when, among the field's candidates, one with that name has `kind` `own` or `filing`, or those with that name have two or more distinct origins." | selection | D01, D02, INV4 |
| V1-09 | ★ | investors | "In place of the selection rule in `stage-2.md`, the value is the array of the members' names, sorted by Unicode code point, or null when there is no member." | selection | INV4, D01, D03 |
| V1-10 | ★ | investors | "`investors` is `known` exactly when it has a member, and `unknown` otherwise, in place of the rules that make a field `known` exactly when the evidence supports a value for it." | format | INV4 (never `contested`) |
| V1-11 | ★ | investors | "`selected` is true on every candidate whose name is a member, and false on the others." | selection | INV4, D01 |
| V1-12 | ★ | investors | "`candidates` lists every candidate in the order the selection rule in `stage-2.md` ranks them." | selection | INV4 |
| V1-13 | ★ | investors | "`citations` are, for each member in the order of the value, the `url`, `excerpt` and `provider` of every candidate with its name, in rank order." | selection | INV4 |
| V1-14 | ★ | investors | "A member's `true_from` is the earliest `true_from` that is not null among the candidates with its name, or null when all of them are null. The field's `true_from` is the latest of its members' `true_from`, or null when the value is null or any member's is null." | format | INV4, D01 (2025-06-01) |
| V1-15 | ★ | investors | "`GET /dossiers/{domain}/values` decides membership from the candidates at `true_at` and gives the value, `true_from` and `citations` from them by these rules." | format | S3 VALUES (investors via oracle4), D03 |
| V1-16 | ★ | investors | "A history and feed entry for `investors` is typed by name, in place of the table in `stage-3.md` Changes and corrections. A name in the new value and not in the earlier one counts as a correction when its `true_from` and the earlier value's `true_from` are both not null and its `true_from` is on or before the earlier value's." | behaviour | D03 |
| V1-17 | ★ | investors | "The entry is `correction` when every name in exactly one of the two values counts as a correction, and `change` otherwise." | behaviour | D03 (Atlas Capital added, dated 2023-01-01 ≤ 2025-06-01 → correction) |

## V2 Investors on the screens

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| V2-01 | ★ | screens | "The screens treat `investors` as `stage-3.md` treats `executives`: it takes none of the `data-testid` attributes of `stage-2.md`" | ui | B14, B06 |
| V2-02 | ★ | screens | "and \"no field is contested\" on `/contested` means none of the six fields of §4 is." | ui | B14, B13 |

## B1 `POST /batches`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| B1-01 | | batches | "A batch researches several companies under one shared budget. A batch belongs to the user who created it" | behaviour | E01 |
| B1-02 | | batches | "**An idempotent write path.** `Idempotency-Key` is required; see §7." | retry | E01 |
| B1-03 | ★ | batches | (§7 for this path) replay 200 with the original body; same key with another body 409; concurrent identical requests take effect once | retry | E01, E03 (8 identical posts → one 202, seven 200) |
| B1-04 | | batches | `202 { "batch_id", "state", "budget_units", "spent_units", "dossiers": [ { "domain", "state" } ] }` | format | E01 |
| B1-05 | ★ | batches | "`dossiers` lists the normalised domains in the order given, each with its dossier's state." | format | E01 |
| B1-06 | ★ | batches | "`domains` missing, empty or longer than 50 entries — 422"; "An entry of `domains` invalid after normalisation (§4) — 422"; "Two entries of `domains` the same after normalisation — 422" | error | E01 |
| B1-07 | ★ | batches | "`budget_units` missing, not an integer, below 1 or above 100000 — 422 `validation_failed`" | error | E01 |
| B1-08 | ★ | batches | "A `budget_units` that is not an integer is 422 `validation_failed` whatever its JSON type: a string, `true` or `1.5` included. The row above takes precedence over the 400 `malformed_request` of §5 for a field of the wrong JSON type." | error | E01 |
| B1-09 | ★ | batches | "`spent_units` is the total cost (§9) of the provider calls the batch's builds made. It never exceeds `budget_units`." | cost | E01, E02 (== call log), R-post-kill |
| B1-10 | ★ | batches | "A domain with no dossier gets one, and the batch runs its first build. A domain that already has a dossier is not researched by the batch and costs it nothing." | behaviour | E01 |
| B1-11 | ★ | batches | "Each build in a batch still spends at most 80 units, and its cost also counts in its dossier's `spent_units`." | cost | E01, E02 |
| B1-12 | ★ | batches | "When the budget would be exceeded by a further call, the batch makes no more provider calls, and its remaining builds complete with the pages and research claims they have obtained: each of their fields is `known` exactly when those support a value for it." | cost | E02 (budgets 30, 75, 1: builds end ready) |
| B1-13 | ★ | batches | "`POST /batches` starts builds, and so joins `POST /dossiers` and `POST /dossiers/{domain}/refresh` as a request that makes provider calls" (one build per dossier at a time, R8-04, R8-18) | concurrency | E03 (overlapping batches and a refresh → one research run per domain) |

## B2 `GET /batches/{id}`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| B2-01 | ★ | batches | "another user's batch is 404 `not_found`." | error | E01 |
| B2-02 | | batches | "Returns the batch in the shape above. … Unknown batch is 404 `not_found`." | error | E01 |
| B2-03 | ★ | batches | "`state` is `running` while any of its builds runs, then `done`." | state | E01, E02, R-post-kill |

## P1 Provider failure

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| P1-00 | | failure | "A provider may answer a call with an error (any 5xx status, or 429). The build continues: it may make the same request again, through that provider or another." | retry | F01, S2-A06 |
| P1-01 | ★ | failure | "A build in which every call to one or more providers fails, while `nimble` answers, completes `ready`, with every field `known` that the evidence (§4) reachable through the providers that answer supports." | behaviour | F01 (tavily, kernel, browserbase faulted) |
| P1-02 | ★ | failure | "A build in which every research run fails, while searches and extracts are answered, completes `ready`, with every field `known` that the evidence reachable by search and extract supports." | behaviour | F01 (research error and permanent 429) |
| P1-03 | ★ | failure | "A build in which every call to every provider fails completes `failed` (§8), within the time bound of §8." | timing | F01 (≤ 10 s) |
| P1-04 | | failure | "A call a provider refuses with an error status costs nothing (§9)." | cost | F01, S1-P09 |

## R4 Restarts

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| R4-00 | ★ | restarts | "The restart requirements of `stage-3.md` hold for batches as for the rest of the state. When builds are running at the stop, everything else is still answered as before the stop" | state | R-s3-*, R-post-kill |
| R4-01 | ★ | restarts | "Does not stay `building`. It ends `ready` or `failed` within 10 seconds of `GET /health` first answering 200 after the restart, when each provider call it makes after the restart answers within one second. It may end `failed` although some of its calls succeeded; it then leaves the fields as they were (§8)." | timing | R-post-kill |
| R4-02 | ★ | restarts | "Is one build across the restart: its calls before and after the stop together spend at most 80 units (§9), and a batch's builds together never spend more than its `budget_units`." | cost | R-post-kill |
| R4-03 | ★ | restarts | "Has every unit a provider billed for its calls, before and after the stop, counted in its dossier's `spent_units` and, for a batch's build, in the batch's `spent_units`. They may also count calls that were in flight at the stop and that no provider billed." | cost | R-post-kill (billed ≤ batch spent ≤ budget; dossiers sum to batch) |
| R4-04 | ★ | restarts | "After the restart, `POST /dossiers/{domain}/refresh` starts a new build of each such dossier as it does for any other." | behaviour | R-post-kill |

## U4 Upgrades

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| U4-01 | ★ | upgrades | "A stage-4 service must accept an export produced by the same team's stage-1, stage-2 or stage-3 service, preserving dossiers, candidates, history, the change feed and completed idempotent responses as in `stage-1.md` §10." | export-state | U5 |
| U4-02 | ★ | upgrades | "A stage-3 export keeps its builds: after the upgrade, `?as_of=` and `/values` answer from them as the stage-3 service did, with the keys this stage adds." | export-state | U5 (stage-3 history and feed unchanged; as_of carries origins) |
| U4-03 | ★ | upgrades | "Citations carried in the imported state remain citations served to this service." | export-state | U5, SERVED |
| U4-04 | ★ | upgrades | "An export of a stage-1, stage-2 or stage-3 service has no `investors` candidates. After its import, `investors` is `unknown`, in the imported state and in every build kept from the export, and has no history entry" | export-state | U5 |
| U4-05 | ★ | upgrades | "the first build that completes `ready` with a value for it adds a `change`, or an `initial` entry when it is the dossier's first build that completes `ready`." | export-state | U5 |

## QX4 Export/import — state kinds that leave the service in stage 4

| ID | ★ | Requirement | Kind | Probe |
|---|---|---|---|---|
| QX4-01 | ★ | batches (id, owner, state, budget, spent, dossiers) survive: `GET /batches/{id}` identical | export-state | X1 |
| QX4-02 | ★ | candidate origins survive | export-state | X1 |
| QX4-03 | ★ | standing-origin state survives: `corroborated_since` identical after import | export-state | X1 |
| QX4-04 | ★ | investors candidates, history and feed entries survive | export-state | X1 |
| QX4-05 | | earlier state kinds (builds, versions, history, feed, tokens, idempotency) as in stage 3 | export-state | S3-C04, S1-P15 |

## TD Planner decisions

| ID | ★ | Decision | Text (from decisions.md, summarised by the planner) | Kind | Probe |
|---|---|---|---|---|---|
| TD-35 | | D35 | all earlier decisions continue except that D43 supersedes D27 for builds running at a stop; earlier folders byte-identical | delivery | run_all (D35 check) |
| TD-36 | ★ | D36 | kind from the rendered header with stage-2 defaults; `own` only if the registrant (valid normalised Registrant, else normalised URL host) is the company's domain, else `aggregator`; lookalike = states `Kind: own` and registrant ≠ normalised host of its own URL | format | EV4 |
| TD-37 | ★ | D37 | origin rules in order; Canonical compared after trimming, lower-casing scheme/host, ignoring fragment; at most three hops; fourth hop / unreachable / cycle → normalised host of that URL; originals obtained once per build with the cheapest call whose header lines are those of the rendered text | format | EV4, D01, D02 |
| TD-38 | ★ | D38 | standing origins and corroborated_since per field and per member since it last became selected; persisted and exported; `?as_of=` snapshots carry the three keys; `/values` keeps the stage-3 shape for eight fields | format | D03, X1 |
| TD-39 | ★ | D39 | investors per the spec (phrases, name rules, rules 1–4, rendered text only, one candidate per url/provider/name with the first supporting sentence, research never; members; sorted value; never contested) | support | D01, D02, INV4 |
| TD-40 | ★ | D40 | POST /batches → 202 {batch_id ≤ 64 chars, state, budget_units, spent_units, dossiers}; `done` when no started build runs (also when every domain existed); replay 200 original body; another user's/unknown batch 404; 401 first | format | E01 |
| TD-41 | ★ | D41 | worst-case reservation before every call against 80 and the batch budget; a stopped build ends `ready`; existing dossiers cost nothing; a refresh of a dossier whose batch build runs starts nothing and counts to the batch; batch spent = sum of its builds' settled spending ≤ budget | cost | E02, E03 |
| TD-42 | ★ | D42 | 5xx and 429 cost 0, retried up to 4 attempts in all (1.1 s); research failing alone → ready; every call failing → failed within the §8 bound | retry | F01 |
| TD-43 | ★ | D43 | in-flight reservations written durably; on start-up, before /health answers 200, running builds are closed `failed` with fields/history/feed unchanged, settled spending plus in-flight reservations added to dossier and batch; batch `done` when all its builds ended; later refresh as usual | state | R-post-kill |
| TD-44 | ★ | D44 | stage-4 export: format_version 1, track "dossier", plus batches, origins, standing-origin state, investors; import accepts four shapes; imported candidates without origin take the URL host; stage-1/2 candidates count at researched_at, stage-3 at their build's time; investors unknown in imported state; kinds as exported | export-state | U5, X1 |
| TD-45 | ★ | D45 | UI keeps exactly the six stage-2 field testids; executives and investors in separate markup; `/contested` six fields only | ui | B13, B14 |
| TD-46 | | D46 | cap stays 80; originals and investor pages compete for budget; re-measure discovery; the cost auditor compares with 9.377 | cost | (cost auditor), S1 windows |

## Rows added by the blind re-derivation

From `factory/reviews/stage-4-blind.md`.

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| O3-09 | ★ | origins | (consequence of "From the page whose origin is sought, rule 2 follows at most three `Canonical` URLs in a row") the hop budget counts from the page whose origin is sought, not afresh at each original | format | D02 (stops at chain-e.test, not deep-origin.test) |
| V1-18 | ★ | investors | (consequence of the typing rule) a name removed from the value always makes the entry a `change` | behaviour | history oracle (`oracle4.investors_change_type`), read |
| V1-19 | ★ | investors | (stage-3 "For a selected value, it is the time of the build that made it the selected value") the field's `learned_at` is the time of the build that made the current array selected; null when `unknown` | format | INV4, D03 |
| V1-20 | | investors | field shape `{ "value": [...], "status", "true_from", "learned_at", "citations", "candidates", "origins", "corroborated", "corroborated_since" }` | format | INV4 |

## Probe index

| Probe | Covers |
|---|---|
| S1-*, S2-*, S3-* | every earlier API probe re-run with INV4 (eight fields, origins keys, investors rules) |
| D01 | orbit-forge.test e0: syndication, mirror copy, lookalike, unreachable original, self-canonical; corroboration; investors members |
| D02 | lattice-lineage.test: 3-hop chain, 4th hop, 2-cycle, invalid lineage lines, fan site `Kind: own` |
| D03 | orbit timeline e0–e2: standing origins, corroborated_since, new value resets, investors correction by name, as_of keys |
| E01 | batches: validation table, shape, ownership, 401/404, idempotency, existing dossiers cost nothing |
| E02 | budget exhaustion (budgets 30, 75, 1): mock log total ≤ budget, batch spent == log, each build ≤ 80, builds end ready |
| E03 | burst of identical and overlapping batches plus a refresh: one build per domain |
| F01 | other providers failing, research failing (5xx and 429), every call failing within 10 s, refusals cost 0 |
| U5 | upgrades from real stage-1/2/3 exports (closed services) |
| X1 | stage-4 export/import round trip |
| R-s3-pre/post-restart | stage-3 restart guarantees re-run on stage 4 |
| R-pre-kill / R-post-kill | batch of three builds killed mid-build: not building within 10 s of health, billed ≤ spent ≤ budget, ≤ 80 per build, refresh afterwards |
| B02..B14, U02 | screens (B14: investors markup) |

## Row count

110 rows: 83 new stage-4 specification rows, 5 export state rows, 10 changed earlier rows, 12 planner-decision rows; 95 marked ★. The 311 stage-1, 184 stage-2 and 123 stage-3 rows remain binding except as changed by TC4-01..TC4-10.
