"""Origins and corroboration of selected values (stage 4, Origins; decision D38). Pure functions.

Standing origins are computed from the build log: for each selected value (or member of
`executives`/`investors`) the union of the origins of its candidates over the ready builds since it
last became selected (a member), up to the build being shown.
"""
from __future__ import annotations

import json

from .selection import derive_fields


def _groups(field: str, derived: dict) -> dict:
    """{member key: [origins of its candidates]} for the field's selected value in one build."""
    d = derived[field]
    value = d["value"]
    if value is None:
        return {}
    cands = d["candidates"]
    if field == "executives":
        return {(m["title"], m["name"]): [c["origin"] for c in cands
                                          if c.get("title") == m["title"] and c["value"].strip() == m["name"]]
                for m in value}
    if field == "investors":
        return {n: [c["origin"] for c in cands if c["value"].strip() == n] for n in value}
    key = json.dumps(value.strip() if isinstance(value, str) else value)
    return {key: [c["origin"] for c in cands
                  if json.dumps(c["value"].strip() if isinstance(c["value"], str) else c["value"]) == key]}


def origin_keys(builds: list[dict], index: int | None, fields: tuple) -> dict:
    """{field: {"origins", "corroborated", "corroborated_since"}} as of ready build `index`."""
    empty = {"origins": [], "corroborated": False, "corroborated_since": None}
    if index is None:
        return {f: dict(empty) for f in fields}
    # per field: {member key: (standing origins, first time with two or more)} over the current run of each member
    runs: dict[str, dict] = {f: {} for f in fields}
    current: dict[str, dict] = {}
    for i in range(index + 1):
        b = builds[i]
        if b["outcome"] != "ready":
            continue
        derived = derive_fields(b["candidates"])
        for f in fields:
            groups = _groups(f, derived)
            kept = {k: v for k, v in runs[f].items() if k in groups}
            for k, origins in groups.items():
                standing, since = kept.get(k, (set(), None))
                standing = standing | set(origins)
                if since is None and len(standing) >= 2:
                    since = b["time"]
                kept[k] = (standing, since)
            runs[f] = kept
            if i == index:
                current[f] = groups
    out = {}
    for f in fields:
        groups = current.get(f, {})
        if not groups:
            out[f] = dict(empty)
            continue
        origins = sorted({o for v in groups.values() for o in v})
        if f in ("executives", "investors"):
            corroborated = all(len(set(v)) >= 2 for v in groups.values())
        else:
            corroborated = len(origins) >= 2
        sinces = [runs[f][k][1] for k in groups]
        out[f] = {"origins": origins, "corroborated": corroborated,
                  "corroborated_since": None if any(s is None for s in sinces) else max(sinces, key=_instant_key)}
    return out


def _instant_key(ts: str):
    import datetime as dt
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
