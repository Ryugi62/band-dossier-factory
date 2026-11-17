# Cost audit — stage 1, round 1

Commit audited: `f72df407766174680d78a792ea83081f7ba24041` (fresh clone, `docker build` of `stage-1/`,
no outbound network: service and mock web on a `docker network create --internal` network; the
mock `dossier-web` with the sample corpus is the only reachable host). Auditor: cost-auditor.

**Decision: ACCEPT** (first round, so there is no earlier figure for the 10% rule).

## Workload (fixed; reuse it next round)

For each of the 12 companies of `sf-2026/challenges/dossier/web/corpus/sample` and for epochs 0 and 1:
mock `POST /_mock/reset {"epoch": e}`, service `POST /_test/reset`, login, `POST /dossiers`, poll
`GET /dossiers/{domain}` until not `building`, then `GET /_mock/log`. 24 builds, one build each.
Every build's `spent_units` equalled the sum of the `cost` column of the mock log (24 of 24).

## Figures

| Measure | Value |
|---|---|
| Builds / all ended `ready` | 24 / 24 |
| Units total | 766 |
| Provider calls | 190 (7.9 per build) |
| Units per build | mean 31.9, min 27, **max 34** (cap 80) |
| Known fields / correct known fields | 137 / 137 |
| **Units per correct output item** | **5.59** |
| Duplicates (identical successful calls in a build) | 0 |
| Wall time per build | 0.20-0.44 s |

Units per call kind:

| Kind | Calls | Units | Share |
|---|---|---|---|
| nimble research | 24 | 600 | 78.3% |
| nimble search `lite` | 114 (24 domain searches, 90 field searches) | 114 | 14.9% |
| nimble extract | 52 | 52 | 6.8% |
| nimble search `fast`/`deep`, tavily (anything) | 0 | 0 | 0% |

A value counted as correct when every excerpt it cites (a) is in text the log shows a call returned for that
URL, and (b) supports the value under the verifier's independent Appendix A oracle
(`factory/probes/stage-1/appendix_a.py`). All 137 known fields passed both tests.

Per company, epoch 0 / epoch 1 (units, calls, field searches, extracts, known fields):

| Domain | Units | Calls | Field searches | Extracts | Known |
|---|---|---|---|---|---|
| ashgrove-solar.test | 32 / 32 | 8 / 8 | 5 / 5 | 1 / 1 | 5 / 5 |
| brightwater-labs.test | 33 / 33 | 9 / 9 | 5 / 5 | 2 / 2 | 6 / 5 |
| corvid-security.test | 32 / 32 | 8 / 8 | 3 / 3 | 3 / 3 | 6 / 6 |
| ferncliff-foods.test | 34 / 34 | 10 / 10 | 5 / 5 | 3 / 3 | 5 / 5 |
| halvorsen-robotics.test | 34 / 34 | 10 / 10 | 3 / 3 | 5 / 5 | 6 / 6 |
| larkspur-health.test | 34 / 34 | 10 / 10 | 6 / 6 | 2 / 2 | 6 / 6 |
| mosaic-freight.test | 27 / 27 | 3 / 3 | 1 / 1 | 0 / 0 | 6 / 6 |
| ostrava-mobility.test | 32 / 32 | 8 / 8 | 5 / 5 | 1 / 1 | 6 / 6 |
| pemberton-analytics.test | 33 / 33 | 9 / 9 | 3 / 3 | 4 / 4 | 6 / 6 |
| quillmate.test | 32 / 32 | 8 / 8 | 3 / 3 | 3 / 3 | 5 / 5 |
| tidemark-energy.test | 28 / 30 | 4 / 6 | 2 / 4 | 0 / 0 | 6 / 6 |
| windrush-bakery.test | 31 / 31 | 7 / 7 | 3 / 3 | 2 / 2 | 6 / 6 |

(Field searches here = lite searches after the domain search.) These match the builder's host-run figures for
the same twelve companies.

The largest single unit of work is 34 units (ferncliff-foods, halvorsen-robotics, larkspur-health, both
epochs): 42.5% of the 80-unit cap.

## Calls that bought nothing used

