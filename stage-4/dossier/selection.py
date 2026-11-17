"""The selection rule and Status (stage 2): rank a field's candidates, pick one, derive the field.

Pure functions only. A candidate is a dict with `value`, `url`, `excerpt`, `provider`, `kind`,
`published_at` and `retrieved_at`.
"""
from __future__ import annotations

import datetime as dt

from .roles import TITLES
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
        return {"value": None, "status": "unknown", "true_from": None, "citations": [], "candidates": []}
    chosen = ranked[0]["value"]
    distinct = []
    for c in ranked:
        if not any(same_value(c["value"], v) for v in distinct):
            distinct.append(c["value"])
    out_candidates = [dict(c, selected=(i == 0)) for i, c in enumerate(ranked)]
    return {
        "value": chosen.strip() if isinstance(chosen, str) else chosen,
        "status": "known" if len(distinct) == 1 else "contested",
        "true_from": ranked[0].get("true_from"),
        "citations": [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]}
                      for c in ranked if same_value(c["value"], chosen)],
        "candidates": out_candidates,
    }


def derive_executives(candidates: list[dict]) -> dict:
    """Stage 3 `executives`: the selection rule per title; members in title order cfo, coo, cto."""
    members, citations, ordered, true_froms, contested = [], [], [], [], False
    for title in TITLES:
        f = derive_field([c for c in candidates if c.get("title") == title])
        if f["value"] is None:
            continue
        members.append({"title": title, "name": f["value"]})
        citations.extend(f["citations"])
        ordered.extend(f["candidates"])
        true_froms.append(f["true_from"])
        contested = contested or f["status"] == "contested"
    if not members:
        return {"value": None, "status": "unknown", "true_from": None, "citations": [], "candidates": []}
    return {
        "value": members,
        "status": "contested" if contested else "known",
        "true_from": None if any(t is None for t in true_froms) else max(true_froms),
        "citations": citations,
        "candidates": ordered,
        "member_true_from": {m["title"]: t for m, t in zip(members, true_froms)},
    }


def investor_members(candidates: list[dict]) -> list[str]:
    """Names with an `own`/`filing` candidate or candidates from two or more distinct origins, by code point."""
    by_name: dict[str, list[dict]] = {}
    for c in candidates:
        by_name.setdefault(c["value"].strip(), []).append(c)
    return sorted(n for n, cs in by_name.items()
                  if any(c.get("kind") in ("own", "filing") for c in cs) or len({c.get("origin") for c in cs}) >= 2)


def derive_investors(candidates: list[dict]) -> dict:
    """Stage 4 `investors`: the members' names in place of the selection rule; never contested."""
    ranked = sorted(candidates, key=rank_key)
    members = investor_members(ranked)
    out_candidates = [dict(c, selected=c["value"].strip() in members) for c in ranked]
    if not members:
        return {"value": None, "status": "unknown", "true_from": None, "citations": [], "candidates": out_candidates,
                "member_true_from": {}}
    citations, member_tf = [], {}
    for name in members:
        mine = [c for c in ranked if c["value"].strip() == name]
        citations += [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]} for c in mine]
        dated = [c["true_from"] for c in mine if c.get("true_from") is not None]
        member_tf[name] = min(dated) if dated else None
    tfs = list(member_tf.values())
    return {"value": members, "status": "known", "true_from": None if any(t is None for t in tfs) else max(tfs),
            "citations": citations, "candidates": out_candidates, "member_true_from": member_tf}


def same_selected(field: str, a, b) -> bool:
    """Two selected values of a field are the same (executives: same members by title and name)."""
    if field == "investors":
        return sorted(x.strip() for x in a or []) == sorted(x.strip() for x in b or []) and (a is None) == (b is None)
    if field != "executives":
        if a is None or b is None:
            return a is None and b is None
        return same_value(a, b)
    norm = lambda v: [(m["title"], m["name"].strip()) for m in (v or [])]  # noqa: E731
    return norm(a) == norm(b)


def derive_fields(candidates: list[dict]) -> dict:
    """The eight fields from a build's candidates (each carrying `field`, and `title` for executives)."""
    by_field = {f: [] for f in FIELDS + ("executives", "investors")}
    for c in candidates:
        by_field.setdefault(c["field"], []).append({k: v for k, v in c.items() if k != "field"})
    out = {f: derive_field(by_field[f]) for f in FIELDS}
    out["executives"] = derive_executives(by_field["executives"])
    out["investors"] = derive_investors(by_field["investors"])
    return out
