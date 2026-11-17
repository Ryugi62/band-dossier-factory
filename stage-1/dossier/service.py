"""Dossier operations (§7, §8, §10): create, refresh, read, list, idempotency, builds, reset, import.

Nothing here awaits between reading and writing the store, so concurrent requests behave as
if run one at a time (§11).
"""
from __future__ import annotations

import asyncio
import json
import logging

from . import accounts, domains, errors, exchange
from .clock import Clock, format_ts, parse_rfc3339
from .pipeline import run_build
from .provider import Gateway, Meter
from .store import Dossier, Store, User

log = logging.getLogger("dossier.service")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Service:
    def __init__(self, gateway: Gateway | None = None) -> None:
        self.store = Store()
        self.clock = Clock()
        self.gateway = gateway or Gateway()

    # -------------------------------------------------------------- control
    async def reset(self, body) -> None:
        if not isinstance(body, dict):
            raise errors.malformed("fixture must be a JSON object")
        now = body.get("now")
        if now is not None and not isinstance(now, str):
            raise errors.malformed("now must be a string")
        users_raw = body.get("users", [])
        if users_raw is None:
            users_raw = []
        if not isinstance(users_raw, list) or not all(isinstance(u, dict) for u in users_raw):
            raise errors.malformed("users must be a list of objects")
        if now is None:
            raise errors.invalid("now is required")
        when = parse_rfc3339(now)
        if when is None:
            raise errors.invalid("now must be an RFC 3339 timestamp with an offset")
        seeds = []
        for u in users_raw:
            uid = u.get("id")
            if uid is not None and not isinstance(uid, str):
                raise errors.malformed("user id must be a string")
            email, password, display_name = accounts.require_strs(u, "email", "password", "display_name")
            if not uid or len(uid) > 64:
                raise errors.invalid("every seeded user needs an id of 1 to 64 characters")
            seeds.append((uid, email, password, display_name))
        if len({s[1].lower() for s in seeds}) != len(seeds):
            raise errors.invalid("two users share an email")
        if len({s[0] for s in seeds}) != len(seeds):
            raise errors.invalid("two users share an id")
        hashes = await asyncio.gather(*(accounts.hash_password_async(s[2]) for s in seeds))
        users = [User(s[0], s[1], s[3], h) for s, h in zip(seeds, hashes)]
        self.store.replace(users, {}, [], {})
        self.clock.set(when)

    def set_clock(self, body) -> None:
        if not isinstance(body, dict):
            raise errors.malformed("body must be a JSON object")
        now = body.get("now")
        if now is None:
            raise errors.invalid("now is required")
        if not isinstance(now, str):
            raise errors.malformed("now must be a string")
        when = parse_rfc3339(now)
        if when is None:
            raise errors.invalid("now must be an RFC 3339 timestamp with an offset")
        if self.clock.is_earlier(when):
            raise errors.invalid("now is earlier than the clock")
        self.clock.set(when)

    def export(self) -> dict:
        return exchange.export(self.store)

    def import_state(self, body) -> None:
        users, tokens, dossiers, idem = exchange.parse_import(body)
        self.store.replace(users, tokens, dossiers, idem)

    # -------------------------------------------------------------- accounts
    async def signup(self, body) -> dict:
        email, password, display_name = accounts.validate_signup(_object(body))
        if self.store.user_by_email(email):
            raise errors.ApiError(409, "email_taken", "email already registered")
        password_hash = await accounts.hash_password_async(password)
        if self.store.user_by_email(email):
            raise errors.ApiError(409, "email_taken", "email already registered")
        user = User(self.store.unused_user_id(accounts.new_user_id), email, display_name, password_hash)
        self.store.add_user(user)
        return self._session(user)

    async def login(self, body) -> dict:
        email, password = accounts.validate_login(_object(body))
        user = self.store.user_by_email(email)
        if user is None or not await accounts.verify_password_async(password, user.password_hash):
            raise errors.unauthenticated("wrong email or password")
        if self.store.users.get(user.id) is not user:
            raise errors.unauthenticated("wrong email or password")
        return self._session(user)

    def _session(self, user: User) -> dict:
        token = accounts.new_token()
        self.store.issue_token(token, user.id)
        return {"user_id": user.id, "display_name": user.display_name, "token": token}

    def authenticate(self, header: str | None) -> str:
        if not header:
            raise errors.unauthenticated()
        scheme, _, token = header.strip().partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token or token not in self.store.tokens:
            raise errors.unauthenticated()
        return self.store.tokens[token]

    # -------------------------------------------------------------- idempotent writes
    def idempotent(self, user_id: str, method: str, path: str, key: str, request: str, perform):
        """(status, body): a replay returns 200 with the stored body; a fresh success is stored."""
        slot = (user_id, method, path, key)
        stored = self.store.idempotent.get(slot)
        if stored is not None:
            if stored["request"] != request:
                raise errors.ApiError(409, "idempotency_key_reuse", "key already used with a different body")
            return 200, stored["response"]
        status, body = perform()
        self.store.idempotent[slot] = {"request": request, "response": body}
        return status, body

    def create(self, body: dict) -> tuple[int, dict]:
        raw = body.get("domain")
        if raw is None:
            raise errors.invalid("domain is required")
        if not isinstance(raw, str):
            raise errors.malformed("domain must be a string")
        domain = domains.normalise(raw)
        if domain is None:
            raise errors.invalid("domain is not a valid host name")
        existing = self.store.dossiers.get(domain)
        if existing is not None:
            return 200, existing.ref()
        dossier = Dossier(id=self.store.new_dossier_id(), domain=domain)
        self.store.dossiers[domain] = dossier
        self._start_build(dossier)
        return 202, dossier.ref()

    def refresh(self, raw_domain: str) -> tuple[int, dict]:
        dossier = self.store.dossiers.get(self.domain_or_422(raw_domain))
        if dossier is None:
            raise errors.not_found("no dossier for this domain")
        if dossier.state != "building":
            dossier.settled_state, dossier.settled_spent = dossier.state, dossier.spent_units
            dossier.state = "building"
            self._start_build(dossier)
        return 202, dossier.ref()

    # -------------------------------------------------------------- reads
    @staticmethod
    def domain_or_422(raw: str) -> str:
        domain = domains.normalise(raw)
        if domain is None:
            raise errors.invalid("domain is not a valid host name")
        return domain

    def read(self, raw_domain: str) -> dict:
        dossier = self.store.dossiers.get(self.domain_or_422(raw_domain))
        if dossier is None:
            raise errors.not_found("no dossier for this domain")
        return dossier.view()

    def list(self, q: str | None, limit: int, offset: int) -> dict:
        items = sorted(self.store.dossiers.values(), key=lambda d: d.domain)
        if q:
            needle = q.lower()
            items = [d for d in items if needle in d.domain.lower()
                     or (d.fields["legal_name"]["value"] or "").lower().find(needle) >= 0]
        page = items[offset:offset + limit]
        return {"dossiers": [d.summary() for d in page], "has_more": offset + limit < len(items)}

    # -------------------------------------------------------------- builds
    def _start_build(self, dossier: Dossier) -> None:
        dossier.state = "building"
        build_time = format_ts(self.clock.now())
        generation = self.store.generation
        dossier.task = asyncio.get_running_loop().create_task(self._build(dossier, generation, build_time))

    def _current(self, dossier: Dossier, generation: int) -> bool:
        return self.store.generation == generation and self.store.dossiers.get(dossier.domain) is dossier

    async def _build(self, dossier: Dossier, generation: int, build_time: str) -> None:
        def on_charge(cost: int) -> None:
            if self._current(dossier, generation):
                dossier.spent_units += cost

        meter = Meter(on_charge)
        try:
            fields = await run_build(self.gateway, dossier.domain, meter)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a build never takes the service down
            log.exception("build of %s crashed", dossier.domain)
            fields = None
        if not self._current(dossier, generation):
            return
        if fields is None:
            dossier.state = "failed"
        else:
            dossier.fields, dossier.researched_at, dossier.state = fields, build_time, "ready"
        dossier.settled_state, dossier.settled_spent = dossier.state, dossier.spent_units
        dossier.task = None


def _object(body) -> dict:
    if not isinstance(body, dict):
        raise errors.malformed("body must be a JSON object")
    return body
