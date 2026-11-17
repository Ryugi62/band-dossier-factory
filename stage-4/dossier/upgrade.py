"""Upgrades (stage 3): a dossier from a stage-1 or stage-2 export becomes one ready build plus history.

A stage-2 export holds each dossier's settled candidates (decision D25); a stage-1 export holds the
value and citations, and each citation whose excerpt supports the value becomes a candidate
(decision D16). Either way the state counts as one build that completed `ready` at the dossier's
`researched_at`, spending its `spent_units`; each candidate URL is one page version of it;
candidates are learned at their `retrieved_at`; every field with a value gets one `initial` entry;
`executives` stays unknown with no history entry.
"""
from __future__ import annotations

import datetime as dt

from . import lineage, selection, support
from .store import Dossier, empty_history
from .support import FIELDS


class Invalid(Exception):
    pass


def need(cond: bool, what: str) -> None:
    if not cond:
        raise Invalid(what)


def utc_date(published_at: str | None) -> str | None:
    if published_at is None:
        return None
    return dt.datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(dt.timezone.utc).date().isoformat()


def first_seen_key(c: dict) -> str:
    import json
    return json.dumps([c["field"], c.get("title", ""), c["value"], c["url"], c["provider"]], ensure_ascii=False)


def candidates_stage2(name: str, f: dict, retrieved_default: str | None, check_candidate) -> list[dict]:
    out = []
    for c in f["candidates"]:
        c = check_candidate(name, c)
        retrieved = c.get("retrieved_at") or retrieved_default
        out.append({"field": name, "value": c["value"], "url": c["url"], "excerpt": c["excerpt"],
                    "provider": c["provider"], "kind": c.get("kind"), "published_at": c.get("published_at"),
                    "true_from": utc_date(c.get("published_at")), "retrieved_at": retrieved, "learned_at": retrieved,
                    "origin": c.get("origin") or lineage.url_host(c["url"])})
    return out


def candidates_stage1(name: str, f: dict, domain: str, researched_at: str | None, check_value, check_citation) -> list:
    value = f.get("value")
    if value is None:
        need(f.get("citations") == [], f"field {name} citations")
        return []
    check_value(name, value)
    out, seen = [], set()
    for c in f.get("citations") or []:
        url, excerpt, provider = check_citation(c)
        if not support.supports(excerpt, name, value, domain) or (url, provider) in seen:
            continue
        seen.add((url, provider))
        out.append({"field": name, "value": value, "url": url, "excerpt": excerpt, "provider": provider, "kind": None,
                    "published_at": None, "true_from": None, "retrieved_at": researched_at, "learned_at": researched_at,
                    "origin": lineage.url_host(url)})
    return out


def dossier_from_old(d: dict, raw_fields: dict, researched_at: str | None, state: str, spent: int,
                     field_candidates) -> Dossier:
    """The stage-3 dossier for a stage-1/2 exported one; `field_candidates(name, f)` gives a field's candidates."""
    candidates = []
    for name in FIELDS:
        candidates.extend(field_candidates(name, raw_fields[name]))
    dossier = Dossier(id=d["id"], domain=d["domain"], state=state, spent_units=spent, settled_state=state,
                      settled_spent=spent, history=empty_history())
    if researched_at is None:
        need(not candidates, "candidates without researched_at")
        return dossier
    versions = {}
    for c in candidates:
        versions.setdefault(c["url"], c["true_from"])
        dossier.first_seen.setdefault(first_seen_key(c), c["learned_at"])
    dossier.builds = [{"time": researched_at, "outcome": "ready", "spent": spent, "candidates": candidates,
                       "versions": versions}]
    derived = selection.derive_fields(candidates)
    for name in FIELDS:
        v = derived[name]
        if v["value"] is not None:
            dossier.history[name].append({"type": "initial", "value": v["value"], "true_from": v["true_from"],
                                          "learned_at": researched_at, "citations": v["citations"], "build": 0,
                                          "from": None})
    return dossier