A call is counted when no excerpt cited in the final dossier appears in any text it returned.

| Kind | Calls | Units | Note |
|---|---|---|---|
| research | 8 of 24 builds | 200 | The 25-unit run is required by D2; in these builds no cited excerpt came from the run. Not a builder defect. |
| extract | 18 of 52 | 18 | Speculative extracts of snippet-cut pages that were then not cited (cityfeed, the-weekly-roundup, supplierfinder, vendorlist and `/leadership`/`/executive-team` pages). |
| search `lite` (field) | 8 of 90 | 8 | Field searches for a field a page elsewhere already supplied, or that returned only uncited pages. |
| search `lite` (domain) | 2 builds (larkspur) | 2 | Required by §4: exactly one search per build has the domain as its query. Not waste. |

Non-research waste: 28 units of 766 (3.7%). No identical call was repeated in any build.

## Other measurements

- **Refresh** (ashgrove, same epoch): the second build spent 32 units again (8 calls) and `spent_units`
  went 32 -> 64. Cap per build holds; spending is cumulative as D4/D5 say.
- **Replays, reads, listing, export, and `POST /dossiers` for an existing domain written as
  `www.ASHGROVE-SOLAR.TEST.`**: 0 provider calls (log length unchanged at 8, then 16 after the one refresh). A refresh replay: 200, 0 calls.
- **Rate-limit weather on** (mock `weather` true, all 12 companies, epoch 0): all 12 builds `ready` with the same
  units as without weather (27-34), refused calls (20 of them across 10 builds) cost 0, no duplicate successful call,
  the same known fields.
- Nothing but `nimble` research, `nimble` lite search and `nimble` extract at 1 unit per URL was called. No
  Tavily call, no `fast`/`deep` search, no `render`.

## Support check (§4 step 4)

All 137 known fields: every cited excerpt appears (whitespace collapsed) in text that a logged call returned for
the same URL: 0 not served, 0 not supporting.

Re-confirmed by the cheapest single retrieval (one 1-unit nimble extract per URL through `web_router`, 12 units,
12 of 12 confirmed, each excerpt inside the page's prose):

| Epoch | Company | Field | Value | URL |
|---|---|---|---|---|
| 0 | ashgrove-solar | legal_name | Ashgrove Solar GmbH | ashgrove-solar.test/about |
| 0 | ashgrove-solar | ceo | Marcus Mensah | ashgrove-solar.test/team |
| 0 | ashgrove-solar | founded_year | 2019 | startupindex.test/companies/ashgrove-solar |
| 0 | ashgrove-solar | headcount_range | 11-50 | startupindex.test/companies/ashgrove-solar |
| 0 | ashgrove-solar | funding_total | 21500000 | businessbeat.test/2025/09/ashgrove-solar-eyes-new-markets |
| 0 | brightwater-labs | hq_city | Columbus | companies-register.test/entity/70797957 |
| 1 | ashgrove-solar | legal_name | Ashgrove Solar GmbH | ashgrove-solar.test/about |
| 1 | ashgrove-solar | hq_city | Cork | ashgrove-solar.test/about |
| 1 | ashgrove-solar | ceo | Marcus Mensah | ashgrove-solar.test/team |
| 1 | ashgrove-solar | founded_year | 2019 | startupindex.test/companies/ashgrove-solar |
| 1 | ashgrove-solar | headcount_range | 11-50 | startupindex.test/companies/ashgrove-solar |
| 1 | corvid-security | funding_total | 84000000 | businessbeat.test/2025/11/corvid-security-eyes-new-markets |

## Advisory (no finding; for the next round)

1. 78% of all units are the mandatory 25-unit research run (D2). Its answer was used in 16 of 24 builds. Nothing
   cheaper exists inside the specification while D2 stands.
2. The type (b) extracts (relevant pages whose snippet was cut short) were uncited 18 of 52 times. Preferring
   pages whose snippet already contains a statement phrase for a missing field would drop most of them (up to
   18 units over the workload, 2.3%). Not required.

Nothing in this round exceeds the cap, lacks a served excerpt, or repeats a call, so the 10% rule has no
previous round to compare against; this round (5.59 units per correct item) becomes the baseline.
