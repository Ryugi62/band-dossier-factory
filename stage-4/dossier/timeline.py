"""Change over time (stage 3): build log views, history and feed entries, as_of, and page versions.

Pure functions over plain data. A dossier's build log is a list of builds in build order:
`{"time", "outcome": "ready"|"failed", "spent", "candidates": [...], "versions": {url: true_from}}`;
history entries carry the index of the build that added them (`build`), never shown.
"""
from __future__ import annotations

import datetime as dt

from . import corroboration
from .selection import derive_fields, same_selected
from .support import FIELDS

ALL_FIELDS = FIELDS + ("executives", "investors")


def instant(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00").replace("z", "+00:00"))


# ---------------------------------------------------------------- views of one build

def _public_candidate(c: dict) -> dict:
    return {k: v for k, v in c.items() if k != "field"}


def field_learned_at(history: dict, field: str, upto: int) -> str | None:
    """`learned_at` of the field's selected value as of build `upto`: its latest history entry's (decision D32)."""
    entries = [e for e in history.get(field, []) if e["build"] <= upto]
    if not entries or entries[-1]["value"] is None:
        return None
    return entries[-1]["learned_at"]


def view_fields(builds: list[dict], index: int | None, history: dict) -> dict:
    """The eight fields of ready build `index` as the API shows them: learned_at from history up to that
    build, origins and corroboration from the builds up to it (stage 4)."""
    derived = derive_fields(builds[index]["candidates"] if index is not None else [])
    upto = index if index is not None else -1
    keys = corroboration.origin_keys(builds, index, ALL_FIELDS)
    out = {}
    for f in ALL_FIELDS:
        d = derived[f]
        out[f] = {
            "value": d["value"], "status": d["status"], "true_from": d["true_from"],
            "learned_at": field_learned_at(history, f, upto) if d["value"] is not None else None,
            "citations": d["citations"], "candidates": [_public_candidate(c) for c in d["candidates"]],
            **keys[f],
        }
    return out


# ---------------------------------------------------------------- history and feed

def change_type(field: str, old: dict, new: dict) -> str:
    """`correction` or `change` for a differing selected value (Changes and corrections; executives by title,
    investors by name)."""
    if field == "investors":
        old_names, new_names = set(old["value"] or []), set(new["value"] or [])
        for name in old_names ^ new_names:
            tf = (new.get("member_true_from") or {}).get(name)
            if name not in new_names or tf is None or old["true_from"] is None or not tf <= old["true_from"]:
                return "change"
        return "correction"
    if field != "executives":
        if old["value"] is not None and new["value"] is not None and old["true_from"] is not None \
                and new["true_from"] is not None and new["true_from"] <= old["true_from"]:
            return "correction"
        return "change"
    om = {m["title"]: m["name"].strip() for m in old["value"] or []}
    nm = {m["title"]: m["name"].strip() for m in new["value"] or []}
    otf, ntf = old.get("member_true_from") or {}, new.get("member_true_from") or {}
    differing = [t for t in set(om) | set(nm) if om.get(t) != nm.get(t)]
    for t in differing:
        if t not in om or t not in nm or otf.get(t) is None or ntf.get(t) is None or not ntf[t] <= otf[t]:
            return "change"
    return "correction"


def new_entries(builds: list[dict], build_no: int) -> list[tuple[str, dict]]:
    """History entries (field, entry) added by ready build `build_no`, in field order then executives."""
    build = builds[build_no]
    new = derive_fields(build["candidates"])
    earlier = [i for i in range(build_no) if builds[i]["outcome"] == "ready"]
    out = []
    if not earlier:
        for f in ALL_FIELDS:
            if new[f]["value"] is not None:
                out.append((f, _entry("initial", new[f], build["time"], build_no)))
        return out
    old = derive_fields(builds[earlier[-1]]["candidates"])
    for f in ALL_FIELDS:
        if not same_selected(f, old[f]["value"], new[f]["value"]):
            out.append((f, _entry(change_type(f, old[f], new[f]), new[f], build["time"], build_no, old[f]["value"])))
    return out


def _entry(kind: str, d: dict, learned_at: str, build_no: int, previous=None) -> dict:
    value = d["value"]
    return {"type": kind, "value": value, "true_from": d["true_from"] if value is not None else None,
            "learned_at": learned_at, "citations": d["citations"] if value is not None else [],
            "build": build_no, "from": previous}


def public_entry(e: dict) -> dict:
    return {k: e[k] for k in ("type", "value", "true_from", "learned_at", "citations")}


# ---------------------------------------------------------------- as_of

def snapshot_index(builds: list[dict], as_of: dt.datetime) -> int | None:
    """The last ready build, in build order, whose time is at or before `as_of`."""
    found = None
    for i, b in enumerate(builds):
        if b["outcome"] == "ready" and instant(b["time"]) <= as_of:
            found = i
    return found


def spent_upto(builds: list[dict], as_of: dt.datetime) -> int:
    return sum(b["spent"] for b in builds if instant(b["time"]) <= as_of)


# ---------------------------------------------------------------- page versions and /values

def versions_known(builds: list[dict], as_of: dt.datetime) -> dict:
    """{url: [(from, until, candidates)]}: the versions of each URL that ready builds up to `as_of` gathered.

    A later version replaces every earlier version of its URL dated on or after its own date (all of
    them when it has no date) and ends the latest earlier version it does not replace on its date.
    """
    out: dict[str, list] = {}
    for b in builds:
        if b["outcome"] != "ready" or instant(b["time"]) > as_of:
            continue
        for url, true_from in b["versions"].items():
            cands = [c for c in b["candidates"] if c["url"] == url]
            vs = out.setdefault(url, [])
            if true_from is None:
                vs.clear()
            else:
                vs[:] = [v for v in vs if not (v[0] is not None and v[0] >= true_from)]
                if vs and (vs[-1][1] is None or vs[-1][1] > true_from):
                    vs[-1] = (vs[-1][0], true_from, vs[-1][2])
            vs.append((true_from, None, cands))
    return out


def candidates_at(builds: list[dict], true_at: str, as_of: dt.datetime) -> list[dict]:
    """Candidates of every version holding on `true_at`; a version with no date holds on no date."""
    out = []
    for vs in versions_known(builds, as_of).values():
        for start, until, cands in vs:
            if start is not None and start <= true_at and (until is None or true_at < until):
                out.extend(cands)
    return out


def values_at(builds: list[dict], true_at: str, as_of: dt.datetime) -> dict:
    derived = derive_fields(candidates_at(builds, true_at, as_of))
    return {f: {"value": derived[f]["value"], "true_from": derived[f]["true_from"],
                "citations": derived[f]["citations"]} for f in ALL_FIELDS}
