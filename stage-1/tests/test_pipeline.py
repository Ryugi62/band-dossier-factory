import asyncio
import unittest

from dossier.pipeline import Evidence, decide, run_build
from dossier.provider import Claim, Meter, SearchHit

D = "acme.test"


class FakeGateway:
    """Stands in for the WebRouter gateway; records each call and charges the meter like the real one."""

    live = False

    def __init__(self, hits, pages=None, claims=None):
        self.hits, self.pages, self.claims, self.calls = hits, pages or {}, claims, []

    async def search(self, meter, query):
        if not meter.reserve(1):
            return None
        meter.release(1)
        meter.charge(1)
        meter.succeeded = True
        self.calls.append(("search", query))
        return self.hits.get(query, [])

    async def extract(self, meter, url):
        if not meter.reserve(1):
            return None
        meter.release(1)
        meter.charge(1)
        meter.succeeded = True
        self.calls.append(("extract", url))
        return self.pages.get(url)

    async def research(self, meter, domain):
        if self.claims is None or not meter.reserve(25):
            return None
        meter.release(25)
        meter.charge(25)
        meter.succeeded = True
        self.calls.append(("research", domain))
        return self.claims


def build(gateway):
    meter = Meter(lambda cost: None)
    return asyncio.run(run_build(gateway, D, meter)), meter


class Pipeline(unittest.TestCase):
    def test_short_snippets_need_no_extract(self):
        hits = {D: [SearchHit("https://acme.test/a", "About Acme", "Acme was founded in 2014.")]}
        fields, meter = build(FakeGateway(hits, claims=[]))
        self.assertEqual(fields["founded_year"]["value"], 2014)
        self.assertEqual(fields["founded_year"]["citations"],
                         [{"url": "https://acme.test/a", "excerpt": "Acme was founded in 2014.", "provider": "nimble"}])
        self.assertEqual(meter.spent, 26)

    def test_truncated_page_is_extracted_while_fields_are_missing(self):
        long = "Acme makes things. " * 20
        hits = {D: [SearchHit("https://acme.test/b", "Acme", long[:300])]}
        pages = {"https://acme.test/b": "Kind: own\n\n" + long + "\nAcme CEO: Dana Ruiz."}
        gw = FakeGateway(hits, pages, claims=[])
        fields, _ = build(gw)
        self.assertIn(("extract", "https://acme.test/b"), gw.calls)
        self.assertEqual(fields["ceo"]["value"], "Dana Ruiz")

    def test_full_domain_search_triggers_field_queries(self):
        hits = {D: [SearchHit(f"https://x.test/{i}", "Acme", "Acme is nice.") for i in range(10)]}
        gw = FakeGateway(hits, claims=[])
        build(gw)
        self.assertEqual(sum(1 for c in gw.calls if c[0] == "search" and c[1] == D), 1)
        self.assertEqual(sum(1 for c in gw.calls if c[0] == "search"), 7)

    def test_unsupported_claim_is_dropped_supported_one_extracted(self):
        claims = [Claim("ceo", "Ines Brandt", "https://hidden.test/p", ["Ines Brandt is the chief executive of Acme."]),
                  Claim("funding_total", 8000000, "https://hidden.test/q", ["Acme wants to raise $8M next year."])]
        pages = {"https://hidden.test/p": "Kind: news\n\nIntro.\nInes Brandt is the chief executive of Acme."}
        gw = FakeGateway({D: []}, pages, claims)
        fields, _ = build(gw)
        self.assertEqual(fields["ceo"]["value"], "Ines Brandt")
        self.assertIsNone(fields["funding_total"]["value"])
        self.assertNotIn(("extract", "https://hidden.test/q"), gw.calls)

    def test_claim_excerpt_not_on_page_is_dropped(self):
        claims = [Claim("ceo", "Ines Brandt", "https://hidden.test/p", ["Ines Brandt is the chief executive of Acme."])]
        pages = {"https://hidden.test/p": "Kind: news\n\nSomething else entirely."}
        fields, _ = build(FakeGateway({D: []}, pages, claims))
        self.assertIsNone(fields["ceo"]["value"])

    def test_no_successful_call_fails(self):
        class Dead(FakeGateway):
            async def search(self, meter, query):
                return None
        fields, meter = build(Dead({}, claims=None))
        self.assertIsNone(fields)
        self.assertEqual(meter.spent, 0)


class Decide(unittest.TestCase):
    def test_most_pages_then_first(self):
        ev = Evidence(D)
        ev.candidates = [("hq_city", "Leeds", "u1", "e1"), ("hq_city", "Galway", "u2", "e2"),
                         ("hq_city", "Galway", "u3", "e3")]
        out = decide(ev, [])
        self.assertEqual(out["hq_city"]["value"], "Galway")
        self.assertEqual([c["url"] for c in out["hq_city"]["citations"]], ["u2", "u3"])
        ev.candidates = ev.candidates[:2]
        self.assertEqual(decide(ev, [])["hq_city"]["value"], "Leeds")


class MeterCap(unittest.TestCase):
    def test_reservations_never_pass_the_cap(self):
        m = Meter(lambda c: None)
        self.assertTrue(m.reserve(25))
        self.assertTrue(m.reserve(55))
        self.assertFalse(m.reserve(1))
        m.release(55)
        m.charge(25)
        m.release(25)
        self.assertTrue(m.reserve(55))
        self.assertFalse(m.reserve(1))


if __name__ == "__main__":
    unittest.main()
