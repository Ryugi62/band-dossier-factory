import unittest

from dossier.selection import derive_field, rank_key, same_value


def cand(value, url, kind="own", published=None, provider="nimble"):
    return {"value": value, "url": url, "excerpt": f"{value} at {url}", "provider": provider, "kind": kind,
            "published_at": published, "retrieved_at": "2026-03-01T09:00:00+00:00"}


class SelectionRule(unittest.TestCase):
    def test_authority_beats_recency(self):
        f = derive_field([cand("Tomas Berg", "https://news.test/a", "news", "2026-02-01T00:00:00+00:00"),
                          cand("Mara Lind", "https://acme.test/team", "own", "2024-01-01T00:00:00+00:00")])
        self.assertEqual((f["value"], f["status"]), ("Mara Lind", "contested"))
        self.assertEqual([c["selected"] for c in f["candidates"]], [True, False])

    def test_own_and_filing_rank_equal_then_recency_as_instants(self):
        f = derive_field([cand("Oslo", "https://n.test/1", "news", "2025-05-01T00:00:00Z"),
                          cand("Bergen", "https://n.test/2", "news", "2025-09-01T10:00:00+02:00"),
                          cand("Tromsø", "https://agg.test/3", "aggregator", "2026-03-01T00:00:00Z")])
        self.assertEqual([c["value"] for c in f["candidates"]], ["Bergen", "Oslo", "Tromsø"])

    def test_undated_ranks_below_dated_same_authority(self):
        f = derive_field([cand(2001, "https://a.test/x", "aggregator"),
                          cand(2002, "https://b.test/y", "aggregator", "2026-03-01T00:00:00Z")])
        self.assertEqual(f["value"], 2002)

    def test_url_then_provider_then_value(self):
        f = derive_field([cand("501-1000", "https://acme.test/b-jobs"), cand("51-200", "https://acme.test/a-careers")])
        self.assertEqual(f["value"], "51-200")
        f = derive_field([cand(20000000, "https://reg.test/c", "filing"), cand(15000000, "https://reg.test/c", "filing")])
        self.assertEqual(f["value"], 15000000)
        f = derive_field([cand("X Y", "https://a.test/", provider="tavily"), cand("A B", "https://a.test/", provider="nimble")])
        self.assertEqual(f["candidates"][0]["provider"], "nimble")

    def test_imported_null_kind_has_aggregator_authority(self):
        f = derive_field([cand("Lisbon", "https://a.test/", None), cand("Porto", "https://z.test/", "news")])
        self.assertEqual(f["value"], "Porto")
        self.assertEqual(rank_key(cand("x", "u", None))[0], rank_key(cand("x", "u", "aggregator"))[0])

    def test_citations_are_every_candidate_with_the_value_in_rank_order(self):
        f = derive_field([cand("Lisbon", "https://b.test/"), cand("Porto", "https://c.test/", "news"),
                          cand("Lisbon", "https://a.test/")])
        self.assertEqual([c["url"] for c in f["citations"]], ["https://a.test/", "https://b.test/"])
        self.assertEqual(set(f["citations"][0]), {"url", "excerpt", "provider"})

    def test_status(self):
        self.assertEqual(derive_field([])["status"], "unknown")
        self.assertIsNone(derive_field([])["value"])
        self.assertEqual(derive_field([cand("Lisbon", "https://a.test/"), cand(" Lisbon ", "https://b.test/")])["status"],
                         "known")

    def test_same_value(self):
        self.assertTrue(same_value(" A ", "A"))
        self.assertFalse(same_value(2014, "2014"))


if __name__ == "__main__":
    unittest.main()
