"""Export / import (§10; stage 3, Upgrades): the envelope and strict validation of an imported state.

Four state shapes are accepted (decisions D26, D44): this service's own (`schema: dossier-stage-4`,
with batches), a stage-3 export (builds, history and feed restored; candidates without an origin
take the host of their URL; no investors), and stage-2 or stage-1 exports, whose dossiers become
one ready build each (`upgrade.py`).
"""
from __future__ import annotations

from . import accounts, domains, errors, lineage, selection, upgrade
from .clock import parse_rfc3339
from .pages import KINDS
from .store import Batch, Dossier, Store, User
from .roles import TITLES
from .support import FIELDS, HEADCOUNT_VALUES
from .timeline import ALL_FIELDS
from .upgrade import need as _need

TRACK = "dossier"
FORMAT_VERSION = 1
SCHEMA = "dossier-stage-4"
SCHEMA_STAGE3 = "dossier-stage-3"


def export(store: Store) -> dict:
    return {"track": TRACK, "format_version": FORMAT_VERSION, "state": store.snapshot(settled=True)}


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _str(obj: dict, key: str, max_len: int | None = None) -> str:
    v = obj.get(key)
    _need(isinstance(v, str) and v != "" and (max_len is None or len(v) <= max_len), f"{key} must be a string")
    return v


def _ts(v, what: str, nullable: bool = False) -> None:
    _need((nullable and v is None) or (isinstance(v, str) and parse_rfc3339(v) is not None), what)


def parse_import(body, restoring: bool = False) -> dict:
    """The parts of a valid export as keyword arguments of Store.replace, or a 422 naming what is wrong."""
    if not isinstance(body, dict):
        raise errors.invalid("import body must be an export object")
    if body.get("track") != TRACK or body.get("format_version") != FORMAT_VERSION \
            or not _is_int(body.get("format_version")):
        raise errors.invalid("wrong track or format_version")
    state = body.get("state")
    if not isinstance(state, dict):
        raise errors.invalid("state must be an object")
    try:
        return _parse_state(state, restoring)
    except upgrade.Invalid as exc:
        raise errors.invalid(f"invalid state: {exc}") from None
    except (TypeError, KeyError, AttributeError, ValueError, IndexError):
        raise errors.invalid("invalid state") from None


def _parse_state(state: dict, restoring: bool = False) -> dict:
    for key in ("users", "tokens", "dossiers", "idempotent"):
        _need(isinstance(state.get(key), list), f"{key} must be a list")
    users, emails = [], set()
    for u in state["users"]:
        _need(isinstance(u, dict), "user must be an object")
        user = User(_str(u, "id", 64), _str(u, "email"), _str(u, "display_name", 100), _str(u, "password_hash"))
        _need(accounts.is_password_hash(user.password_hash), "password_hash")
        _need(user.email.lower() not in emails, "duplicate email")
        emails.add(user.email.lower())
        users.append(user)
    ids = {u.id for u in users}
    _need(len(ids) == len(users), "duplicate user id")
    tokens = {}
    for t in state["tokens"]:
        _need(isinstance(t, dict), "token must be an object")
        token, uid = _str(t, "token"), _str(t, "user_id")
        _need(uid in ids, "token for unknown user")
        tokens[token] = uid
    own = state.get("schema") in (SCHEMA, SCHEMA_STAGE3)
    dossiers = [_parse_own_dossier(d, restoring) if own else _parse_old_dossier(d) for d in state["dossiers"]]
    _need(len({d.domain for d in dossiers}) == len(dossiers), "duplicate domain")
    _need(len({d.id for d in dossiers}) == len(dossiers), "duplicate dossier id")
    idem = {}
    for e in state["idempotent"]:
        _need(isinstance(e, dict), "idempotent entry must be an object")
        key = (_str(e, "user_id"), _str(e, "method"), _str(e, "path"), _str(e, "key", 255))
        _need(key[0] in ids, "idempotent entry for unknown user")
        _need(isinstance(e.get("request"), str) and isinstance(e.get("response"), dict), "idempotent entry")
        idem[key] = {"request": e["request"], "response": e["response"]}
    feed, next_seq = [], 1
    if own:
        feed = state.get("feed")
        _need(isinstance(feed, list) and all(_feed_ok(f) for f in feed), "feed")
        seqs = [f["seq"] for f in feed]
        _need(seqs == sorted(set(seqs)), "feed seq order")
        next_seq = state.get("next_seq")
        _need(_is_int(next_seq) and next_seq > (seqs[-1] if seqs else 0), "next_seq")
    batches = []
    if state.get("schema") == SCHEMA:
        _need(isinstance(state.get("batches"), list), "batches")
        known = {d.domain for d in dossiers}
        for b in state["batches"]:
            _need(isinstance(b, dict) and b.get("owner") in ids and _is_int(b.get("budget")) and _is_int(b.get("spent"))
                  and 0 <= b["spent"] <= b["budget"], "batch")
            _str(b, "id", 64)
            _need(isinstance(b.get("domains"), list) and all(x in known for x in b["domains"]), "batch domains")
            _need(isinstance(b.get("running", []), list), "batch running")
            batches.append(Batch.from_dict(b))
    return {"users": users, "tokens": tokens, "dossiers": dossiers, "idempotent": idem, "feed": feed,
            "next_seq": next_seq, "batches": batches}


