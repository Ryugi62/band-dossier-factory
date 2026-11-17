import asyncio
import unittest

from dossier import errors, lineage, support
from dossier.batches import validate
from dossier.corroboration import origin_keys
from dossier.provider import Meter
from dossier.selection import derive_investors
from dossier.store import Batch
from dossier.timeline import change_type

D = "orbit-forge.test"


def run(coro):
    return asyncio.run(coro)


class Lineage(unittest.TestCase):
    def test_registrant_and_own_rule(self):
        self.assertEqual(lineage.registrant({"Registrant": "WWW.Wire.TEST."}, "https://x.test/a"), "wire.test")
        self.assertEqual(lineage.registrant({"Registrant": "not a domain!"}, "https://Odd.TEST/p"), "odd.test")
        self.assertEqual(lineage.own_rule("own", {"Registrant": "orbit-forge-holdings.test"}, "https://orbitforge.test/",
                                          D), "aggregator")
        self.assertEqual(lineage.own_rule("own", {"Registrant": D}, "https://orbit-forge.test/about", D), "own")
        self.assertTrue(lineage.is_lookalike({"Kind": "own", "Registrant": "orbit-forge-holdings.test"},
                                             "https://orbitforge.test/about"))

    def test_origin_rules(self):
        pages = {
            "https://b.test/x": {"Canonical": "https://c.test/x", "Registrant": "b.test"},
            "https://c.test/x": {"Canonical": "https://d.test/x", "Registrant": "c.test"},
            "https://d.test/x": {"Canonical": "https://e.test/x", "Registrant": "d.test"},
            "https://e.test/x": {"First-Published-By": "deep.test"},
            "https://loop-b.test/x": {"Canonical": "https://loop-a.test/x"},
        }

        async def fetch(url):
            return pages.get(url)

        def origin(header, url):
            return run(lineage.resolve_origin(header, url, D, fetch))

        self.assertEqual(origin({"First-Published-By": "WWW.Wire.TEST."}, "https://p.test/a"), "wire.test")
        self.assertEqual(origin({"Canonical": "https://b.test/x"}, "https://a.test/x"), "e.test")   # fourth hop: host
        self.assertEqual(origin({"Canonical": "https://c.test/x"}, "https://a.test/x"), "deep.test")
        self.assertEqual(origin({"Canonical": "https://gone.test/o"}, "https://r.test/a"), "gone.test")
        self.assertEqual(origin({"Canonical": "https://loop-b.test/x"}, "https://loop-a.test/x"), "loop-a.test")
        self.assertEqual(origin({"Canonical": "HTTPS://P.TEST/a#top", "Registrant": "p.test"}, "https://p.test/a"), "p.test")
        self.assertEqual(origin({"Kind": "own", "Registrant": "holdings.test"}, "https://lookalike.test/"), D)


