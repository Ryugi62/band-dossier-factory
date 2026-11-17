"""The selection rule and Status (stage 2): rank a field's candidates, pick one, derive the field.

Pure functions only. A candidate is a dict with `value`, `url`, `excerpt`, `provider`, `kind`,
`published_at` and `retrieved_at`.
"""
from __future__ import annotations

import datetime as dt

from .support import FIELDS

PROVIDER_ORDER = ("nimble", "tavily", "kernel", "browserbase")
_AUTHORITY = {"own": 0, "filing": 0, "news": 1, "aggregator": 2}  # an imported candidate (kind null) ranks as aggregator


def same_value(a, b) -> bool:
    """Equal as JSON values; strings compared exactly after removing surrounding whitespace."""
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip()
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    return type(a) is type(b) and a == b


def _instant(published_at: str | None) -> float | None:
    if published_at is None:
        return None
    return dt.datetime.fromisoformat(published_at.replace("Z", "+00:00").replace("z", "+00:00")).timestamp()


def _value_key(value):
    if isinstance(value, str):
        return (1, 0, value.strip())
    return (0, value, "")


def rank_key(candidate: dict) -> tuple:
    """Authority, then recency (undated last), then URL by code point, provider order, value."""
    instant = _instant(candidate.get("published_at"))
    provider = candidate.get("provider")
    return (
        _AUTHORITY.get(candidate.get("kind"), 2),
        (1, 0.0) if instant is None else (0, -instant),
        candidate["url"],
        PROVIDER_ORDER.index(provider) if provider in PROVIDER_ORDER else len(PROVIDER_ORDER),
        _value_key(candidate["value"]),
    )


def derive_field(candidates: list[dict]) -> dict:
    """A field's `value`, `status`, `citations` and ranked `candidates` (with `selected`) from its candidates."""
    ranked = sorted(candidates, key=rank_key)
    if not ranked:
        return {"value": None, "status": "unknown", "citations": [], "candidates": []}
    chosen = ranked[0]["value"]
    distinct = []
    for c in ranked:
        if not any(same_value(c["value"], v) for v in distinct):
            distinct.append(c["value"])
    out_candidates = [dict(c, selected=(i == 0)) for i, c in enumerate(ranked)]
    return {
        "value": chosen.strip() if isinstance(chosen, str) else chosen,
        "status": "known" if len(distinct) == 1 else "contested",
        "citations": [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]}
                      for c in ranked if same_value(c["value"], chosen)],
        "candidates": out_candidates,
    }


def derive_fields(candidates_by_field: dict) -> dict:
    return {f: derive_field(candidates_by_field.get(f, [])) for f in FIELDS}
