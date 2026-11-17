import asyncio
import unittest

from dossier.pipeline import candidates_from_text, run_build
from dossier.provider import Claim, Meter, SearchHit
from dossier.selection import derive_fields

D = "acme.test"
T = "2026-03-01T09:00:00+00:00"


class FakeGateway:
    """Stands in for the WebRouter gateway; records each call and charges the meter like the real one."""

    def __init__(self, hits, pages=None, claims=None, live=False):
        self.hits, self.pages, self.claims, self.calls, self.live = hits, pages or {}, claims, [], live

    def _pay(self, meter, cost):
        if not meter.reserve(cost):
            return False
        meter.release(cost)
        meter.charge(cost)
        meter.succeeded = True
        return True

    async def search(self, meter, query):
        if not self._pay(meter, 1):
            return None
        self.calls.append(("search", query))
        return self.hits.get(query, [])

    async def extract(self, meter, url, render=False):
        if not self._pay(meter, 3 if render else 1):
            return None
        self.calls.append(("render" if render else "extract", url))
        return self.pages.get(url)

    async def research(self, meter, domain):
        if self.claims is None or not self._pay(meter, 25):
            return None
        self.calls.append(("research", domain))
        return self.claims


def build(gateway):
    meter = Meter(lambda cost: None)
    result = asyncio.run(run_build(gateway, D, meter, T))
    return (derive_fields(result[0]) if result else None), meter


class Pipeline(unittest.TestCase):
    def test_supporting_short_snippet_is_rendered_once(self):
        hits = {D: [SearchHit("https://acme.test/a", "About Acme", "Acme was founded in 2014."),
                    SearchHit("https://acme.test/b", "Acme", "Nothing to see.")]}
        pages = {"https://acme.test/a": "Kind: own\nPublished: 2024-01-01T00:00:00Z\n\nAcme was founded in 2014."}
        gw = FakeGateway(hits, pages, claims=[])
        fields, meter = build(gw)
        self.assertEqual(gw.calls.count(("render", "https://acme.test/a")), 1)
        self.assertNotIn(("render", "https://acme.test/b"), gw.calls)
        self.assertNotIn(("extract", "https://acme.test/b"), gw.calls)
        cand = fields["founded_year"]["candidates"][0]
        self.assertEqual((cand["value"], cand["kind"], cand["published_at"], cand["retrieved_at"], cand["selected"]),
                         (2014, "own", "2024-01-01T00:00:00+00:00", T, True))
        self.assertEqual(meter.spent, 25 + 1 + 3)

    def test_long_snippet_without_support_is_probed_then_rendered(self):
        long = "Acme makes things. " * 20
        hits = {D: [SearchHit("https://acme.test/b", "Acme", long[:300])]}
        pages = {"https://acme.test/b": "Kind: own\n\n" + long + "\nAcme CEO: Dana Ruiz."}
        gw = FakeGateway(hits, pages, claims=[])
        fields, _ = build(gw)
        u = "https://acme.test/b"
        self.assertLess(gw.calls.index(("extract", u)), gw.calls.index(("render", u)))
        self.assertEqual(fields["ceo"]["value"], "Dana Ruiz")

    def test_full_domain_search_runs_all_field_queries(self):
        hits = {D: [SearchHit(f"https://x.test/{i}", "Acme", "Acme is nice.") for i in range(10)]}
        gw = FakeGateway(hits, claims=[])
        build(gw)
        searches = [c for c in gw.calls if c[0] == "search"]
        self.assertEqual(len(searches), 13)
        self.assertEqual(sum(1 for c in searches if c[1] == D), 1)

    def test_claim_cited_page_is_read_even_if_claim_unsupported(self):
        claims = [Claim("funding_total", 8000000, "https://hidden.test/q", ["Acme wants to raise $8M next year."])]
        pages = {"https://hidden.test/q": "Kind: news\n\nAcme wants to raise $8M next year.\nAcme is based in Porto."}
        gw = FakeGateway({D: []}, pages, claims)
        fields, _ = build(gw)
        self.assertEqual(gw.calls[-2:], [("extract", "https://hidden.test/q"), ("render", "https://hidden.test/q")])
        self.assertEqual(fields["hq_city"]["value"], "Porto")
        self.assertEqual(fields["funding_total"]["candidates"], [])

    def test_supported_claim_page_rendered_directly(self):
        claims = [Claim("ceo", "Ines Brandt", "https://reg.test/p", ["Ines Brandt is the chief executive of Acme."])]
        pages = {"https://reg.test/p": "Kind: filing\n\nInes Brandt is the chief executive of Acme."}
        gw = FakeGateway({D: []}, pages, claims)
        fields, _ = build(gw)
        self.assertIn(("render", "https://reg.test/p"), gw.calls)
        self.assertNotIn(("extract", "https://reg.test/p"), gw.calls)
        self.assertEqual(fields["ceo"]["candidates"][0]["kind"], "filing")

    def test_live_snippets_are_never_evidence(self):
        hits = {D: [SearchHit("https://acme.test/a", "About Acme", "Acme was founded in 2014."),
                    SearchHit("https://other.test/z", "Unrelated", "Nothing here.")]}
        pages = {"https://acme.test/a": "Acme was founded in 2015."}
        gw = FakeGateway(hits, pages, claims=[], live=True)
        fields, _ = build(gw)
        self.assertEqual(fields["founded_year"]["value"], 2015)
        self.assertIn(("extract", "https://acme.test/a"), gw.calls)
        self.assertNotIn(("extract", "https://other.test/z"), gw.calls)

    def test_no_successful_call_fails(self):
        class Dead(FakeGateway):
            async def search(self, meter, query):
                return None
        fields, meter = build(Dead({}, claims=None))
        self.assertIsNone(fields)
        self.assertEqual(meter.spent, 0)


class CandidatesFromText(unittest.TestCase):
    def test_one_candidate_per_value_first_sentence(self):
        text = ("Kind: filing\nPublished: 2025-01-15T00:00:00Z\n\nAcme has raised $20M in total.\n"
                "Acme has raised $15M from two funds.\nAcme has raised $20 million overall.")
        got = candidates_from_text("https://reg.test/acme", text, D, T)
        self.assertEqual([(c["value"], c["excerpt"]) for c in got],
                         [(20000000, "Acme has raised $20M in total."), (15000000, "Acme has raised $15M from two funds.")])
        self.assertTrue(all(c["kind"] == "filing" and c["provider"] == "nimble" for c in got))

    def test_facts_header_is_not_evidence(self):
        text = 'Facts: {"hq_city": "Acme is headquartered in Berlin."}\n\nAcme is headquartered in Zürich.'
        got = candidates_from_text("https://dir.test/acme", text, D, T)
        self.assertEqual([(c["value"], c["kind"]) for c in got], [("Zürich", "aggregator")])


class MeterCap(unittest.TestCase):
    def test_reservations_never_pass_the_cap(self):
        m = Meter(lambda c: None)
        self.assertTrue(m.reserve(25))
        self.assertTrue(m.reserve(55))
        self.assertFalse(m.reserve(1))


if __name__ == "__main__":
    unittest.main()
