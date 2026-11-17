import asyncio
import os
import tempfile
import unittest

from dossier.persistence import Persistence
from dossier.service import Service, canonical
from tests.test_pipeline import FakeGateway

FIXTURE = {"now": "2026-03-01T09:00:00+00:00",
           "users": [{"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}]}
PAGE = "Kind: own\nPublished: 2024-01-01T00:00:00Z\n\nAcme was founded in 2014."


async def settled(svc, domain="acme.test"):
    """Wait until the dossier's build has finished (fsyncs make it slower on a busy machine)."""
    for _ in range(200):
        if svc.store.dossiers[domain].state != "building":
            return
        await asyncio.sleep(0.02)


def gateway():
    from dossier.provider import SearchHit
    return FakeGateway({"acme.test": [SearchHit("https://acme.test/a", "Acme", "Acme was founded in 2014.")]},
                       {"https://acme.test/a": PAGE}, claims=[])


class Restart(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "state.db")

    def tearDown(self):
        self.dir.cleanup()

    def test_state_survives_a_restart(self):
        async def before():
            svc = Service(gateway(), Persistence(self.path))
            await svc.reset(dict(FIXTURE))
            session = await svc.login({"email": "ada@example.com", "password": "correct horse"})
            body = {"domain": "acme.test"}
            first = svc.idempotent("u_ada", "POST", "/dossiers", "k", canonical(body), lambda: svc.create(body))
            await settled(svc)
            svc.set_clock({"now": "2026-03-05T00:00:00+00:00"})
            return session["token"], first[1], svc.read("acme.test"), svc.history("acme.test")

        token, response, dossier, history = asyncio.run(before())

        async def after():
            svc = Service(gateway(), Persistence(self.path))
            replay = svc.idempotent("u_ada", "POST", "/dossiers", "k", canonical({"domain": "acme.test"}), None)
            return svc, replay

        svc, replay = asyncio.run(after())
        self.assertEqual(svc.authenticate(f"Bearer {token}"), "u_ada")
        self.assertEqual(svc.read("acme.test"), dossier)
        self.assertEqual(svc.history("acme.test"), history)
        self.assertEqual(replay, (200, response))
        self.assertEqual(svc.clock.fixed_iso(), "2026-03-05T00:00:00+00:00")

    def test_build_cut_off_by_a_stop_is_closed_failed(self):
        async def before():
            svc = Service(gateway(), Persistence(self.path))
            await svc.reset(dict(FIXTURE))
            svc.create({"domain": "acme.test"})
            await settled(svc)
            dossier = svc.store.dossiers["acme.test"]
            dossier.settled_state, dossier.state = "ready", "building"   # a refresh in flight at the stop
            dossier.settled_spent = dossier.spent_units
            dossier.spent_units += 7      # settled before the stop
            dossier.inflight = 3          # a call made, not yet answered
            svc.store.save_dossier(dossier)
            return dossier.spent_units, len(dossier.builds), svc.read("acme.test")["fields"]

        spent, builds, fields = asyncio.run(before())
        svc = Service(gateway(), Persistence(self.path))
        d = svc.store.dossiers["acme.test"]
        # D43: closed failed before /health; in-flight counted as billed; logged as a failed build of 10 units
        self.assertEqual((d.state, d.spent_units, len(d.builds)), ("failed", spent + 3, builds + 1))
        self.assertEqual((d.builds[-1]["outcome"], d.builds[-1]["spent"]), ("failed", 10))
        self.assertEqual(svc.read("acme.test")["fields"], fields)

    def test_reset_replaces_stored_state(self):
        async def run():
            svc = Service(gateway(), Persistence(self.path))
            await svc.reset(dict(FIXTURE))
            svc.create({"domain": "acme.test"})
            await settled(svc)
            await svc.reset(dict(FIXTURE))
        asyncio.run(run())
        self.assertEqual(Service(gateway(), Persistence(self.path)).store.dossiers, {})


if __name__ == "__main__":
    unittest.main()
