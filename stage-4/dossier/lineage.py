"""Lineage header lines (stage 4): registrant, own pages, lookalikes and origins. Pure functions.

`resolve_origin` walks rule 2 (Canonical) through a `fetch(url) -> header dict | None` the caller
supplies, so the pipeline decides how each original is obtained (decision D37).
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from . import domains


def normalise(raw) -> str | None:
    return domains.normalise(raw) if isinstance(raw, str) and raw.strip() else None


def valid_url(raw) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        p = urlparse(raw.strip())
    except ValueError:
        return False
    return p.scheme.lower() in ("http", "https") and bool(p.hostname)


def url_host(url: str) -> str:
    host = (urlparse(url.strip()).hostname or "").lower()
    return normalise(host) or host


def url_key(url: str) -> str:
    """Comparable form of a URL: trimmed, scheme and host lower-cased, fragment dropped."""
    p = urlparse(url.strip())
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path, p.params, p.query, ""))


def registrant(header: dict, url: str) -> str:
    """A valid `Registrant` domain, else the normalised host of the page's own URL."""
    return normalise(header.get("Registrant")) or url_host(url)


def own_rule(kind: str, header: dict, url: str, domain: str) -> str:
    """Stage 4: a page counts as `own` only when its registrant is the company's domain."""
    if kind == "own" and registrant(header, url) != domain:
        return "aggregator"
    return kind


def is_lookalike(header: dict, url: str) -> bool:
    return header.get("Kind") == "own" and registrant(header, url) != url_host(url)


def canonical_target(header: dict, url: str) -> str | None:
    """The `Canonical` URL when it is valid and not the page's own URL, else None."""
    can = header.get("Canonical")
    if not valid_url(can) or url_key(can) == url_key(url):
        return None
    return can.strip()


async def resolve_origin(header: dict, url: str, domain: str, fetch, max_hops: int = 3) -> str:
    """The page's origin by rules 1-4; rule 2 follows at most `max_hops` Canonical URLs in a row from this page.

    A fourth hop, an original no provider serves, or a cycle takes the host of that URL.
    """
    seen = {url_key(url)}
    hops = 0
    while True:
        first = normalise(header.get("First-Published-By"))
        if first:
            return first
        target = canonical_target(header, url)
        if target is None:
            return domain if is_lookalike(header, url) else registrant(header, url)
        if hops >= max_hops or url_key(target) in seen:
            return url_host(target)
        original = await fetch(target)
        if original is None:
            return url_host(target)
        seen.add(url_key(target))
        hops += 1
        header, url = original, target
