"""One build (§8, §9): gather evidence through the gateway within the cap, then decide each field.

Order of calls, cheapest first:
1. a Nimble research run asking for all six fields (decision D2), started at once;
2. one lite search whose query is exactly the domain;
3. when that search came back full (more pages may exist) or failed, one lite search per
   still-unsupported field, the domain plus that field's statement phrases;
4. one extract per page still needed: pages whose snippet was cut short (only while some field
   is unsupported), and pages a research claim cites when the claim supports its value and
   its field is still unsupported (decision D8).
A lite snippet off the mock is the first 300 characters of the page's prose, so a shorter one
is the whole prose and needs no extract. Against the live providers snippets are not prose,
so every page is extracted.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urlparse

from . import pages, support
from .provider import Claim, Gateway, Meter, SearchHit

SNIPPET_CHARS = 300
MAX_CITATIONS = 10
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
    prose: str
    truncated: bool
    searched: bool = True
    extracted: bool = False
    snippet: str = ""


@dataclass
class Evidence:
    """Everything a build holds for one company, in the order it was gathered."""
    domain: str
    pages: dict = field(default_factory=dict)
    candidates: list = field(default_factory=list)  # (field, value, url, excerpt)

    def add_hits(self, hits: list[SearchHit], snippets_are_prose: bool) -> None:
        for h in hits:
            if h.url in self.pages:
                continue
            complete = snippets_are_prose and len(h.snippet) < SNIPPET_CHARS
            usable = h.snippet if snippets_are_prose else ""
            self.pages[h.url] = Page(h.url, h.title, usable, truncated=not complete, snippet=h.snippet)
            self._scan(self.pages[h.url])

    def add_extract(self, url: str, text: str) -> None:
        _, prose = pages.split_prose(text)
        page = self.pages.get(url)
        if page is None:
            self.pages[url] = Page(url, "", prose, truncated=False, searched=False, extracted=True)
            return
        self.candidates = [c for c in self.candidates if c[2] != url]
        page.prose, page.truncated, page.extracted = prose, False, True
        self._scan(page)

    def _scan(self, page: Page) -> None:
        if not page.searched:
            return  # a page no search returned is evidence only through a research claim
        for f, value, excerpt in pages.supporting_sentences(
                pages.complete_sentences(page.prose, page.truncated), self.domain):
            self.candidates.append((f, value, page.url, excerpt))

    def supported_fields(self) -> set:
        return {c[0] for c in self.candidates}

    def unsupported(self) -> list[str]:
        have = self.supported_fields()
        return [f for f in support.FIELDS if f not in have]

    def relevant(self, page: Page) -> bool:
        host = (urlparse(page.url).hostname or "").lower()
        if host == self.domain or host.endswith("." + self.domain):
            return True
        return support.names_company(f"{page.title} {page.snippet} {page.prose}", self.domain)

    def verify_claim(self, claim: Claim) -> tuple | None:
        """(field, value, url, excerpt) when the claim's citation supports its value in text held for its url."""
        value = support.normalise_claim(claim.field, claim.value)
        page = self.pages.get(claim.url)
        if value is None or page is None:
            return None
        held = page.prose if not page.truncated else " ".join(pages.complete_sentences(page.prose, True))
        for excerpt in claim.excerpts:
            text = support.collapse_ws(excerpt)
            if 0 < len(text) <= pages.MAX_EXCERPT and support.supports(text, claim.field, value, self.domain) \
                    and pages.contains_excerpt(held, text):
                return claim.field, value, claim.url, text
        return None


def claim_supports_itself(claim: Claim, domain: str) -> bool:
    value = support.normalise_claim(claim.field, claim.value)
    return value is not None and any(
        support.supports(support.collapse_ws(e), claim.field, value, domain) for e in claim.excerpts)


def decide(evidence: Evidence, claims: list[tuple]) -> dict:
    """Each field's value and citations (decision D3: most distinct pages, ties by first gathered)."""
    out = {}
    rows = evidence.candidates + claims
    for f in support.FIELDS:
        mine = [r for r in rows if r[0] == f]
        if not mine:
            out[f] = {"value": None, "citations": []}
            continue
        order, urls = {}, {}
        for i, (_, value, url, _) in enumerate(mine):
            key = repr(value)
            order.setdefault(key, (i, value))
            urls.setdefault(key, set()).add(url)
        best = min(order, key=lambda k: (-len(urls[k]), order[k][0]))
        value = order[best][1]
        cits, seen = [], set()
        for _, v, url, excerpt in mine:
            if repr(v) == best and (url, excerpt) not in seen:
                seen.add((url, excerpt))
                cits.append({"url": url, "excerpt": excerpt, "provider": "nimble"})
        out[f] = {"value": value, "citations": cits[:MAX_CITATIONS]}
    return out


async def run_build(gateway: Gateway, domain: str, meter: Meter) -> dict | None:
    """The decided fields, or None when no provider call succeeded (the build failed)."""
    research = asyncio.create_task(gateway.research(meter, domain))
    try:
        evidence = Evidence(domain)
        prose_snippets = not gateway.live
        hits = await gateway.search(meter, domain)
        if hits:
            evidence.add_hits(hits, prose_snippets)
        if hits is None or len(hits) >= 10 or gateway.live:
            need = evidence.unsupported()
            results = await asyncio.gather(*(gateway.search(meter, f"{domain} {FIELD_QUERY_WORDS[f]}") for f in need))
            for more in results:
                if more:
                    evidence.add_hits(more, prose_snippets)
        claims = await research or []
    finally:
        if not research.done():
            research.cancel()
    await _extract_needed(gateway, meter, evidence, claims)
    verified = [v for v in (evidence.verify_claim(c) for c in claims) if v is not None]
    if not meter.succeeded:
        return None
    return decide(evidence, verified)


async def _extract_needed(gateway: Gateway, meter: Meter, evidence: Evidence, claims: list[Claim]) -> None:
    free = {v[0] for v in (evidence.verify_claim(c) for c in claims) if v is not None}
    need = set(evidence.unsupported()) - free
    if not need:
        return
    urls = []
    for c in claims:
        page = evidence.pages.get(c.url)
        if c.field in need and claim_supports_itself(c, evidence.domain) and (page is None or page.truncated):
            urls.append(c.url)
    for page in list(evidence.pages.values()):
        if page.truncated and page.searched and evidence.relevant(page):
            urls.append(page.url)
    urls = list(dict.fromkeys(urls))
    texts = await asyncio.gather(*(gateway.extract(meter, u) for u in urls))
    for url, text in zip(urls, texts):
        if text is not None:
            evidence.add_extract(url, text)
