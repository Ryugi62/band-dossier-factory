"""Build time limits (§8): ends within 300 s against live providers, within 10 s off-live when calls answer in 1 s."""
import asyncio
import unittest

from dossier import provider
from dossier.provider import BUILD_DEADLINE, Deadline, Gateway, Meter


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Refused(Exception):
    pass


def gateway_with(clock, live):
    async def sleep(seconds):
        clock.t += seconds
    return Gateway(live=live, classifier=lambda exc: provider.REFUSED if isinstance(exc, Refused) else provider.LOST,
                   sleep=sleep)


class DeadlineRules(unittest.TestCase):
    def test_no_call_starts_that_could_end_past_the_deadline(self):
        clock = FakeClock()
        d = Deadline(live=True, now=clock)
        clock.t = BUILD_DEADLINE - provider.CALL_TIMEOUT
        self.assertTrue(d.can_start(provider.CALL_TIMEOUT))
        clock.t += 0.1
        self.assertFalse(d.can_start(provider.CALL_TIMEOUT))

    def test_floors_hold_in_the_first_120_seconds(self):
        clock = FakeClock()
        d = Deadline(live=True, now=clock)
        clock.t = 120.0
        self.assertTrue(d.can_start(provider.RESEARCH_START_TIMEOUT))
        self.assertTrue(d.can_retry(provider.CALL_TIMEOUT))
        self.assertGreaterEqual(provider.CALL_TIMEOUT, 30)

    def test_research_wait_leaves_a_final_round(self):
        clock = FakeClock()
        d = Deadline(live=True, now=clock)
        clock.t = 60.0
        self.assertEqual(d.research_wait(), BUILD_DEADLINE - provider.FINAL_ROUND - 60.0)
        clock.t = 280.0
        self.assertEqual(d.research_wait(), 0.0)

    def test_refused_calls_are_retried_whatever_the_build_time_off_live(self):
        clock = FakeClock()
        d = Deadline(live=False, now=clock)
        clock.t = 30.0
        self.assertTrue(d.can_retry(provider.CALL_TIMEOUT))


class WorstCases(unittest.TestCase):
    def test_live_worst_case_research_then_extract_ends_before_300(self):
        """Research accepted after 60 s, no answer ever, then an extract that hangs 45 s: still < 300 s."""
        clock = FakeClock()

        class Job:
            async def aresult(self, timeout):
                clock.t += timeout
                raise TimeoutError

        class Router:
            async def submit_research(self, *a, **k):
                clock.t += 60.0
                return Job()

            async def extract(self, *a, **k):
                clock.t += provider.CALL_TIMEOUT
                raise TimeoutError

        gw = gateway_with(clock, live=True)
        gw._router = Router()
        meter = Meter(lambda c: None, deadline=Deadline(live=True, now=clock))
        self.assertIsNone(asyncio.run(gw.research(meter, "acme.test")))
        asyncio.run(gw.extract(meter, "https://acme.test/a"))
        self.assertLessEqual(clock.t, BUILD_DEADLINE)
        self.assertEqual(meter.spent, 26)

    def test_live_refusals_never_retry_past_the_deadline(self):
        clock = FakeClock()
        attempts = []

        class Router:
            async def extract(self, *a, **k):
                attempts.append(clock.t)
                clock.t += 1.0
                raise Refused()

        gw = gateway_with(clock, live=True)
        gw._router = Router()
        meter = Meter(lambda c: None, deadline=Deadline(live=True, now=clock))
        clock.t = BUILD_DEADLINE - provider.CALL_TIMEOUT - 1.0
        asyncio.run(gw.extract(meter, "https://acme.test/a"))
        self.assertEqual(len(attempts), 1)
        self.assertEqual(meter.spent, 0)

    def test_three_refusals_then_an_answer(self):
        """A call refused three times in a row is answered on its fourth attempt, each after >= 1.1 s (D15)."""
        clock = FakeClock()
        attempts = []

        class Router:
            async def search(self, *a, **k):
                attempts.append(clock.t)
                if len(attempts) <= 3:
                    raise Refused()

                class Resp:
                    results = []
                return Resp()

        gw = gateway_with(clock, live=False)
        gw._router = Router()
        meter = Meter(lambda c: None, deadline=Deadline(live=False, now=clock))
        self.assertEqual(asyncio.run(gw.search(meter, "acme.test")), [])
        self.assertEqual(len(attempts), 4)
        self.assertTrue(all(b - a >= provider.RETRY_GAP for a, b in zip(attempts, attempts[1:])))
        self.assertEqual(meter.spent, 1)


if __name__ == "__main__":
    unittest.main()