def _feed_ok(f) -> bool:
    return (isinstance(f, dict) and _is_int(f.get("seq")) and f["seq"] > 0 and isinstance(f.get("domain"), str)
            and f.get("field") in ALL_FIELDS and f.get("type") in ("change", "correction"))


# ---------------------------------------------------------------- values and candidates

def _parse_value(name: str, value) -> None:
    if name in ("founded_year", "funding_total"):
        _need(_is_int(value), f"field {name} value")
    else:
        _need(isinstance(value, str) and value.strip() != "", f"field {name} value")
    if name == "headcount_range":
        _need(value in HEADCOUNT_VALUES, "headcount_range value")


def _parse_citation(c) -> tuple[str, str, str]:
    _need(isinstance(c, dict) and c.get("provider") in selection.PROVIDER_ORDER, "citation")
    return _str(c, "url"), _str(c, "excerpt", 500), c["provider"]


def _parse_candidate(name: str, c) -> dict:
    _need(isinstance(c, dict), "candidate")
    _parse_value(name, c.get("value"))
    _parse_citation(c)
    _need(c.get("kind") is None or c.get("kind") in KINDS, "candidate kind")
    for key in ("published_at", "retrieved_at", "learned_at"):
        _ts(c.get(key), f"candidate {key}", nullable=True)
    tf = c.get("true_from")
    _need(tf is None or (isinstance(tf, str) and len(tf) == 10), "candidate true_from")
    return c


def _domain_of(d) -> str:
    _need(isinstance(d, dict), "dossier must be an object")
    domain = _str(d, "domain")
    _need(domains.normalise(domain) == domain, "dossier domain")
    _str(d, "id", 64)
    return domain


# ---------------------------------------------------------------- stage-1 and stage-2 dossiers

def _parse_old_dossier(d) -> Dossier:
    domain = _domain_of(d)
    state = d.get("state")
    _need(state in ("ready", "failed"), "dossier state")
    ra = d.get("researched_at")
    _ts(ra, "researched_at", nullable=True)
    spent = d.get("spent_units")
    _need(_is_int(spent) and spent >= 0, "spent_units")
    raw = d.get("fields")
    _need(isinstance(raw, dict) and set(FIELDS) <= set(raw), "fields")

    def field_candidates(name: str, f) -> list[dict]:
        _need(isinstance(f, dict), f"field {name}")
        if "candidates" in f:
            _need(isinstance(f["candidates"], list), f"field {name} candidates")
            return upgrade.candidates_stage2(name, f, ra, _parse_candidate)
        _need(isinstance(f.get("citations"), list), f"field {name}")
        return upgrade.candidates_stage1(name, f, domain, ra, _parse_value, _parse_citation)

    return upgrade.dossier_from_old(d, raw, ra, state, spent, field_candidates)


# ---------------------------------------------------------------- stage-3 dossiers

def _parse_own_dossier(d, restoring: bool = False) -> Dossier:
    _domain_of(d)
    running = restoring and d.get("state") == "building"   # closed by the service at start-up (D43)
    _need(running or d.get("state") in ("ready", "failed") and d.get("settled_state", d["state"]) in ("ready", "failed"),
          "dossier state")
    for key in ("spent_units", "settled_spent"):
        _need(_is_int(d.get(key, 0)) and d.get(key, 0) >= 0, key)
    _need(isinstance(d.get("builds"), list) and isinstance(d.get("history"), dict)
          and isinstance(d.get("first_seen"), list), "dossier log")
    for b in d["builds"]:
        _need(isinstance(b, dict) and b.get("outcome") in ("ready", "failed") and _is_int(b.get("spent")), "build")
        _ts(b.get("time"), "build time")
        _need(isinstance(b.get("candidates"), list) and isinstance(b.get("versions"), dict), "build content")
        for c in b["candidates"]:
            _need(isinstance(c, dict) and c.get("field") in ALL_FIELDS, "build candidate field")
            if not isinstance(c.get("origin"), str) or not c["origin"]:
                c["origin"] = lineage.url_host(_str(c, "url"))   # imported without origin (D44)
            if c["field"] == "investors":
                _need(isinstance(c.get("value"), str) and c["value"].strip() != "", "investors candidate")
                _parse_citation(c)
            elif c["field"] == "executives":
                _need(c.get("title") in TITLES and isinstance(c.get("value"), str), "executives candidate")
                _parse_citation(c)
            else:
                _parse_candidate(c["field"], c)
    for f, entries in d["history"].items():
        _need(f in ALL_FIELDS and isinstance(entries, list), "history field")
        for e in entries:
            _need(isinstance(e, dict) and e.get("type") in ("initial", "change", "correction") and _is_int(e.get("build"))
                  and isinstance(e.get("citations"), list), "history entry")
            _ts(e.get("learned_at"), "history learned_at")
    for pair in d["first_seen"]:
        _need(isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], str), "first_seen")
        _ts(pair[1], "first_seen time")
    dossier = Dossier.from_dict(d)
    dossier.state, dossier.spent_units = d["state"], d["spent_units"]
    return dossier
