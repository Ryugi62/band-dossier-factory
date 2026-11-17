"""One build (§8, §9, stage 2): gather the evidence through the gateway within the cap, read every
page that supports a value in its browser text, and turn those sentences into candidates.

Order of calls, cheapest first:
1. a Nimble research run asking for all six fields (decision D2), started at once;
2. one lite search whose query is exactly the domain;
3. when that search came back full (more pages may exist) or failed, one lite search per field,
   the company's name plus that field's statement phrases, so every page that supports a value is
   reached (a query with the domain favours pages that merely mention the domain);
4. a rendered extract (3 units, decision D13) of every page whose known text supports a value:
   off the live endpoint a lite snippet is the first 300 characters of the page's prose, so a
   shorter snippet is the whole prose and a longer one shows its leading sentences;
5. a plain extract (1 unit) of each relevant page whose text is not fully known, followed by a
   rendered extract only when that text supports a value;
6. the same for every page a research claim cites (stage-2 Candidates), once the run answers.
Candidates come only from rendered text: one per (url, provider, value) of a field, the first
supporting sentence being its excerpt (decision D19).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

from . import pages, selection, support
from .provider import Claim, Gateway, Meter, SearchHit

SNIPPET_CHARS = 300
FIELD_QUERY_WORDS = {
    "legal_name": "legal name registered name registered as legal entity",
    "hq_city": "headquartered headquarters head office based in registered office",
    "ceo": "CEO chief executive officer",
    "founded_year": "founded established incorporated founding",
    "headcount_range": "employees employs staff people headcount workforce",
    "funding_total": "raised funding investment invested",
}


@dataclass
class Page:
    url: str
    title: str
    snippet: str
    known: str        # prose this build already holds for the page (may be the leading part only)
    complete: bool    # `known` is the page's whole prose


def supports_any(sentences: list[str], domain: str) -> bool:
    return any(True for _ in pages.supporting_sentences(sentences, domain))


def candidates_from_text(url: str, text: str, domain: str, retrieved_at: str) -> list[dict]:
    """One candidate per (field, value) the page's rendered text supports, from its first supporting sentence."""
    header, prose = pages.split_prose(text)
    values = pages.header_values(header)
    kind, published = pages.page_kind(values, url, domain), pages.page_published(values)
    out, seen = [], set()
    for field, value, excerpt in pages.supporting_sentences(support.split_sentences(prose), domain):
        if (field, repr(value)) in seen:
            continue
        seen.add((field, repr(value)))
        out.append({"field": field, "value": value, "url": url, "excerpt": excerpt, "provider": "nimble",
                    "kind": kind, "published_at": published, "retrieved_at": retrieved_at})
    return out


class Build:
    def __init__(self, gateway: Gateway, domain: str, meter: Meter, build_time: str) -> None:
        self.gateway, self.domain, self.meter, self.build_time = gateway, domain, meter, build_time
        self.pages: dict[str, Page] = {}
        self.handled: set[str] = set()
        self.candidates: list[dict] = []

    # -------------------------------------------------------------- pages from searches
    def add_hits(self, hits: list[SearchHit]) -> None:
        for h in hits:
            if h.url in self.pages:
                continue
            if self.gateway.live:
                self.pages[h.url] = Page(h.url, h.title, h.snippet, "", False)
            else:
                complete = len(h.snippet) < SNIPPET_CHARS
                self.pages[h.url] = Page(h.url, h.title, h.snippet, h.snippet, complete)

    def relevant(self, page: Page) -> bool:
        host = (urlparse(page.url).hostname or "").lower()
        if host == self.domain or host.endswith("." + self.domain):
            return True
        return support.names_company(f"{page.title} {page.snippet}", self.domain)

    # -------------------------------------------------------------- reading pages
    async def render(self, url: str) -> None:
        text = await self.gateway.extract(self.meter, url, render=True)
        if text is not None:
            self.candidates.extend(candidates_from_text(url, text, self.domain, self.build_time))

    async def probe_then_render(self, url: str) -> None:
        text = await self.gateway.extract(self.meter, url)
        if text is not None and supports_any(support.split_sentences(pages.split_prose(text)[1]), self.domain):
            await self.render(url)

    def read_search_page(self, page: Page):
        """The coroutine that reads a search result, or None when its known prose already shows nothing."""
        if supports_any(pages.complete_sentences(page.known, not page.complete), self.domain):
            self.handled.add(page.url)
            return self.render(page.url)
        if not page.complete and self.relevant(page):
            self.handled.add(page.url)
            return self.probe_then_render(page.url)
        if page.complete:
            self.handled.add(page.url)  # its whole prose is known and supports nothing
        return None

    def read_cited_page(self, claim_excerpts: list[str], url: str):
        self.handled.add(url)
        if any(supports_any([e], self.domain) for e in claim_excerpts):
            return self.render(url)
        return self.probe_then_render(url)

    # -------------------------------------------------------------- the build
    async def run(self) -> dict | None:
        research = asyncio.create_task(self.gateway.research(self.meter, self.domain))
        readers = []
        try:
            hits = await self.gateway.search(self.meter, self.domain)
            if hits:
                self.add_hits(hits)
            if hits is None or len(hits) >= 10 or self.gateway.live:
                name = support.company_name(self.domain)
                more = await asyncio.gather(*(self.gateway.search(self.meter, f"{name} {FIELD_QUERY_WORDS[f]}")
                                              for f in support.FIELDS))
                for result in more:
                    if result:
                        self.add_hits(result)
            readers = [asyncio.create_task(c) for c in map(self.read_search_page, list(self.pages.values())) if c]
            claims: list[Claim] = await research or []
            cited = {}
            for claim in claims:
                cited.setdefault(claim.url, []).extend(claim.excerpts)
            readers += [asyncio.create_task(self.read_cited_page(ex, url))
                        for url, ex in cited.items() if url not in self.handled]
            await asyncio.gather(*readers)
        finally:
            for task in readers + [research]:
                if not task.done():
                    task.cancel()
        if not self.meter.succeeded:
            return None
        by_field = {}
        for c in self.candidates:
            by_field.setdefault(c["field"], []).append({k: v for k, v in c.items() if k != "field"})
        return selection.derive_fields(by_field)


async def run_build(gateway: Gateway, domain: str, meter: Meter, build_time: str) -> dict | None:
    """The decided fields with their candidates, or None when no provider call succeeded (the build failed)."""
    return await Build(gateway, domain, meter, build_time).run()
