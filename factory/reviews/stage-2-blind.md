# Blind re-derivation — dossier stage 2

The two longest new sections of `spec/stage-2.md` are **Web access** (47 lines) and
**Candidates** (44 lines). Their normative statements were listed again from the
specification text, without the ledger open, and then compared with
`factory/ledger/stage-2.md`. Statements the ledger did not have as their own row are marked
**NEW** and appended to the ledger as Q3-10..Q3-15 and Q5-16..Q5-17.

## Web access

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| W-01 | An extract through `nimble` may ask Nimble to load the page in a browser and serve the browser text (no control activated) via `provider_options={"render": True}`. | Q3-01 |
| W-02 | Two optional browser vendors are available in addition to the §2 providers: `kernel` (open_browser), `browserbase` (open_browser, browse). | Q3-02 |
| W-03 | A service may use Nimble's rendered extract alone; neither browser vendor is required. | Q3-03 |
| W-04 | The deployment provides `KERNEL_API_KEY`, `KERNEL_BASE_URL`, `BROWSERBASE_API_KEY`, `BROWSERBASE_BASE_URL`. | Q3-04 |
| W-05 | WebRouter reads the keys from the environment. | **NEW** → Q3-10 |
| W-06 | A service using the vendors passes their base URLs in `provider_config`, beside those of §2. | Q3-05 |
| W-07 | Rendered Nimble extract: 3 units per URL requested, including a URL with no page. | Q3-06 |
| W-08 | Open a session through `kernel`: 0. | **NEW** → Q3-11 (Q3-07 lumped four table rows together) |
| W-09 | Open a session through `browserbase`: 2. | **NEW** → Q3-12 |
| W-10 | Each page served to a session, through either: 1. | **NEW** → Q3-13 |
| W-11 | Browse run through `browserbase`: 4. | **NEW** → Q3-14 |
| W-12 | A failed open, a failed page load and releasing a session cost nothing. | Q3-08 |
| W-13 | Each provider keeps at most 4 sessions open; opening another is answered with an error. | Q3-09 |
| W-14 | A session with no connected client for 60 seconds is closed by the provider. | **NEW** → Q3-15 (Q3-09 lumped it with W-13) |

## Candidates

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| C-01 | A candidate is one value for one field, supported by one excerpt of one page. | Q5-01 |
| C-02 | Every value a page of the evidence supports for a field is a candidate, once for each such page. | Q5-02 |
| C-03 | The evidence also holds the page each research claim cites, whether or not the citation supports the claim; the build reads it like any other page. | Q5-03 |
| C-04 | A research claim whose citation does not support it is not a candidate. | Q5-04 |
| C-05 | A candidate's `provider` is a provider that served the text of its excerpt; any of several may be given. | Q5-05 |
| C-06 | Each field gains `candidates` (shape as in the example). | Q5-06 |
| C-07 | `url`, `excerpt`, `provider` follow the §4 citation rules. | Q5-07 |
| C-08 | `kind` is the page's kind; `published_at` its publication time or null. | Q5-08 |
| C-09 | Only an imported candidate has a null `kind`. | Q5-09 |
| C-10 | ★ An imported candidate's null `kind` has the authority of `aggregator` in the selection rule. | **NEW** → Q5-16 (Q5-09 named it, but nothing checked the ranking consequence) |
| C-11 | `retrieved_at` is the time of the build that gathered the candidate. | Q5-10 |
| C-12 | `selected` is true on exactly one candidate (the one the rule picks), false on the others. | Q5-11 |
| C-13 | `candidates` lists the candidates of the last build that completed `ready`. | Q5-12 |
| C-14 | They are listed in rank order, the selected one first. | Q5-13 |
| C-15 | A field with no candidate has `"candidates": []` and is `unknown`. | Q5-14 |
| C-16 | Two values are the same when equal as JSON values; strings are compared exactly after trimming. | Q5-15 |
| C-17 | ★ Consequence of C-02: one page that supports two different values for a field (two sentences) yields two candidates from that page. | **NEW** → Q5-17 (probed by A02 kestrel funding, two values on one filing page) |

## Result

8 statements added to the ledger: Q3-10..Q3-15 and Q5-16..Q5-17. Nothing in the ledger contradicts the re-derived list.

Q5-02 ("once for each such page") and decision D19 ("one candidate per (url, provider, value)") disagree only when two providers serve the same page. Under D1 and D14 the service uses Nimble alone, so that case cannot arise; it is recorded here and needs no row.
