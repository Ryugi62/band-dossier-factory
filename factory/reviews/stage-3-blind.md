# Blind re-derivation — dossier stage 3

The two longest new sections of `spec/stage-3.md` are **Executives** (65 lines) and
**`GET /dossiers/{domain}/values`** (41 lines). Their normative statements were listed again
from the specification text, without the ledger open, and then compared with
`factory/ledger/stage-3.md`. Statements without their own row are marked **NEW**; they are
appended to the ledger as T2-19..T2-21 and T5-14.

## Executives

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| E-01 | A dossier has a seventh field `executives`, listed after the six fields in every response that lists fields. | T2-01 |
| E-02 | A research run still asks for the six fields only. | T2-02 |
| E-03 | Value: an array of `{title, name}`, one per title with a selected person, in the order cfo, coo, cto (the members). | T2-03 |
| E-04 | No title with a selected person: value null, field `unknown`. | T2-04 |
| E-05 | Each title is an Appendix A field with its statement phrases and the format and normalisation of `ceo`; its own phrases replace those of `ceo`. | T2-05 |
| E-06 | ★ Consequence of E-05: in a title's name format, only the company name and that title's phrases are taken out of the sentence. The `ceo` phrases and other titles' phrases stay, and as uppercase words (`CEO`) or lowercase words they separate names. | **NEW** → T2-21 |
| E-07 | An executives candidate is a candidate of one title: `title` beside `value`, and `value` is the person's name. | T2-06 |
| E-08 | A research claim is never an executives candidate. | T2-07 |
| E-09 | Field shape as in the example: `value`, `status`, `true_from`, `learned_at`, `citations`, `candidates`. | **NEW** → T2-20 |
| E-10 | ★ The selection rule runs separately over the candidates of each title, so one title's authority or recency never affects another title. | **NEW** → T2-19 (T2-08 had only the `selected` flag) |
| E-11 | `selected` is true on the highest-ranked candidate of each title, false on the others. | T2-08 |
| E-12 | `candidates` are listed by title (cfo, coo, cto), then in rank order. | T2-09 |
| E-13 | `citations`: per member in order, every candidate with the member's title and name, in rank order. | T2-10 |
| E-14 | `status`: unknown / contested (some title has two or more names) / known. | T2-11 |
| E-15 | A candidate's `learned_at` is the first build that gathered the same (title, name, URL, provider). | T2-12 |
| E-16 | A member's `true_from` is its title's selected candidate's; the field's `true_from` is the latest member's, or null when any is null. | T2-13 |
| E-17 | `/values` chooses each title's person from the candidates at `true_at` by these rules. | T2-14 |
| E-18 | History and feed entries for executives are typed by title; definition of a title that differs. | T2-15 |
| E-19 | Correction per title, and the entry type over all differing titles. | T2-16 |
| E-20 | Stage-2 testids name only the six fields; executives uses other markup. | T2-17 |
| E-21 | `/contested`: "no field is contested" means none of the six is. | T2-18 |

## `GET /dossiers/{domain}/values`

| # | Statement (from the spec) | Ledger row |
|---|---|---|
| V-01 | Returns, per field, the value that the evidence the service had at `as_of` says held on `true_at`. | T5-01 |
| V-02 | `as_of` defaults to the current time. | T5-09 |
| V-03 | A page version is what one ready build gathered from one URL: its candidates and its `true_from`. | T5-02 |
| V-04 | The versions known at `as_of` come from ready builds at or before `as_of`, in build order; each holds from its `true_from`. | T5-02 |
| V-05 | A later version replaces earlier versions of the URL whose `true_from` is on or after its own. | T5-03 |
| V-06 | The latest earlier version it does not replace stops holding on the later version's `true_from`. | T5-04 |
| V-07 | A null-dated version holds from no date; a later null-dated version replaces every earlier version. | T5-05 |
| V-08 | A gathered version with no candidates still replaces or ends earlier versions. | T5-06 |
| V-09 | ★ Consequence of V-05..V-08: versions are replaced or ended only by later versions **of the same URL**. A dated version of a page that later builds no longer gather keeps holding. | **NEW** → T5-14 (C01: the dated headcount page is gone after e1, yet `/values` on 2026-02-15 still gives 11-50 while GET shows `unknown`) |
| V-10 | The candidates at `true_at` are those of every holding version; value by the selection rule; `true_from` that of the chosen candidate. | T5-07 |
| V-11 | Response shape `{domain, true_at, as_of, fields}`. | T5-08 |
| V-12 | No candidate at `true_at`: `value` null, `true_from` null, `citations` []; citations are the candidates at `true_at` with the chosen value. | T5-10 |
| V-13 | Bad `true_at` or `as_of` → 422. | T5-11 |
| V-14 | No dossier, or no ready build at or before `as_of` → 404. | T5-12 |
| V-15 | Imported state: builds and versions as Upgrades gives. | T5-13 |

## Result

4 statements added: T2-19, T2-20, T2-21 and T5-14. Nothing in the ledger contradicts the re-derived list.

One ambiguity stays open: V-07, "holds from no date". The probes accept both readings (see the note in the ledger); a planner decision is requested.
