# Requirement ledger — dossier stage 2

Source: `sf-2026/challenges/dossier/spec/stage-2.md` (333 lines), with `stage-1.md` carried
forward, plus planner decisions D12–D22 (`factory/decisions.md`). Written by the verifier from
the specifications only; the shipped checks were not opened.

## How to run every probe (one command)

```sh
factory/probes/stage-2/run_all.sh /path/to/result-repo-checkout
```

The script does the following:

- Checks that `stage-1/` is byte-identical to `9166a28` (D22).
- Builds `<checkout>/stage-2` (the service under test), `<checkout>/stage-1` (the closed stage-1 service, used only for the upgrade probe), the mock web, and the probe-runner image `factory/probes/stage-2/browser/Dockerfile`. The runner image has Python, Playwright Chromium and axe-core, and is built with network access.
- Starts the mock web, both services and the runner on one `docker network create --internal` network, so nothing has outbound access at run time.
- Mounts the sample corpus plus the verifier corpora: `factory/probes/stage-1/corpus` and `factory/probes/stage-2/corpus`.
- Runs, in order:
  1. `run2.py`: the stage-1 probes re-run against stage 2 with stage-2 invariants, then the stage-2 API probes, the upgrade probe and the provenance checks.
  2. `browser.py`: the screens, in a real headless Chromium.

Each run prints one line per probe and ends with `TOTAL: n passed, m failed`. The script exits non-zero when any probe fails.

Environment:

- `SF_ROOT` (default `<workdir>/sf-2026`)
- `PROBE_ONLY=A02,B06` (a subset; the stage-1 probes are named `S1-P06` and so on)
- `PART=api|browser|all`
- `KEEP=1`
- `LOGDIR` for logs and screenshots

## Columns

- **ID**: `Q<section>-<nn>`. The spec sections are numbered in order of appearance:
  - Q0 preamble
  - Q1 Page kind and publication time
  - Q2 Page text
  - Q3 Web access
  - Q4 Rate limits
  - Q5 Candidates
  - Q6 The selection rule
  - Q7 Status
  - Q8 Screens
  - Q9 Product and visual direction
  - Q10 Signup and login
  - Q11 Dossier list
  - Q12 Dossier screen
  - Q13 Evidence
  - Q14 Contested fields
  - Q15 Refresh and competing clients
  - Q16 Existing clients after an upgrade

  Other prefixes: `QX-` export/import state kinds; `QD-` planner decisions; `QC-` stage-1 rows whose expected behaviour changes.
- **★**: a row a quick reading would miss.
- **Kind**: behaviour, error, format, timing, concurrency, retry, state, cost, support, selection, ui, ui-quality, export-state, reading.
- **Probe**:
  - `A..` API probes in `run2.py`; `B..` browser probes in `browser.py`; `U..` upgrade probes.
  - `S1-*` the stage-1 probes re-run.
  - `INV2` the stage-2 dossier invariant checker, run on every dossier read.
  - `EV2` the corpus evidence oracle.
  - `LOG` mock call-log checks.
  - `SERVED` provenance of every excerpt.
  - `G` global response checks.
  - `read` reading at verification time; `shot` a screenshot reviewed by the verifier.

## Stage-1 rows

All rows of `factory/ledger/stage-1.md` stay binding, except those listed under "Changed
stage-1 rows" below.

- **Re-run as probes.** The stage-1 probes run against stage 2 as `S1-P00` … `S1-P18`, `S1-SERVED` and `S1-G`. The invariant checker is replaced by INV2, and the cost window accepts 3 units per URL for rendered extracts (D13).
- **Read at verification.** Stage-1 rows marked `read` in the stage-1 ledger are re-read on `stage-2/`: R2-08..R2-12, R2-19, R3-02, R6-13, R8-10..R8-12, R2-27.

### Changed stage-1 rows

