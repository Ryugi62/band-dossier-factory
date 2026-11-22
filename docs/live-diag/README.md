# Live-web diagnostic after the run (not seat output, not part of the submitted factory run)

Written by the human operator on 19 November 2026 after the factory run, to test the cause named in `FACTORY.md`
("What did not work"). The stage folders are unchanged; the patch is stored here only and was applied to a local build.

| File | What it is |
|---|---|
| `diag2.json`, `diag3.json` | unchanged stage 4, live Nimble, runway.com and stripe.com: `ready`, 80 units, 8 of 8 fields `unknown` |
| `live-budget-fix.patch` | at most 6 plain page probes in flight; a page keeps its slot until its render is done (+1 unit test) |
| `fix2-runway.com.json`, `fix2-stripe.com.json` | the same two domains with the patch, `ready`, 79 and 80 units |
| `run.sh` | the command used (needs a Nimble key in `NIMBLE_API_KEY`; spends live units) |

Measured fields (`status` is the service's own label; **not checked against ground truth**, and at least one is wrong):

| Domain | Units | known | contested | unknown |
|---|---|---|---|---|
| runway.com, unchanged | 79 | 0 | 0 | 8 |
| runway.com, patched | 79 | 2 (founded_year, executives) | 2 | 4 |
| stripe.com, unchanged | 80 | 0 | 0 | 8 |
| stripe.com, patched | 80 | 3 (legal_name, ceo, founded_year) | 3 | 2 |

Read this as: the budget split was a real cause (0 filled fields to 4 (runway.com) and 6 (stripe.com) of 8 for the same 80 units), but live quality is
poor: stripe.com `founded_year` 2021 is wrong (Stripe was founded in 2010), runway.com `ceo` "Board Member" is not a name.
Units per filled field here are 79/4 = 19.8 and 80/6 = 13.3, against the mock-web figures of 5.6 to 9.4, and fields are not
verified. This diagnostic is not counted in any stage figure, not rerun through the factory, and is not claimed as a result.
