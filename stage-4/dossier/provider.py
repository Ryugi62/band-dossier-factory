"""Provider access through WebRouter's `nimble` provider, metered against a per-build cap (§9).

Every call reserves its worst-case cost before it is made; the cost is charged once the call
was answered or lost (timeout, connection failure) and released when the provider refused it
with an error status. Refused calls are retried a few times, never sooner than a second later.
Tavily is never called (decision D1).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from .support import FIELDS

log = logging.getLogger("dossier.provider")

BUILD_CAP = 80
COST_SEARCH_LITE = 1
COST_EXTRACT = 1
COST_RENDER = 3
COST_RESEARCH = 25
MAX_RESULTS = 10
RETRIES = 3
RETRY_GAP = 1.1
CALL_TIMEOUT = 45.0
RESEARCH_START_TIMEOUT = 60.0
RESEARCH_RESULT_TIMEOUT = 200.0
# A build ends within 300 s (§8): no call starts unless it can time out by BUILD_DEADLINE, and the
# research wait leaves room for one more round of calls. The first call that could be cut short
# starts after 245 s, well past the 120 s floor, and no call is ever given less than 45 s (> 30 s).
BUILD_DEADLINE = 290.0
FINAL_ROUND = CALL_TIMEOUT + 5.0
# A refused call (429 or another error status, cost 0) is made again after RETRY_GAP, up to RETRIES more
# times (four attempts in all, decision D15): the same call less than a second after a 429 is refused
# again, and no call is refused more than three times in a row. Time spent waiting after a 429 does
# not count toward the 10 s bound (stage 2, Rate limits), so retries have no time window of their own.

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "legal_name": {"type": ["string", "null"], "description": "registered legal name"},
        "hq_city": {"type": ["string", "null"], "description": "city of the headquarters, no region or country"},
        "ceo": {"type": ["string", "null"], "description": "full name of the chief executive"},
        "founded_year": {"type": ["integer", "null"], "description": "year founded"},
        "headcount_range": {"type": ["string", "null"],
                            "description": "1-10, 11-50, 51-200, 201-500, 501-1000, 1001-5000, 5001-10000 or 10001+"},
        "funding_total": {"type": ["integer", "null"], "description": "total equity funding in whole US dollars"},
    },
    "required": list(FIELDS),
}


def is_live() -> bool:
    """Live providers: NIMBLE_BASE_URL unset, or its host sdk.nimbleway.com (§8 Builds)."""
    base = os.environ.get("NIMBLE_BASE_URL")
    return base is None or urlparse(base).hostname == "sdk.nimbleway.com"


class Deadline:
    """One build's time limits, measured from its start on a monotonic clock."""

    def __init__(self, live: bool, now=time.monotonic) -> None:
        self._now = now
        self.start = now()
        self.live = live

    def elapsed(self) -> float:
        return self._now() - self.start

    def can_start(self, timeout: float, after: float = 0.0) -> bool:
        """A call started `after` seconds from now, waiting up to `timeout`, still ends by the deadline."""
        return self.elapsed() + after + timeout <= BUILD_DEADLINE

    def can_retry(self, timeout: float) -> bool:
        return self.can_start(timeout, after=RETRY_GAP)

    def research_wait(self) -> float:
        """Seconds to wait for a research answer, leaving one final round of calls before the deadline."""
        return max(0.0, min(RESEARCH_RESULT_TIMEOUT, BUILD_DEADLINE - FINAL_ROUND - self.elapsed()))


class BatchBudget:
    """A batch's shared budget (stage 4): reservations of its builds' calls against `budget_units`."""

    def __init__(self, budget: int, spent: int = 0) -> None:
        self.budget = budget
        self.spent = spent
        self.reserved = 0

    def can_reserve(self, cost: int) -> bool:
        return self.spent + self.reserved + cost <= self.budget


class Meter:
    """One build's spending: worst-case reservations against the 80-unit cap (and its batch's budget), and
    settled charges. `on_update` runs after every reservation and settlement, so the caller can write the
    in-flight reservations durably before a call is made (decision D43)."""

    def __init__(self, on_charge, cap: int = BUILD_CAP, deadline: Deadline | None = None,
                 batch: BatchBudget | None = None, on_update=None) -> None:
        self.deadline = deadline or Deadline(live=False)
        self.cap = cap
        self.reserved = 0
        self.spent = 0
        self.succeeded = False
        self.budget_blocked = False
        self.batch = batch
        self._on_charge = on_charge
        self._on_update = on_update or (lambda: None)

    def reserve(self, cost: int) -> bool:
        if self.spent + self.reserved + cost > self.cap:
            return False
        if self.batch is not None:
            if not self.batch.can_reserve(cost):
                self.budget_blocked = True
                return False
            self.batch.reserved += cost
        self.reserved += cost
        self._on_update()
        return True

    def settle(self, reserved: int, charged: int) -> None:
        """Release a reservation and charge what the provider billed for that call, in one step."""
        self.reserved -= reserved
        self.spent += charged
        if self.batch is not None:
            self.batch.reserved -= reserved
            self.batch.spent += charged
        if charged:
            self._on_charge(charged)
        self._on_update()

    # stage-3 names, kept for callers that charge and release separately
    def release(self, cost: int) -> None:
        self.settle(cost, 0)

    def charge(self, cost: int) -> None:
        self.spent += cost
        if self.batch is not None:
            self.batch.spent += cost
        self._on_charge(cost)


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str


