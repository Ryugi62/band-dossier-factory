import unittest

from dossier import pages, support
from dossier.timeline import change_type, instant, new_entries, snapshot_index, spent_upto, values_at, view_fields

D = "lumen.test"


def cand(field, value, url, true_from, kind="own", title=None, published=None):
    c = {"field": field, "value": value, "url": url, "excerpt": f"{value} at {url}", "provider": "nimble",
         "kind": kind, "published_at": published, "true_from": true_from, "retrieved_at": "2026-03-01T09:00:00+00:00",
         "learned_at": "2026-03-01T09:00:00+00:00"}
    if title:
        c["title"] = title
    return c


def build(time, cands, versions=None, outcome="ready", spent=30):
    return {"time": time, "outcome": outcome, "spent": spent, "candidates": cands,
            "versions": versions if versions is not None else {c["url"]: c["true_from"] for c in cands}}


T0, T1, T2 = "2026-03-01T09:00:00+00:00", "2026-03-02T09:00:00+00:00", "2026-03-03T09:00:00+00:00"


class History(unittest.TestCase):
    def test_initial_then_change_and_correction(self):
        b0 = build(T0, [cand("ceo", "Rita Gomes", "https://lumen.test/team", "2021-01-01"),
                        cand("funding_total", 8000000, "https://news.test/seed", "2025-06-10", "news")])
        b1 = build(T1, [cand("ceo", "Tiago Neves", "https://lumen.test/team", "2026-02-01"),
                        cand("funding_total", 9000000, "https://news.test/seed", "2025-06-01", "news")])
        builds = [b0, b1]
        self.assertEqual([(f, e["type"]) for f, e in new_entries(builds, 0)],
                         [("ceo", "initial"), ("funding_total", "initial")])
        self.assertEqual([(f, e["type"]) for f, e in new_entries(builds, 1)],
                         [("ceo", "change"), ("funding_total", "correction")])

    def test_same_value_adds_nothing_and_disappearance_is_a_change(self):
        b0 = build(T0, [cand("hq_city", "Porto", "https://lumen.test/about", "2020-05-01"),
                        cand("headcount_range", "11-50", "https://agg.test/x", "2025-03-01", "aggregator")])
        b1 = build(T1, [cand("hq_city", "Porto", "https://lumen.test/about", "2026-03-01")])
        entries = new_entries([b0, b1], 1)
        self.assertEqual([(f, e["type"], e["value"], e["citations"]) for f, e in entries],
                         [("headcount_range", "change", None, [])])

    def test_failed_build_is_skipped_when_comparing(self):
        b0 = build(T0, [cand("ceo", "Rita Gomes", "https://lumen.test/team", "2021-01-01")])
        failed = build(T1, [], {}, outcome="failed", spent=0)
        b2 = build(T2, [cand("ceo", "Rita Gomes", "https://lumen.test/team", "2021-01-01")])
        self.assertEqual(new_entries([b0, failed, b2], 2), [])

    def test_executives_typed_by_title(self):
        old = {"value": [{"title": "cfo", "name": "Ana Silva"}, {"title": "cto", "name": "Bruno Costa"}],
               "member_true_from": {"cfo": "2021-01-01", "cto": "2026-02-01"}}
        corrected = {"value": [{"title": "cfo", "name": "Ana Silva"}, {"title": "cto", "name": "Bruna Costa"}],
                     "member_true_from": {"cfo": "2021-01-01", "cto": "2021-01-01"}}
        added = {"value": old["value"] + [{"title": "coo", "name": "Marta Reis"}],
                 "member_true_from": dict(old["member_true_from"], coo="2026-01-15")}
        self.assertEqual(change_type("executives", old, corrected), "correction")
        self.assertEqual(change_type("executives", old, added), "change")

    def test_learned_at_comes_from_history(self):
        b0 = build(T0, [cand("legal_name", "Lumen S.A.", "https://lumen.test/about", "2020-05-01")])
        b1 = build(T1, [cand("legal_name", "Lumen S.A.", "https://lumen.test/about", "2026-03-01")])
        history = {"legal_name": [dict(new_entries([b0], 0)[0][1])]}
        fields = view_fields(b1, history, 1)
        self.assertEqual((fields["legal_name"]["learned_at"], fields["legal_name"]["true_from"]), (T0, "2026-03-01"))
        self.assertIsNone(fields["ceo"]["learned_at"])


