"""Export / import (§10): the envelope and strict validation of an imported state."""
from __future__ import annotations

from . import accounts, domains, errors
from .clock import parse_rfc3339
from .store import Dossier, Store, User
from .support import FIELDS, HEADCOUNT_VALUES

TRACK = "dossier"
FORMAT_VERSION = 1


def export(store: Store) -> dict:
    return {"track": TRACK, "format_version": FORMAT_VERSION, "state": store.export_state()}


class _Invalid(Exception):
    pass


def _need(cond: bool, what: str) -> None:
    if not cond:
        raise _Invalid(what)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _str(obj: dict, key: str, max_len: int | None = None) -> str:
    v = obj.get(key)
    _need(isinstance(v, str) and v != "" and (max_len is None or len(v) <= max_len), f"{key} must be a string")
    return v


def parse_import(body) -> tuple[list[User], dict[str, str], list[Dossier], dict]:
    """The parts of a valid export, or a 422 naming what is wrong."""
    if not isinstance(body, dict):
        raise errors.invalid("import body must be an export object")
    if body.get("track") != TRACK or body.get("format_version") != FORMAT_VERSION \
            or not _is_int(body.get("format_version")):
        raise errors.invalid("wrong track or format_version")
    state = body.get("state")
    if not isinstance(state, dict):
        raise errors.invalid("state must be an object")
    try:
        return _parse_state(state)
    except _Invalid as exc:
        raise errors.invalid(f"invalid state: {exc}") from None
    except (TypeError, KeyError, AttributeError, ValueError):
        raise errors.invalid("invalid state") from None


def _parse_state(state: dict):
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
    dossiers = [_parse_dossier(d) for d in state["dossiers"]]
    _need(len({d.domain for d in dossiers}) == len(dossiers), "duplicate domain")
    _need(len({d.id for d in dossiers}) == len(dossiers), "duplicate dossier id")
    idem = {}
    for e in state["idempotent"]:
        _need(isinstance(e, dict), "idempotent entry must be an object")
        key = (_str(e, "user_id"), _str(e, "method"), _str(e, "path"), _str(e, "key", 255))
        _need(key[0] in ids, "idempotent entry for unknown user")
        _need(isinstance(e.get("request"), str) and isinstance(e.get("response"), dict), "idempotent entry")
        idem[key] = {"request": e["request"], "response": e["response"]}
    return users, tokens, dossiers, idem


def _parse_dossier(d) -> Dossier:
    _need(isinstance(d, dict), "dossier must be an object")
    domain = _str(d, "domain")
    _need(domains.normalise(domain) == domain, "dossier domain")
    state = d.get("state")
    _need(state in ("ready", "failed"), "dossier state")
    ra = d.get("researched_at")
    _need(ra is None or (isinstance(ra, str) and parse_rfc3339(ra) is not None), "researched_at")
    spent = d.get("spent_units")
    _need(_is_int(spent) and spent >= 0, "spent_units")
    raw_fields = d.get("fields")
    _need(isinstance(raw_fields, dict) and set(raw_fields) == set(FIELDS), "fields")
    fields = {f: _parse_field(f, raw_fields[f]) for f in FIELDS}
    return Dossier(id=_str(d, "id", 64), domain=domain, state=state, fields=fields, researched_at=ra,
                   spent_units=spent, settled_state=state, settled_spent=spent)


def _parse_field(name: str, f) -> dict:
    _need(isinstance(f, dict) and isinstance(f.get("citations"), list), f"field {name}")
    value = f.get("value")
    if value is None:
        _need(f["citations"] == [], f"field {name} citations")
        return {"value": None, "citations": []}
    if name in ("founded_year", "funding_total"):
        _need(_is_int(value), f"field {name} value")
    else:
        _need(isinstance(value, str) and value, f"field {name} value")
    if name == "headcount_range":
        _need(value in HEADCOUNT_VALUES, "headcount_range value")
    cits = []
    for c in f["citations"]:
        _need(isinstance(c, dict), "citation")
        _need(c.get("provider") in ("nimble", "tavily"), "citation provider")
        excerpt = _str(c, "excerpt", 500)
        cits.append({"url": _str(c, "url"), "excerpt": excerpt, "provider": c["provider"]})
    _need(len(cits) >= 1, f"field {name} without citations")
    return {"value": value, "citations": cits}