| ID | ★ | Stage-1 row | Change in stage 2 (quoted) | Kind | Probe |
|---|---|---|---|---|---|
| QC-01 | ★ | R4-23 "`status` is `known` when `value` is not null, and `unknown` when it is." | "`status` is now one of three values: `known` … `contested` … `unknown`" | format | INV2 |
| QC-02 | ★ | R4-24/R4-25 citations of a known field | "its `citations` are the `url`, `excerpt` and `provider` of every candidate with that value, in rank order" | selection | INV2 |
| QC-03 | ★ | R4-40 "When the evidence supports more than one value for a field, the field holds one of them" (and D3) | replaced by the selection rule: "A field's selected value is the one the selection rule below picks from the field's candidates" | selection | INV2, A02 |
| QC-04 | ★ | R4-28 evidence | "The evidence now also holds the page that each research claim of the evidence cites, whether or not the citation supports its claim: a build reads that page as it reads any other." | support | EV2 (A01) |
| QC-05 | ★ | R4-33/R4-35 citation text = served text, prose | "a page's **text** is the text a browser shows once the page has loaded … a citation's excerpt must appear in the page's text" | support | SERVED, A04 |
| QC-06 | ★ | R4-14 "A dossier has exactly these six fields" / R4-50 field shape | "Each field gains `candidates`" | format | INV2 |
| QC-07 | ★ | R9-15 "An extract through `nimble` does not set `render`." | "From this stage an extract through `nimble` may ask Nimble to load the page in a browser … `provider_options={\"render\": True}`" (3 units per URL) | cost | LOG (S1 window patched) |
| QC-08 | ★ | R8-09 10 s bound | "Time a build spends waiting to make a call again after a 429 does not count toward the 10 seconds" | timing | A06 (no time bound asserted under 429) |
| QC-09 | ★ | R10-11..R10-19 export state kinds | candidates are new state that leaves the service: see QX rows | export-state | A07 |
| QC-10 | ★ | R6-09 "Every other endpoint requires a bearer token" | with D18 the UI document for `Accept: text/html` on the browser routes needs none; API requests stay 401 | behaviour | A08 |
| QC-11 | | R8-35/R8-36 list `legal_name` | "`GET /dossiers` (§8) is unchanged. The `legal_name` it lists is the selected value." | format | A02, S1-P12 |

## Q0 Preamble

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q0-01 | | intro | "The stage-1 requirements continue to apply, with the additions below." | behaviour | S1-* |
| Q0-02 | | intro | "A dossier now keeps every value its evidence supports, as candidates, and selects one per field by a fixed rule." | selection | EV2, INV2 |
| Q0-03 | ★ | intro | "3. A field's selected value is the one the selection rule below picks from the field's candidates" | selection | INV2 |
| Q0-04 | ★ | intro | "the same candidates always yield the same value." | selection | INV2 (deterministic rank), A02 (refresh with unchanged web keeps the selection) |