class AsOfAndValues(unittest.TestCase):
    def test_snapshot_takes_last_build_at_or_before_as_of(self):
        builds = [build(T0, []), build(T1, []), build(T1, [], spent=5), build(T2, [], outcome="failed", spent=2)]
        self.assertEqual(snapshot_index(builds, instant("2026-03-02T04:00:00-05:00")), 2)
        self.assertIsNone(snapshot_index(builds, instant("2026-03-01T08:59:59+00:00")))
        self.assertEqual(snapshot_index(builds, instant(T2)), 2)
        self.assertEqual(spent_upto(builds, instant(T2)), 67)

    def test_page_versions_replace_and_end(self):
        team = "https://lumen.test/team"
        b0 = build(T0, [cand("ceo", "Rita Gomes", team, "2021-01-01")])
        b1 = build(T1, [cand("ceo", "Tiago Neves", team, "2026-02-01")])
        b2 = build(T2, [cand("ceo", "Rita Gomes", team, "2021-01-01")])
        as_of_t1 = instant(T1)
        self.assertEqual(values_at([b0, b1], "2026-02-15", as_of_t1)["ceo"]["value"], "Tiago Neves")
        self.assertEqual(values_at([b0, b1], "2025-01-01", as_of_t1)["ceo"]["value"], "Rita Gomes")
        # the third version (2021) replaces the 2026 one, so Rita holds again from 2021 on
        self.assertEqual(values_at([b0, b1, b2], "2026-02-15", instant(T2))["ceo"]["value"], "Rita Gomes")

    def test_undated_version_holds_on_no_date_and_wipes_earlier(self):
        url = "https://news.test/seed"
        b0 = build(T0, [cand("funding_total", 8000000, url, "2025-06-10", "news")])
        b1 = build(T1, [cand("funding_total", 9000000, url, None, "news")])
        out = values_at([b0, b1], "2025-07-01", instant(T1))["funding_total"]
        self.assertEqual((out["value"], out["true_from"], out["citations"]), (None, None, []))

    def test_a_page_no_longer_gathered_keeps_holding(self):
        b0 = build(T0, [cand("headcount_range", "11-50", "https://agg.test/x", "2025-03-01", "aggregator")])
        b1 = build(T1, [])
        self.assertEqual(values_at([b0, b1], "2026-02-15", instant(T1))["headcount_range"]["value"], "11-50")


class TitlesAndTrueFrom(unittest.TestCase):
    def test_title_support(self):
        self.assertEqual(support.supported_title("Lumen CFO: Ana Silva.", "cfo", D), "Ana Silva")
        self.assertEqual(support.supported_title("Bruno Costa is the chief technology officer of Lumen.", "cto", D),
                         "Bruno Costa")
        self.assertIsNone(support.supported_title("Lumen CFO: Ana Silva.", "cto", D))
        self.assertIsNone(support.supported_title("Former Lumen CFO Ana Silva left.", "cfo", D))

    def test_page_true_from(self):
        self.assertEqual(pages.page_true_from({"Effective": "2021-01-01", "Published": "2026-01-01T00:00:00Z"}),
                         "2021-01-01")
        self.assertEqual(pages.page_true_from({"Effective": "2025-13-40", "Published": "2024-03-05T23:30:00-02:00"}),
                         "2024-03-06")
        self.assertIsNone(pages.page_true_from({}))


if __name__ == "__main__":
    unittest.main()