@dataclass
class Claim:
    field: str
    value: object
    url: str
    excerpts: list


REFUSED, LOST, NOT_SENT, ANSWERED_EMPTY = "refused", "lost", "not_sent", "answered_empty"


def classify(exc: BaseException) -> str:
    from web_router import (ConfigurationError, DeadlineExceededError, InvalidParameterError, ProviderError,
                            UnsupportedParameterError)
    if isinstance(exc, (ConfigurationError, InvalidParameterError, UnsupportedParameterError)):
        return NOT_SENT
    if isinstance(exc, DeadlineExceededError):
        return LOST
    if isinstance(exc, ProviderError):
        if getattr(exc, "kind", None) == "target":
            return ANSWERED_EMPTY
        status = getattr(exc, "status_code", None)
        if isinstance(status, int) and status >= 400:
            return REFUSED
    return LOST


class Gateway:
    """The one WebRouter client of the process, shared by every build."""

    def __init__(self, live: bool | None = None, classifier=None, sleep=asyncio.sleep) -> None:
        self._router = None
        self.live = is_live() if live is None else live
        self._classify = classifier or classify
        self._sleep = sleep

    def router(self):
        if self._router is None:
            from web_router import AsyncWebRouter
            self._router = AsyncWebRouter()
        return self._router

    async def _metered(self, meter: Meter, cost: int, call, what: str, timeout: float = CALL_TIMEOUT):
        """(ok, result): run `call` within the cap and the deadline, retrying refusals while time allows."""
        if not meter.deadline.can_start(timeout):
            log.info("%s skipped: the build deadline leaves no room", what)
            return False, None
        if not meter.reserve(cost):
            log.info("%s skipped: the build cap or the batch budget leaves no room", what)
            return False, None
        settled = False
        try:
            for attempt in range(RETRIES + 1):
                try:
                    result = await call()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - every provider failure is classified below
                    kind = self._classify(exc)
                    log.info("%s attempt %d: %s (%s)", what, attempt + 1, kind, exc)
                    if kind == REFUSED and attempt < RETRIES and meter.deadline.can_retry(timeout):
                        await self._sleep(RETRY_GAP)
                        continue
                    billed = cost if kind in (LOST, ANSWERED_EMPTY) else 0
                    meter.settle(cost, billed)
                    settled = True
                    if kind == ANSWERED_EMPTY:
                        meter.succeeded = True
                    return False, None
                meter.settle(cost, cost)
                settled = True
                meter.succeeded = True
                return True, result
            return False, None
        finally:
            if not settled:
                meter.settle(cost, 0)

    async def search(self, meter: Meter, query: str) -> list[SearchHit] | None:
        async def call():
            return await self.router().search(query, provider="nimble", search_depth="lite",
                                              max_results=MAX_RESULTS, timeout=CALL_TIMEOUT, data_apis=False)
        ok, resp = await self._metered(meter, COST_SEARCH_LITE, call, f"search {query!r}")
        if not ok:
            return None
        return [SearchHit(r.url, r.title or "", r.description or r.content or "") for r in resp.results if r.url]

    async def extract(self, meter: Meter, url: str, render: bool = False) -> str | None:
        """The page text Nimble serves for `url`; with `render`, the text a browser shows once it has loaded."""
        options = {"render": True} if render else None

        async def call():
            return await self.router().extract(url, provider="nimble", format="markdown", provider_options=options,
                                               timeout=CALL_TIMEOUT)
        cost = COST_RENDER if render else COST_EXTRACT
        ok, resp = await self._metered(meter, cost, call, f"{'render' if render else 'extract'} {url}")
        if not ok or not resp.documents:
            return None
        return resp.documents[0].content or ""

    async def research(self, meter: Meter, domain: str) -> list[Claim] | None:
        query = (f"Company profile for the company whose web domain is {domain}: its registered legal name, "
                 f"headquarters city, chief executive, founding year, headcount range and total equity funding.")

        async def start():
            return await asyncio.wait_for(
                self.router().submit_research(query, provider="nimble", output_schema=RESEARCH_SCHEMA),
                RESEARCH_START_TIMEOUT)
        ok, job = await self._metered(meter, COST_RESEARCH, start, f"research {domain}",
                                      timeout=RESEARCH_START_TIMEOUT)
        if not ok:
            return None
        wait = meter.deadline.research_wait()
        try:
            if wait <= 0:
                raise TimeoutError("no time left to wait for the research answer")
            resp = await asyncio.wait_for(job.aresult(timeout=wait), wait + 1.0)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a run that never answers leaves no claims
            log.info("research %s gave no answer: %s", domain, exc)
            return None
        return _claims(resp)


def _claims(resp) -> list[Claim]:
    structured = resp.structured if isinstance(resp.structured, dict) else {}
    out = []
    for c in resp.citations or []:
        field = (c.field or "").removeprefix("$.")
        if field not in FIELDS or structured.get(field) is None or not c.url:
            continue
        excerpts = [e for e in ([c.snippet] + list((c.extra or {}).get("excerpts") or [])) if isinstance(e, str) and e]
        out.append(Claim(field, structured[field], c.url, list(dict.fromkeys(excerpts))))
    return out
