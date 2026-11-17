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


if __name__ == "__main__":
    unittest.main()