class Investors(unittest.TestCase):
    def test_names(self):
        self.assertEqual(support.investor_names("Orbit Forge raised $20M in a round led by General Atlantic.", D),
                         ["General Atlantic"])
        self.assertEqual(support.investor_names("Orbit Forge is led by Dana Ruiz.", D), [])
        self.assertEqual(support.investor_names("Orbit Forge is backed by Northwind Ventures.", D), ["Northwind Ventures"])
        self.assertEqual(support.investor_names("Orbit Forge might be backed by Sequoia Holdings next.", D), [])

    def test_members_value_and_true_from(self):
        def c(name, url, kind, origin, tf):
            return {"value": name, "url": url, "excerpt": name, "provider": "nimble", "kind": kind, "origin": origin,
                    "published_at": None, "true_from": tf}
        f = derive_investors([c("Ember Fund", "https://a.test/", "news", "wire.test", "2025-04-01"),
                              c("Ember Fund", "https://b.test/", "news", "wire.test", "2025-04-02"),
                              c("General Atlantic", "https://r.test/", "news", "gone.test", "2025-06-01"),
                              c("General Atlantic", "https://d.test/", "news", "dealwire.test", "2025-06-02"),
                              c("Northwind Ventures", "https://orbit-forge.test/about", "own", D, "2024-05-02")])
        self.assertEqual(f["value"], ["General Atlantic", "Northwind Ventures"])
        self.assertEqual(f["true_from"], "2025-06-01")
        self.assertEqual(f["status"], "known")
        self.assertEqual({x["value"]: x["selected"] for x in f["candidates"]},
                         {"Ember Fund": False, "General Atlantic": True, "Northwind Ventures": True})

    def test_typing_by_name(self):
        old = {"value": ["General Atlantic"], "true_from": "2025-06-01"}
        self.assertEqual(change_type("investors", old, {"value": ["Atlas Capital", "General Atlantic"],
                                                        "member_true_from": {"Atlas Capital": "2023-01-01"}}), "correction")
        self.assertEqual(change_type("investors", old, {"value": ["Zeta Capital", "General Atlantic"],
                                                        "member_true_from": {"Zeta Capital": "2026-01-01"}}), "change")
        self.assertEqual(change_type("investors", old, {"value": None, "member_true_from": {}}), "change")


class Corroboration(unittest.TestCase):
    def test_standing_origins_survive_a_page_no_longer_gathered(self):
        def cand(value, url, origin):
            return {"field": "hq_city", "value": value, "url": url, "excerpt": value, "provider": "nimble",
                    "kind": "news", "origin": origin, "published_at": None, "true_from": None}
        b0 = {"time": "2026-03-01T09:00:00+00:00", "outcome": "ready", "spent": 1,
              "candidates": [cand("Lyon", "https://a.test/", "a.test"), cand("Lyon", "https://b.test/", "b.test")]}
        b1 = {"time": "2026-03-02T09:00:00+00:00", "outcome": "ready", "spent": 1,
              "candidates": [cand("Lyon", "https://a.test/", "a.test")]}
        b2 = {"time": "2026-03-03T09:00:00+00:00", "outcome": "ready", "spent": 1,
              "candidates": [cand("Grenoble", "https://a.test/", "a.test")]}
        keys = origin_keys([b0, b1], 1, ("hq_city",))["hq_city"]
        self.assertEqual((keys["origins"], keys["corroborated"], keys["corroborated_since"]),
                         (["a.test"], False, b0["time"]))
        self.assertIsNone(origin_keys([b0, b1, b2], 2, ("hq_city",))["hq_city"]["corroborated_since"])


class Batches(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate({"domains": ["WWW.A.test", "b.test"], "budget_units": 5}), (["a.test", "b.test"], 5))
        for body in ({"budget_units": 5}, {"domains": [], "budget_units": 5}, {"domains": ["a.test", "A.test."], "budget_units": 5},
                     {"domains": ["a.test"], "budget_units": "5"}, {"domains": ["a.test"], "budget_units": True},
                     {"domains": ["a.test"], "budget_units": 1.5}, {"domains": ["a.test"], "budget_units": 100001}):
            with self.assertRaises(errors.ApiError) as ctx:
                validate(body)
            self.assertEqual(ctx.exception.status, 422, body)

    def test_meter_never_passes_the_batch_budget(self):
        batch = Batch(id="b", owner="u", budget=30, domains=[])
        a, b = Meter(lambda c: None, batch=batch), Meter(lambda c: None, batch=batch)
        self.assertTrue(a.reserve(25))
        self.assertFalse(b.reserve(25))
        self.assertTrue(b.budget_blocked)
        self.assertTrue(b.reserve(5))
        a.settle(25, 25)
        b.settle(5, 0)
        self.assertEqual((batch.spent, batch.reserved), (25, 0))
        self.assertTrue(b.reserve(5))
        self.assertFalse(b.reserve(1))


if __name__ == "__main__":
    unittest.main()
