"""One build (§8, §9, stage 2): gather the evidence through the gateway within the cap, read every
page that supports a value in its browser text, and turn those sentences into candidates.

Order of calls, cheapest first:
1. a Nimble research run asking for all six fields (decision D2), started at once;
2. one lite search whose query is exactly the domain;
3. when that search came back full (more pages may exist) or failed, lite searches by the company's
   name: one per field (the six fields, the executives' titles and investors) with all of its statement
   phrases, and one with the shortest phrase for the fields whose statements are often syndicated
   across many sites (ceo, funding, executives, investors), so every page that supports a value is
   reached; re-measured for stage 4 (decision D46): 0 of 301 supporting pages of the corpora missed;
4. a rendered extract (3 units, decision D13) of every page whose known text supports a value:
   off the live endpoint a lite snippet is the first 300 characters of the page's prose, so a
   shorter snippet is the whole prose and a longer one shows its leading sentences;
5. a plain extract (1 unit) of each relevant page whose text is not fully known, followed by a
   rendered extract only when that text supports a value;
6. the same for every page a research claim cites (stage-2 Candidates), once the run answers.
Candidates come only from rendered text: one per (url, provider, value) of a field, the first
supporting sentence being its excerpt (decision D19). Stage 3 adds the executives' titles (one
candidate per (url, provider, title, name)) and each page's `true_from`; every rendered page is a
page version of the build, with or without candidates.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

from . import lineage, pages, support
from .provider import Claim, Gateway, Meter, SearchHit

SNIPPET_CHARS = 300
FIELD_QUERY_WORDS = {
    "legal_name": "legal name registered name registered as legal entity",
    "hq_city": "headquartered headquarters head office based in registered office",
    "ceo": "CEO chief executive officer",
    "founded_year": "founded established incorporated founding",
    "headcount_range": "employees employs staff people headcount workforce",
    "funding_total": "raised funding investment invested",
    "executives": "CFO chief financial officer COO chief operating officer CTO chief technology officer",
    "investors": "investor investors led by backed by participated",
}
FIELD_QUERY_SHORT = {"ceo": "CEO", "funding_total": "raised", "executives": "CFO", "investors": "backed by"}


@dataclass
class Page:
    url: str
    title: str
    snippet: str
    known: str        # prose this build already holds for the page (may be the leading part only)
    complete: bool    # `known` is the page's whole prose


def supports_any(sentences: list[str], domain: str) -> bool:
    return any(True for _ in pages.supporting_sentences(sentences, domain)) or \
        any(True for _ in pages.supporting_titles(sentences, domain)) or \
        any(True for _ in pages.supporting_investors(sentences, domain))


def read_page(url: str, text: str, domain: str, retrieved_at: str) -> tuple[str | None, list[dict]]:
    """(true_from, candidates) of a rendered page: one candidate per (field, title or investor, value), first
    sentence; `kind` follows the stage-4 own-page rule; `origin` is filled in once the build knows it."""
    header, prose = pages.split_prose(text)
    values = pages.header_values(header)
    kind = lineage.own_rule(pages.page_kind(values, url, domain), values, url, domain)
    base = {"url": url, "provider": "nimble", "kind": kind,
            "published_at": pages.page_published(values), "true_from": pages.page_true_from(values),
            "retrieved_at": retrieved_at}
    sentences = support.split_sentences(prose)
    out, seen = [], set()
    for field, value, excerpt in pages.supporting_sentences(sentences, domain):
        if (field, repr(value)) not in seen:
            seen.add((field, repr(value)))
            out.append(dict(base, field=field, value=value, excerpt=excerpt))
    for title, name, excerpt in pages.supporting_titles(sentences, domain):
        if (title, name) not in seen:
            seen.add((title, name))
            out.append(dict(base, field="executives", title=title, value=name, excerpt=excerpt))
    for name, excerpt in pages.supporting_investors(sentences, domain):
        if ("investors", name) not in seen:
            seen.add(("investors", name))
            out.append(dict(base, field="investors", value=name, excerpt=excerpt))
    return base["true_from"], out


def candidates_from_text(url: str, text: str, domain: str, retrieved_at: str) -> list[dict]:
    return read_page(url, text, domain, retrieved_at)[1]


class Build:
    def __init__(self, gateway: Gateway, domain: str, meter: Meter, build_time: str) -> None:
        self.gateway, self.domain, self.meter, self.build_time = gateway, domain, meter, build_time
        self.pages: dict[str, Page] = {}
        self.handled: set[str] = set()
        self.candidates: list[dict] = []
        self.versions: dict[str, str | None] = {}
        # header lines of every page text this build obtained, by url key (renders reused for originals)
        self.headers: dict[str, dict | None] = {}
        self.rendered: dict[str, dict] = {}
        self._fetching: dict[str, asyncio.Future] = {}

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
            true_from, candidates = read_page(url, text, self.domain, self.build_time)
            self.versions[url] = true_from
            self.candidates.extend(candidates)
            header = pages.header_values(pages.split_prose(text)[0])
            self.headers[lineage.url_key(url)] = header
            self.rendered[url] = header

    async def probe_then_render(self, url: str) -> None:
        text = await self.gateway.extract(self.meter, url)
        if text is not None:
            self.headers.setdefault(lineage.url_key(url), pages.header_values(pages.split_prose(text)[0]))
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

    # -------------------------------------------------------------- origins (stage 4)
    async def original_header(self, url: str) -> dict | None:
        """Header lines of an original, from text this build already holds, else one plain extract (1 unit)."""
        key = lineage.url_key(url)
        if key in self.headers:
            return self.headers[key]
        if key not in self._fetching:
            self._fetching[key] = asyncio.ensure_future(self._fetch_original(url))
        return await self._fetching[key]

    async def _fetch_original(self, url: str) -> dict | None:
        text = await self.gateway.extract(self.meter, url)
        header = pages.header_values(pages.split_prose(text)[0]) if text is not None else None
        self.headers[lineage.url_key(url)] = header
        return header

    async def assign_origins(self) -> None:
        urls = list(self.rendered)
        found = await asyncio.gather(*(lineage.resolve_origin(self.rendered[u], u, self.domain, self.original_header)
                                       for u in urls))
        origin = dict(zip(urls, found))
        for c in self.candidates:
            c["origin"] = origin[c["url"]]

    def read_cited_page(self, claim_excerpts: list[str], url: str):
        self.handled.add(url)
        if any(supports_any([e], self.domain) for e in claim_excerpts):
            return self.render(url)
        return self.probe_then_render(url)

    # -------------------------------------------------------------- the build
    async def run(self) -> tuple[list[dict], dict] | None:
        research = asyncio.create_task(self.gateway.research(self.meter, self.domain))
        readers = []
        try:
            hits = await self.gateway.search(self.meter, self.domain)
            if hits:
                self.add_hits(hits)
            if hits is None or len(hits) >= 10 or self.gateway.live:
                name = support.company_name(self.domain)
                queries = [f"{name} {w}" for w in FIELD_QUERY_WORDS.values()]
                queries += [f"{name} {w}" for w in FIELD_QUERY_SHORT.values()]
                more = await asyncio.gather(*(self.gateway.search(self.meter, q) for q in queries))
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
            await self.assign_origins()
        finally:
            for task in readers + [research]:
                if not task.done():
                    task.cancel()
        if not self.meter.succeeded:
            return None
        return self.candidates, self.versions


async def run_build(gateway: Gateway, domain: str, meter: Meter, build_time: str) -> tuple[list[dict], dict] | None:
    """(candidates, page versions {url: true_from}), or None when no provider call succeeded (the build failed)."""
    return await Build(gateway, domain, meter, build_time).run()
