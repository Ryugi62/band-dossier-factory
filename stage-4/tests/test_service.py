import asyncio
import unittest

from dossier import errors
from dossier.service import Service, canonical
from tests.test_pipeline import FakeGateway

FIXTURE = {"now": "2026-03-01T09:00:00+00:00",
           "users": [{"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}]}


def run(coro):
    return asyncio.run(coro)


class ServiceRules(unittest.TestCase):
    def test_idempotent_create_replay_and_reuse(self):
        async def scenario():
            svc = Service(FakeGateway({}, claims=[]))
            await svc.reset(dict(FIXTURE))
            body = {"domain": "acme.test"}
            first = svc.idempotent("u_ada", "POST", "/dossiers", "k", canonical(body), lambda: svc.create(body))
            again = svc.idempotent("u_ada", "POST", "/dossiers", "k", canonical(body), lambda: svc.create(body))
            with self.assertRaises(errors.ApiError) as ctx:
                other = {"domain": "other.test"}
                svc.idempotent("u_ada", "POST", "/dossiers", "k", canonical(other), lambda: svc.create(other))
            await asyncio.sleep(0.05)
            return first, again, ctx.exception.code
        first, again, code = run(scenario())
        self.assertEqual(first[0], 202)
        self.assertEqual(again, (200, first[1]))
        self.assertEqual(code, "idempotency_key_reuse")

    def test_reset_rejects_duplicate_email_and_keeps_state(self):
        async def scenario():
            svc = Service(FakeGateway({}, claims=[]))
            await svc.reset(dict(FIXTURE))
            bad = {"now": FIXTURE["now"], "users": FIXTURE["users"] * 2}
            with self.assertRaises(errors.ApiError):
                await svc.reset(bad)
            return await svc.login({"email": "ada@example.com", "password": "correct horse"})
        self.assertEqual(run(scenario())["user_id"], "u_ada")

    def test_clock_never_goes_back(self):
        async def scenario():
            svc = Service(FakeGateway({}, claims=[]))
            await svc.reset(dict(FIXTURE))
            svc.set_clock({"now": "2026-03-01T09:00:00+00:00"})
            with self.assertRaises(errors.ApiError):
                svc.set_clock({"now": "2026-03-01T08:59:59+00:00"})
        run(scenario())

    def test_export_import_round_trip(self):
        async def scenario():
            svc = Service(FakeGateway({}, claims=[]))
            await svc.reset(dict(FIXTURE))
            svc.create({"domain": "acme.test"})
            await asyncio.sleep(0.05)
            snapshot = svc.export()
            svc.create({"domain": "later.test"})
            svc.import_state(snapshot)
            return svc.list(None, 50, 0), snapshot
        listing, snapshot = run(scenario())
        self.assertEqual([d["domain"] for d in listing["dossiers"]], ["acme.test"])
        self.assertNotIn("correct horse", str(snapshot))


class StageOneImport(unittest.TestCase):
    """Decision D16: a stage-1 export's citations become candidates (kind and published_at null)."""

    def stage1_export(self):
        cit = lambda url, ex: {"url": url, "excerpt": ex, "provider": "nimble"}  # noqa: E731
        empty = {"value": None, "status": "unknown", "citations": []}
        fields = {f: dict(empty) for f in ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range",
                                           "funding_total")}
        fields["hq_city"] = {"value": "Lisbon", "status": "known", "citations": [
            cit("https://b.test/x", "Acme is based in Lisbon."), cit("https://a.test/y", "Acme is headquartered in Lisbon."),
            cit("https://c.test/z", "Acme likes Lisbon.")]}
        return {"track": "dossier", "format_version": 1, "state": {
            "users": [{"id": "u_ada", "email": "ada@example.com", "display_name": "Ada",
                       "password_hash": "scrypt$16384$8$1$00$00"}],
            "tokens": [{"token": "tok-1", "user_id": "u_ada"}],
            "dossiers": [{"id": "d_1", "domain": "acme.test", "state": "ready", "fields": fields,
                          "researched_at": "2026-03-01T09:00:00+00:00", "spent_units": 30}],
            "idempotent": [{"user_id": "u_ada", "method": "POST", "path": "/dossiers", "key": "k",
                            "request": canonical({"domain": "acme.test"}),
                            "response": {"dossier_id": "d_1", "domain": "acme.test", "state": "building"}}]}}

    def test_candidates_rebuilt_from_citations(self):
        svc = Service(FakeGateway({}, claims=[]))
        svc.import_state(self.stage1_export())
        view = svc.read("acme.test")
        hq = view["fields"]["hq_city"]
        self.assertEqual(hq["status"], "known")
        self.assertEqual([c["url"] for c in hq["candidates"]], ["https://a.test/y", "https://b.test/x"])
        self.assertTrue(all(c["kind"] is None and c["published_at"] is None
                            and c["retrieved_at"] == "2026-03-01T09:00:00+00:00" for c in hq["candidates"]))
        self.assertEqual(hq["candidates"][0]["selected"], True)
        self.assertEqual(view["fields"]["ceo"], {"value": None, "status": "unknown", "true_from": None,
                                                 "learned_at": None, "citations": [], "candidates": [],
                                                 "origins": [], "corroborated": False, "corroborated_since": None})
        self.assertEqual(view["fields"]["executives"]["status"], "unknown")
        self.assertEqual([e["type"] for e in svc.history("acme.test")["fields"]["hq_city"]], ["initial"])
        self.assertEqual(svc.authenticate("Bearer tok-1"), "u_ada")
        status, body = svc.idempotent("u_ada", "POST", "/dossiers", "k", canonical({"domain": "acme.test"}),
                                      lambda: (500, {}))
        self.assertEqual((status, body["dossier_id"]), (200, "d_1"))

    def test_stage2_export_round_trip_keeps_candidates(self):
        svc = Service(FakeGateway({}, claims=[]))
        svc.import_state(self.stage1_export())
        before = svc.read("acme.test")
        svc.import_state(svc.export())
        self.assertEqual(svc.read("acme.test"), before)


if __name__ == "__main__":
    unittest.main()