## Q1 Page kind and publication time

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q1-01 | | kind | "`Kind: own`, `Kind: filing`, `Kind: news`, `Kind: aggregator` — The page's **kind**: the company's own site, a filing registry, a news report, or an aggregator of company data" | format | EV2 (kind equals the page's Kind line) |
| Q1-02 | | kind | "`Published: <RFC 3339 timestamp>` — When the page was published" | format | EV2 (published_at equals the instant) |
| Q1-03 | ★ | kind | "A page with no `Kind` line, or with a value not listed above, is of kind `own` when the host of its URL, normalised as `stage-1.md` normalises a domain, is the company's domain" | format | A02 (kestrel `/legal`: no Kind line → `own`) |
| Q1-04 | ★ | kind | "and of kind `aggregator` otherwise." | format | A02 (kestrel `dronedirectory.test`: `Kind: blog` → `aggregator`) |
| Q1-05 | ★ | kind | "A page with no `Published` line, or with a value that is not an RFC 3339 timestamp, has no publication time." | format | A02 (kestrel `Published: sometime in 2019` → null) |

## Q2 Page text

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q2-01 | ★ | text | "From this stage, a page's **text** is the text a browser shows once the page has loaded, without clicking controls." | support | SERVED (excerpt in served text), A04 (rendered text, D13) |
| Q2-02 | | text | "Activating disclosure controls is not required." | behaviour | — (permission) |
| Q2-03 | | text | "Evidence (§4) is read from page text so defined" | support | EV2 |
| Q2-04 | ★ | text | "and a citation's excerpt must appear in the page's text." | support | SERVED |
| Q2-05 | ★ | text | "A citation's `provider` is the provider that served the text the excerpt was copied from." | support | SERVED (provider of the serving call) |

## Q3 Web access

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q3-01 | | web | "an extract through `nimble` may ask Nimble to load the page in a browser and serve the text the browser shows once the page has loaded, with no control activated: `provider_options={\"render\": True}` on WebRouter's extract." | behaviour | LOG (A04) |
| Q3-02 | | web | "Two optional browser vendors are also available … `kernel`, through `open_browser`; `browserbase`, through `open_browser` and `browse`." | behaviour | LOG (notes any use; D14) |
| Q3-03 | | web | "A service may use Nimble's rendered extract alone to obtain every page's browser text; neither browser vendor is required." | behaviour | — |
| Q3-04 | | web env | "`KERNEL_API_KEY` … `KERNEL_BASE_URL` … `BROWSERBASE_API_KEY` … `BROWSERBASE_BASE_URL`" provided by the deployment | delivery | run_all.sh passes all four |
| Q3-05 | | web | "A service that uses these vendors passes their base URLs to WebRouter in `provider_config`" | delivery | read |
| Q3-06 | ★ | cost | "Extract through `nimble` that loads the page in a browser — 3 per URL requested, including a URL for which no page is returned" | cost | LOG (spent_units == log cost; render extract cost == 3 × urls) |
| Q3-07 | | cost | "Open a session through `kernel` — 0"; "Open a session through `browserbase` — 2"; "Each page served to a session, through either — 1"; "Browse run through `browserbase` — 4" | cost | LOG (spent_units == log cost) |
| Q3-08 | | cost | "A failed open, a failed page load and releasing a session cost nothing." | cost | LOG |
| Q3-09 | | sessions | "Each provider keeps at most 4 sessions open at once; opening another is answered with an error. A session that no client has been connected to for 60 seconds is closed by the provider." | behaviour | — (provider property; D14 no sessions) |

## Q4 Rate limits

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q4-01 | ★ | rate | "From this stage a provider may answer any call with 429." | retry | A06 (weather on; `rate_limit` fault on extract, search, research) |
| Q4-02 | ★ | rate | "A call answered 429 costs nothing (`stage-1.md` §9)." | cost | A06 (spent_units == log cost; 429 entries cost 0) |
| Q4-03 | ★ | rate | "The same call (the same provider, operation and arguments) made again less than one second after a 429 for it was answered is answered 429 again." | retry | A06 (with a permanent `rate_limit` fault every call needs 4 attempts; the build still gathers every candidate) |
| Q4-04 | ★ | rate | "No call is answered 429 more than three times in a row, except that opening a session while its provider keeps 4 open (Web access) is answered 429 until one of them closes." | retry | A06 |
| Q4-05 | ★ | rate | "Time a build spends waiting to make a call again after a 429 does not count toward the 10 seconds of `stage-1.md` §8." | timing | A06 (bound = 10 s + 3.5 s per refusal round) |
| Q4-06 | ★ | rate + §4 | (consequence with R4-29/R4-31) under 429s a build still makes exactly one successful search whose query is exactly the domain | retry | A06, S1-P18 |

## Q5 Candidates

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q5-01 | | cand | "A **candidate** is one value for one field, supported by one excerpt of one page." | support | INV2 (excerpt supports value) |
| Q5-02 | ★ | cand | "Every value that a page of the evidence (§4) supports for a field is a candidate of that field, once for each such page." | support | EV2 (every (url, value) the evidence supports is a candidate; no duplicate (url, provider, value)) |
| Q5-03 | ★ | cand | "The evidence now also holds the page that each research claim of the evidence cites, whether or not the citation supports its claim: a build reads that page as it reads any other." | support | EV2 (nordlicht: registry page and claim-cited pages) |
| Q5-04 | ★ | cand | "A research claim whose citation does not support it is still not a candidate." | support | A01 (nordlicht: unsupported funding/headcount claims stay out) |
| Q5-05 | ★ | cand | "A candidate's `provider` is a provider that served the text its excerpt is taken from; when several did, any of them may be given." | support | SERVED |
| Q5-06 | | cand | "Each field gains `candidates`" with keys `value`, `url`, `excerpt`, `provider`, `kind`, `published_at`, `retrieved_at`, `selected` | format | INV2 |
| Q5-07 | | cand | "`url`, `excerpt` and `provider` follow the citation rules in §4." | support | INV2, SERVED |
| Q5-08 | ★ | cand | "`kind` is the page's kind, and `published_at` its publication time or null." | format | EV2, A02 |
| Q5-09 | ★ | cand | "Only an imported candidate (below) has a null `kind`; it has the authority of `aggregator`." | format | INV2 (built dossiers: kind never null), U01 |
| Q5-10 | ★ | cand | "`retrieved_at` is the time of the build that gathered the candidate (§8, Builds)." | format | INV2 (== researched_at of the last ready build), A02 (clock moved during build) |
| Q5-11 | ★ | cand | "`selected` is true on exactly one candidate of a field that has candidates, the one the rule picks, and false on the others." | selection | INV2 |
| Q5-12 | ★ | cand | "`candidates` lists the candidates of the last build that completed `ready`" | state | A05 (during a refresh and after a failed refresh the old candidates stay) |
| Q5-13 | ★ | cand | "in the order the selection rule ranks them, the selected one first." | selection | INV2 |
| Q5-14 | | cand | "A field with no candidate has `\"candidates\": []` and is `unknown`." | format | INV2 |
| Q5-15 | ★ | cand | "Two values are the same value when they are equal as JSON values; strings are compared exactly, after removing surrounding whitespace." | selection | INV2 (status / citations grouping) |

## Q6 The selection rule

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q6-01 | ★ | rule | "1. **Authority** of the page's kind: `own` and `filing` rank equal and highest, then `news`, then `aggregator`." | selection | A02 (kestrel ceo: older own beats newer news; legal_name: own beats newer aggregator; funding: filing beats aggregator) |
| Q6-02 | ★ | rule | "2. **Recency** within the same authority: the later `published_at` ranks higher." | selection | A02 (kestrel hq_city: Bergen 2025-09 beats Oslo 2025-05, offsets compared as instants) |
| Q6-03 | ★ | rule | "A candidate without a publication time ranks below every candidate of the same authority that has one." | selection | A02 (kestrel founded_year: 2002 with a date beats 2001 without) |
| Q6-04 | ★ | rule | "3. **URL**: when authority and publication time are equal, the candidate whose `url` is smaller, comparing the strings by Unicode code point, ranks higher" | selection | A02 (kestrel headcount: `/a-careers` beats `/b-jobs`) |
| Q6-05 | | rule | "between two candidates with the same URL, they rank by provider in the order `nimble`, `tavily`, `kernel`, `browserbase`." | selection | INV2 |
| Q6-06 | ★ | rule | "4. **Value**: between two candidates with the same URL and provider, the one whose value is smaller ranks higher: integers compare as numbers, strings by Unicode code point after removing surrounding whitespace." | selection | A02 (kestrel funding: 15000000 before 20000000 on one page) |
| Q6-07 | | rule | "The highest-ranked candidate is the selected one." | selection | INV2 |
| Q6-08 | | rule | "The field's `value` is the selected candidate's value" | selection | INV2 |
| Q6-09 | ★ | rule | "and its `citations` are the `url`, `excerpt` and `provider` of every candidate with that value, in rank order." | selection | INV2 |
| Q6-10 | ★ | rule | "A candidate of lower authority is selected only when no candidate of higher authority exists for that field." | selection | A02 (kestrel hq_city: newest aggregator Tromsø not selected) |
| Q6-11 | ★ | rule | "The rule runs over all of a field's candidates." | selection | INV2 |

## Q7 Status

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q7-01 | | status | "`known` — The field has candidates, and they all have the same value" | format | INV2 |
| Q7-02 | ★ | status | "`contested` — The field's candidates carry two or more different values" | format | INV2, A02 (all six kestrel fields contested) |
| Q7-03 | | status | "`unknown` — The field has no candidate; `value` is null" | format | INV2 |
| Q7-04 | ★ | status | "A `contested` field still has a selected `value` and its citations." | format | INV2 |
| Q7-05 | ★ | status | "`GET /dossiers` (§8) is unchanged. The `legal_name` it lists is the selected value." | format | A02 (list legal_name of kestrel == "Kestrel Dynamics AS") |

## Q8 Screens

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q8-01 | | screens | "The following screens must be reachable by URL. Other screens must be reachable through the UI." | ui | A08, B12 (every route rendered) |
| Q8-02 | | screens | "Server-side and client-side rendering are both permitted." | ui | — |
| Q8-03 | | route | "`/` — The dossier list with search, and a form to research a domain" | ui | B04, B05 |
| Q8-04 | | route | "`/dossiers/{domain}` — One dossier: its state, its six fields with their values, status and citations, a refresh and a reload" | ui | B06, B07 |
| Q8-05 | | route | "`/dossiers/{domain}/evidence` — Every candidate of every field of that dossier" | ui | B10 |
| Q8-06 | | route | "`/contested` — Every contested field across all dossiers" | ui | B11 |
| Q8-07 | | route | "`/signup` — Signup" | ui | B03 |
| Q8-08 | | route | "`/login` — Login" | ui | B02 |
| Q8-09 | ★ | screens | "The browser and the API share `/dossiers/{domain}`. Return the UI for `Accept: text/html`; API requests without that header receive JSON." | behaviour | A08 |
| Q8-10 | | screens | "`/`, `/dossiers/{domain}/evidence` and `/contested` are browser routes; they read the API's dossier data." | ui | B10, B11 (values equal API) |
| Q8-11 | ★ | screens | "The domain in a browser route is normalised as in §4." | ui | B06 (`/dossiers/WWW.Zephyr-Quantum.TEST` shows `zephyr-quantum.test`), B10 |
| Q8-12 | | screens | "The UI must expose the `data-testid` attributes listed below for integration testing. Additional elements are permitted" | ui | B02..B11 |

## Q9 Product and visual direction

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q9-01 | | quality | "The browser experience must feel like a coherent, presentation-ready research product, not a thin wrapper of raw controls." | ui-quality | shot, read |
| Q9-02 | | quality | "a reader opening a dossier should see at a glance which fields are known, which are unknown and which are contested, and where each value came from." | ui-quality | shot, B06 |
| Q9-03 | | quality | "A field's value and its status must be the clearest information on the dossier screen, with its citations directly beside it." | ui-quality | shot |
| Q9-04 | | quality | "Fields, citations, candidates and contested fields should be easy to scan, and status, provider, page kind and publication time should be understandable without interpreting raw API data." | ui-quality | shot, B10 (visible text of a candidate is not the raw RFC 3339 string alone) |
| Q9-05 | | quality | "Use a consistent visual system for typography, spacing, colour, controls and feedback." | ui-quality | shot |
| Q9-06 | | quality | "Primary actions — research, refresh — must be easy to identify." | ui-quality | shot |
| Q9-07 | ★ | quality | "Known, unknown, contested, building, failed, loading, successful, refused and uncertain states must be visually distinct as well as satisfying the behavioural requirements below." | ui-quality | B12 (computed style of field rows differs by status), shot |
| Q9-08 | ★ | quality | "Format names, years, headcount ranges, money and timestamps for people first; expose technical identifiers only where they help the user." | ui-quality | B06 (funding not shown as bare `12500000`; researched_at not the raw RFC 3339 string), shot |
| Q9-09 | ★ | quality | "Each citation shows its excerpt as quoted text and links to its URL." | ui | B06 |
| Q9-10 | ★ | quality | "The required flows must remain clear and usable at a 375 CSS-pixel viewport and at conventional desktop widths, without horizontal page scrolling." | ui-quality | B12 (scrollWidth ≤ viewport at 375 and 1280 on every route) |
| Q9-11 | ★ | quality | "Inputs need visible labels" | ui-quality | B12 (axe `label`; every input has a visible label) |
| Q9-12 | ★ | quality | "keyboard focus must be apparent" | ui-quality | B12 (focused control's outline/box-shadow differs from unfocused) |
| Q9-13 | ★ | quality | "and text and controls need sufficient contrast." | ui-quality | B12 (axe `color-contrast`, WCAG AA) |
| Q9-14 | | quality | "Provide considered empty, loading and error states" | ui-quality | B04 (empty-dossiers), B11 (empty-contested), shot |
| Q9-15 | | quality | "and keep navigation consistent across the required routes." | ui-quality | B12 (a nav with links to `/` and `/contested` on every signed-in route), shot |
| Q9-16 | | quality | "A custom illustration, brand asset or exact visual match to a reference is not required." | ui-quality | — |

## Q10 Signup and login

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q10-01 | | auth | "`signup-email`, `signup-password`, `signup-display-name` — Inputs"; "`signup-submit` — Button" | ui | B03 |
| Q10-02 | | auth | "`login-email`, `login-password`, `login-submit` — Inputs and button" | ui | B02 |
| Q10-03 | ★ | auth | "`auth-error` — Error message. Present only when there is one" | ui | B02, B03 (absent before, present after a refusal) |
| Q10-04 | ★ | auth | "`current-user` — Visible on every screen when signed in. Text contains the display name" | ui | B12 (every route) |
| Q10-05 | | auth | "`logout-button` — Button" | ui | B02 |

## Q11 Dossier list — `/`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q11-01 | | list | "`research-domain` — Input for the domain to research" | ui | B05 |
| Q11-02 | | list | "`research-submit` — Button. Sends `POST /dossiers`" | ui | B05 |
| Q11-03 | ★ | list | "`research-error` — Error message, when the request is refused — including an invalid domain" | ui | B05 |
| Q11-04 | ★ | list | "`research-uncertain` — Shown when the outcome of a research request is unknown (below)" | ui | B08 |
| Q11-05 | | list | "`dossier-search` — Input. Filters the list as `q` does on `GET /dossiers`" | ui | B04 (results equal API `q`, incl. a legal-name match) |
| Q11-06 | | list | "`dossier-list` — Container. Children ordered by domain ascending" | ui | B04 |
| Q11-07 | ★ | list | "`dossier-item-{domain}` — One per listed dossier. Carries `data-state=\"{state}\"`. Text contains the domain, and the legal name when known. Links to `/dossiers/{domain}`" | ui | B04 |
| Q11-08 | ★ | list | "`empty-dossiers` — Shown instead of the list when no dossier matches" | ui | B04 |
| Q11-09 | ★ | list | "A research request that succeeds, with 202 or 200, opens `/dossiers/{domain}` for the normalised domain." | ui | B05 |
| Q11-10 | ★ | list | "A domain that already has a dossier, including one created by another client after this browser read the list, opens that dossier and starts no build." | ui | B05 (LOG: no research run) |

## Q12 Dossier — `/dossiers/{domain}`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q12-01 | | dossier | "`dossier-domain` — Text is exactly the normalised domain" | ui | B06 |
| Q12-02 | | dossier | "`dossier-state` — Text is exactly `building`, `ready` or `failed`" | ui | B06, B07 |
| Q12-03 | | dossier | "`dossier-spent` — Formatted `spent_units`. Carries `data-units=\"{integer}\"`" | ui | B06 |
| Q12-04 | ★ | dossier | "`dossier-researched-at` — Text contains `researched_at`, formatted. Absent when it is null" | ui | B06 (absent on a failed first build) |
| Q12-05 | ★ | dossier | "`field-{field}` — One per field, six in all, in the order of the table in `stage-1.md` §4. Carries `data-status=\"{status}\"`" | ui | B06 |
| Q12-06 | ★ | dossier | "`field-value-{field}` — The formatted value. Carries `data-value` (below). Present only when the value is not null" | ui | B06 |
| Q12-07 | ★ | dossier | "`field-contested-{field}` — A marker. Present only when the field is `contested`" | ui | B06 (kestrel and zephyr) |
| Q12-08 | | dossier | "`field-citations-{field}` — Container of the field's citations, in API order" | ui | B06 |
| Q12-09 | ★ | dossier | "`citation-{field}-{n}` — The field's `n`th citation, counting from 1. Text contains the excerpt. Contains a link whose `href` is the citation's `url`. Carries `data-provider=\"{provider}\"`" | ui | B06 |
| Q12-10 | | dossier | "`dossier-evidence-link` — Link to `/dossiers/{domain}/evidence`" | ui | B06 |
| Q12-11 | | dossier | "`dossier-refresh` — Button. Sends `POST /dossiers/{domain}/refresh`" | ui | B07 |
| Q12-12 | ★ | dossier | "`refresh-error` — Error message, when a refresh is refused" | ui | B07 (dossier removed by a reset → 404) |
| Q12-13 | ★ | dossier | "`refresh-uncertain` — Shown when the outcome of a refresh is unknown (below)" | ui | B07 |
| Q12-14 | ★ | dossier | "`dossier-reload` — Button. Reads the dossier again without starting a build" | ui | B09 (LOG: no provider call) |
| Q12-15 | ★ | dossier | "`dossier-not-found` — Shown instead of the fields when no dossier exists for the domain" | ui | B06 (absent domain and invalid domain, D18) |
| Q12-16 | ★ | dossier | "`data-value` is the API value as text: a string value unchanged, an integer in plain decimal digits." | ui | B06, B10 |
| Q12-17 | ★ | dossier | "While the dossier's state is `building`, the screen reads the dossier again at least every 2 seconds until the state is `ready` or `failed`" | timing | B06 (gaps between reads ≤ 2.5 s while building; reading stops after) |
| Q12-18 | ★ | dossier | "and then shows the new fields without a manual reload." | ui | B06 |

## Q13 Evidence — `/dossiers/{domain}/evidence`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q13-01 | | evidence | "`evidence-{field}` — One container per field, six in all. Children in API `candidates` order" | ui | B10 |
| Q13-02 | ★ | evidence | "`candidate-{field}-{n}` — The field's `n`th candidate, counting from 1. Text contains the formatted value and the excerpt. Carries `data-value`, `data-provider`, `data-kind`, `data-url`, `data-published-at` (the RFC 3339 `published_at`, empty when null) and `data-selected=\"true\"` or `\"false\"`" | ui | B10 |
| Q13-03 | ★ | evidence | "`evidence-empty-{field}` — Shown instead of candidates when the field has none" | ui | B10 (nordlicht legal_name) |

## Q14 Contested fields — `/contested`

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q14-01 | ★ | contested | "`contested-list` — Container. Children ordered by domain ascending, then by field in the order of the table in `stage-1.md` §4" | ui | B11 |
| Q14-02 | ★ | contested | "`contested-item-{domain}-{field}` — One per contested field of any dossier. Carries `data-value` for the selected value. Text contains the domain, the field and every distinct candidate value. Links to `/dossiers/{domain}/evidence`" | ui | B11 |
| Q14-03 | ★ | contested | "`empty-contested` — Shown instead of the list when no field is contested" | ui | B11 |

## Q15 Refresh and competing clients

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q15-01 | ★ | refresh | "After any successful action, the data on the same page must show the new state without a manual reload." | ui | B07 (after refresh: state building then ready, new spent shown) |
| Q15-02 | ★ | refresh | "Navigation must wait for the write to succeed before it refreshes the data." | ui | B05 (dossier screen shows the dossier, not not-found, when the POST is delayed) |
| Q15-03 | | refresh | "Any mechanism is fine, including a full navigation." | ui | — |
| Q15-04 | | refresh | "there is no live-update requirement: another client may change state, but this browser need only read again after its own action, an explicit reload or a build it is waiting on." | ui | — |
| Q15-05 | ★ | refresh | "`dossier-reload` reads the dossier again. **Latest read wins:** a delayed earlier read must not overwrite a later one, including when responses arrive out of order." | concurrency | B09 |
| Q15-06 | ★ | refresh | "This applies to the reads while a dossier is `building` as well." | concurrency | B09 (a delayed poll answer arriving after a newer one) |
| Q15-07 | ★ | refresh | "Another client may refresh a dossier after this browser reads it. A refresh from this browser while that build runs is answered 202 like any other and the screen follows the running build to its end." | ui | B07 |
| Q15-08 | ★ | refresh | "If a research or refresh response is lost, including after the request commits, show `research-uncertain` or `refresh-uncertain` (nonempty text), not `research-error` or `refresh-error`." | retry | B07, B08 (forward then abort) |
| Q15-09 | ★ | refresh | "Keep the request retryable with the **same key and body**." | retry | B07, B08 (retry carries the same Idempotency-Key and body) |
| Q15-10 | ★ | refresh | "A successful retry removes both the error and the uncertainty elements, shows the dossier, and starts at most one build." | retry | B07, B08 (LOG: one research run) |
| Q15-11 | | refresh | "Unknown outcomes are not confirmed refusals." | retry | B07, B08 |
| Q15-12 | | refresh | "No background polling beyond the reading while `building`, live synchronization, or recovery across page reloads is required." | ui | — |

## Q16 Existing clients after an upgrade

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q16-01 | ★ | upgrade | "A stage-2 service must accept an export produced by the same team's stage-1 service." | export-state | U01 (export from the stage-1 service at 9166a28, import into stage 2 → 204) |
| Q16-02 | ★ | upgrade | "A browser signed in before that export/import upgrade must remain signed in afterwards." | export-state | U02 (browser holding the stage-1 token stays signed in) |
| Q16-03 | ★ | upgrade | "Imported dossiers appear in the list and on their screens." | export-state | U01 (API), U02 (screens) |
| Q16-04 | ★ | upgrade | "Each imported field gains one candidate for every value that text the providers served to the dossier's last stage-1 build that completed `ready` supports for that field (`stage-1.md` §4), once for each page whose served text supports it." | export-state | U01 (per D16: one candidate per exported citation) |
| Q16-05 | ★ | upgrade | "The candidate's excerpt is taken from that text and supports the value" | export-state | U01, INV2 |
| Q16-06 | ★ | upgrade | "its `provider` is the provider that served that text, its `kind` and `published_at` are as the exported state records them or else null, and its `retrieved_at` is the dossier's `researched_at`." | export-state | U01 |
| Q16-07 | ★ | upgrade | "Each imported field's `value`, `status` and `citations` then follow from its candidates by the selection rule and Status, as after a build." | export-state | U01, INV2 |
| Q16-08 | ★ | upgrade | "A research or refresh request whose response was lost before export remains retryable after import with the same body and key; the UI must recover the original response and show the imported dossier." | retry | U01 (API replay → 200 original body), U02 (UI) |
| Q16-09 | | upgrade | "These requirements apply when import completes between browser requests; migration during an in-flight request is not required. No page reload or new screen is required." | export-state | U02 |
| Q16-10 | ★ | upgrade | "The candidates of an imported dossier are replaced by those of its next completed build." | export-state | U01 (refresh after import → kinds non-null, EV2) |

## QX Export / import (one row per kind of state that leaves the service in stage 2)

| ID | ★ | Section | Requirement | Kind | Probe |
|---|---|---|---|---|---|
| QX-01 | ★ | §10 + Q5 | candidates (value, url, excerpt, provider, kind, published_at, retrieved_at, selected) survive a stage-2 export/import unchanged | export-state | A07 |
| QX-02 | ★ | §10 + Q7 | status `contested` and the selected value survive export/import | export-state | A07 |
| QX-03 | ★ | §10 | a mid-build export holds the candidates of the last ready build | export-state | A07 |
| QX-04 | ★ | §10 + Q16 | tokens, users, idempotent records and failed keys from a stage-1 export are valid in stage 2 | export-state | U01 |
| QX-05 | | §10 (D17) | stage-2 export keeps `track: "dossier"`, `format_version: 1` | export-state | A07 |

## QD Planner decisions (binding interpretations)

| ID | ★ | Decision | Text (from decisions.md) | Kind | Probe |
|---|---|---|---|---|---|
| QD-12 | ★ | D12 | "D1, D2, D4, D5, D6, D9, D10, D11 continue. D3 … is replaced by the spec's selection rule. D8 is revised: the page cited by a research claim is gathered and read like any page" | behaviour | S1-*, EV2 |
| QD-13 | ★ | D13 | "Every excerpt of every candidate must appear in the browser text of its page, obtained by a Nimble extract with `render: True` (3 units per URL)." | support | A04 (each candidate URL rendered in that build; excerpt in the rendered text) |
| QD-14 | | D14 | "Not used. Tavily stays unused (D1)." | cost | LOG (note only) |
| QD-15 | ★ | D15 | "A call answered 429 is repeated after waiting at least 1.1 s, up to 4 attempts in all … the stage-1 rule that stops retrying about 5 s into a build … is removed" | retry | A06 |
| QD-16 | ★ | D16 | "one candidate per exported citation whose excerpt supports the field's value under Appendix A …; `provider` as exported; `kind` null … `published_at` null; `retrieved_at` = `researched_at`; a field with value null has no candidates." | export-state | U01 |
| QD-17 | ★ | D17 | "`format_version` stays 1, `track` \"dossier\". The stage-2 state stores candidates; import accepts both shapes" | export-state | A07, U01 |
| QD-18 | ★ | D18 | "A request whose `Accept` header lists `text/html` for `/`, `/signup`, `/login`, `/dossiers/{domain}`, `/dossiers/{domain}/evidence`, `/contested` receives the UI document with status 200 and no bearer check …; sends a signed-out visitor to `/login`. … A domain that is invalid or has no dossier shows `dossier-not-found`." | behaviour | A08, B02, B06 |
| QD-19 | ★ | D19 | "One candidate per (url, provider, value) of a field: the first supporting sentence of the page's browser text, in text order, is its excerpt." | support | EV2 (excerpt == first supporting sentence) |
| QD-20 | ★ | D20 | "A request that produced no HTTP response (network error, abort, timeout) or a 5xx is uncertain; any HTTP 4xx is a refusal" | retry | B07, B08 (abort → uncertain; 5xx → uncertain; 404/422 → error) |
| QD-21 | ★ | D21 | "All UI code, styles and fonts are inside the image; no CDN, no web fonts from the network; system font stack." | delivery | B12 (no request leaves the service origin), read |
| QD-22 | ★ | D22 | "`git diff 9166a28 -- stage-1` must be empty at every stage-2 commit" | delivery | run_all.sh (aborts otherwise) |

## Rows added by the blind re-derivation

From `factory/reviews/stage-2-blind.md`.

| ID | ★ | Section | Requirement (verbatim) | Kind | Probe |
|---|---|---|---|---|---|
| Q3-10 | | web | "WebRouter reads the keys from the environment." | delivery | read |
| Q3-11 | | cost | "Open a session through `kernel` — 0" | cost | LOG (spent_units == log cost) |
| Q3-12 | | cost | "Open a session through `browserbase` — 2" | cost | LOG |
| Q3-13 | | cost | "Each page served to a session, through either — 1" | cost | LOG |
| Q3-14 | | cost | "Browse run through `browserbase` — 4" | cost | LOG |
| Q3-15 | | sessions | "A session that no client has been connected to for 60 seconds is closed by the provider." | behaviour | — (provider property; D14 no sessions) |
| Q5-16 | ★ | cand | "Only an imported candidate (below) has a null `kind`; **it has the authority of `aggregator`**." | selection | INV2 (rank key treats null as aggregator), U01 |
| Q5-17 | ★ | cand | (consequence of "Every value that a page of the evidence (§4) supports for a field is a candidate of that field, once for each such page") one page supporting two values of a field yields two candidates | support | A02 (kestrel funding: 15M and 20M from one filing page) |

## Probe index

| Probe | File | Covers |
|---|---|---|
| S1-P00..S1-P18, S1-SERVED, S1-G | run2.py (imports stage-1 run.py) | every stage-1 probe, with INV2/EV2 and render costs patched in |
| A01 | run2.py | claim-cited pages are evidence; unsupported claims are not candidates (nordlicht) |
| A02 | run2.py | selection rule, kind/published defaults, retrieved_at, contested status, list legal_name (kestrel) |
| A04 | run2.py | D13: candidate excerpts from rendered extracts made by the build |
| A05 | run2.py | candidates of the last ready build during and after a failed refresh |
| A06 | run2.py | rate limits: weather, permanent 429 on extract / search+research |
| A07 | run2.py | stage-2 export/import keeps candidates; mid-build export |
| A08 | run2.py | Accept: text/html on every browser route; API stays JSON/401; no external assets |
| U01 | run2.py | stage-1 export (service built from stage-1/ = 9166a28) imported into stage 2 |
| B02..B12 | browser.py | login/signup, list/search/research, dossier screen, polling, refresh/uncertain/retry, latest read wins, evidence, contested, quality (375 px, axe label/contrast, focus, nav, local assets) |
| U02 | browser.py | browser holding the stage-1 token stays signed in; a research lost on stage 1 is recovered after the upgrade |
| SERVED | run2.py | every citation and candidate excerpt was served for its url, from prose, by the named provider |
| G, G-UI | both | no 5xx, error envelope, JSON content type, timeouts |

## Row count

184 rows: 157 new stage-2 specification rows, 5 export/import state rows, 11 changed stage-1 rows, 11 planner-decision rows; 114 marked ★. The 311 stage-1 rows remain binding except as changed by QC-01..QC-11.
