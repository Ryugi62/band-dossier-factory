# Blind re-derivation — dossier stage 4

The two longest new sections of `spec/stage-4.md` are **Investors** (60 lines) and **Origins**
(56 lines). Their normative statements were listed again from the specification text, without the
ledger open, and then compared with `factory/ledger/stage-4.md`. Statements without their own row
are marked **NEW**; they are appended to the ledger as O3-09 and V1-18..V1-20.

## Origins

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| G-01 | Every page has one origin, a domain, from the first rule that applies. | O3-01 |
| G-02 | Rule 1: its First-Published-By domain. | O3-02 |
| G-03 | Rule 2: when Canonical is not the page's own URL, the origin of the original by the same rules. | O3-03 |
| G-04 | Rule 3: the company's domain for a lookalike. | O3-04 |
| G-05 | Rule 4: its registrant. | O3-05 |
| G-06 | A build obtains from a provider each original that rule 2 needs. | O3-07 |
| G-07 | At most three Canonical URLs in a row from the page whose origin is sought; a fourth, or a URL with no page served, uses that URL's host. | O3-06 |
| G-08 | ★ Consequence of G-07: the three-hop budget is counted from the page whose origin is sought. The original's origin is computed with the hops that remain, not with a fresh budget, so a long chain stops at the fourth URL even though its last page names another origin. | **NEW** → O3-09 (D02: chain A→B→C→D→E stops at chain-e.test although E says First-Published-By deep-origin.test) |
| G-09 | Pages with the same origin are one source. | O3-08 |
| G-10 | Candidates gain `origin`; fields gain origins / corroborated / corroborated_since. | O3-01, O4-01 |
| G-11 | `origins`: distinct origins of the selected value's candidates, sorted; `[]` when unknown. | O4-02 |
| G-12 | `corroborated`: two or more origins. | O4-03 |
| G-13 | `corroborated_since`: earliest ready build after which there were two or more standing origins; null while fewer. | O4-04 |
| G-14 | Standing origins: every candidate with the value gathered since it became selected, whether or not regathered. | O4-05 |
| G-15 | A new selected value starts with none. | O4-06 |
| G-16 | Imported candidates count as gathered at researched_at; stage-3 builds at their own times. | O4-07 |
| G-17 | Imported candidates without an origin take their URL's normalised host. | O4-08 |
| G-18 | For executives and investors the keys follow the members (origins over all members, corroborated when every member has two or more, since when every member has had two or more standing origins; member standing origins since it last became a member). | O4-09..O4-11 |

## Investors

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| I-01 | An eighth field, after executives; feed entries numbered with investors last. | V1-01, V1-02 |
| I-02 | Statement phrases `investor`, `investors`, `led by`, `backed by`, `participated`; the company name and phrases are taken out. | V1-03 |
| I-03 | Investor name: a maximal run of two or more capitalised words ending in one of the seven words. | V1-04 |
| I-04 | With an amount in the excerpt, the run directly after `led by` / `backed by` is a name whatever its length. | V1-05 |
| I-05 | Normalisation: text as written; rules 1–4 of A.2; the excerpt supports each name it contains. | V1-06 |
| I-06 | A candidate's value is one name; research claims are never candidates. | V1-07 |
| I-07 | Member: an own/filing candidate, or two or more distinct origins. | V1-08 |
| I-08 | Value: the members' names sorted by code point, or null. | V1-09 |
| I-09 | `known` exactly when a member exists, otherwise `unknown`. | V1-10 |
| I-10 | Field shape as in the example, including `true_from`, `learned_at`, `origins`, `corroborated`, `corroborated_since`. | **NEW** → V1-20 |
| I-11 | `selected` is true on every candidate of a member. | V1-11 |
| I-12 | Candidates in rank order. | V1-12 |
| I-13 | Citations per member in value order, each in rank order. | V1-13 |
| I-14 | Member and field `true_from`. | V1-14 |
| I-15 | `/values` decides membership from the candidates at `true_at`. | V1-15 |
| I-16 | History and feed typed by name; correction rule for added names; entry type over the names in exactly one value. | V1-16, V1-17 |
| I-17 | ★ Consequence of I-16: the correction test is defined only for names in the new value, so a name **removed** from the value always makes the entry a `change`. | **NEW** → V1-18 |
| I-18 | ★ Consequence (stage-3 Two times per value with I-08): the field's `learned_at` is the time of the build that made the current array the selected value; `learned_at` is null when `unknown`. | **NEW** → V1-19 |
| I-19 | Screens: no stage-2 testids; `/contested` six fields only. | V2-01, V2-02 |

## Result

4 statements added: O3-09 and V1-18..V1-20. Nothing in the ledger contradicts the re-derived list.
