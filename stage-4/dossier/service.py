"""Dossier operations (§7, §8, §10; stage 3): create, refresh, read, list, idempotency, builds,
reset, import, and the build log: history, change feed, as_of and values.

Nothing here awaits between reading and writing the store, so concurrent requests behave as
if run one at a time (§11).
"""
from __future__ import annotations

import asyncio
import json
import logging

from . import accounts, domains, errors, exchange, timeline, upgrade
from .clock import Clock, format_ts, parse_rfc3339
from .pipeline import run_build
from .provider import Deadline, Gateway, Meter
from .store import Dossier, Store, User

log = logging.getLogger("dossier.service")
# Last resort behind the per-call deadline of provider.Deadline: a build never stays `building` past 300 s.
BUILD_HARD_LIMIT = 298.0


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Service:
    def __init__(self, gateway: Gateway | None = None, persistence=None) -> None:
        self.store = Store(persistence)
        self.clock = Clock()
        self.gateway = gateway or Gateway()
        if persistence is not None:
            self._restore(persistence)

    def _restore(self, persistence) -> None:
        """Read the stored state at start-up; a build cut off by a stop is abandoned (decision D27)."""
        loaded = persistence.load()
        if loaded is None:
            self.store.replace([], {}, [], {}, clock=None)
            return
        state, clock = loaded
        parts = exchange.parse_import({"track": exchange.TRACK, "format_version": exchange.FORMAT_VERSION,
                                       "state": state}, restoring=True)
        for dossier in parts["dossiers"]:
            if dossier.state == "building":
                self._close_interrupted(dossier, {b.id: b for b in parts["batches"]})
        self.store.replace(**parts, clock=clock)
        if clock is not None:
            self.clock.set(parse_rfc3339(clock))

    @staticmethod
    def _close_interrupted(dossier: Dossier, batches: dict) -> None:
        """A build running at an abrupt stop ends `failed`: its in-flight reservations count as billed (D43)."""
        dossier.spent_units += dossier.inflight
        batch = batches.get(dossier.batch_id) if dossier.batch_id else None
        if batch is not None:
            batch.spent = min(batch.budget, batch.spent + dossier.inflight)
            if dossier.domain in batch.running:
                batch.running.remove(dossier.domain)
        time = dossier.builds_started_at or (dossier.builds[-1]["time"] if dossier.builds else None)
        if time is not None:
            dossier.builds.append({"time": time, "outcome": "failed", "spent": dossier.spent_units - dossier.settled_spent,
                                   "candidates": [], "versions": {}})
        dossier.state, dossier.inflight, dossier.batch_id = "failed", 0, None
        dossier.settled_state, dossier.settled_spent = "failed", dossier.spent_units

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
        self.clock.set(when)
        self.store.replace(users, {}, [], {}, clock=now)

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
        self.store.save_clock(now)

    def export(self) -> dict:
        return exchange.export(self.store)

    def import_state(self, body) -> None:
        parts = exchange.parse_import(body)
        self.store.replace(**parts, clock=self.clock.fixed_iso())

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
        self.store.put_idempotent(slot, {"request": request, "response": body})
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
                     or (d.summary()["legal_name"] or "").lower().find(needle) >= 0]
        page = items[offset:offset + limit]
        return {"dossiers": [d.summary() for d in page], "has_more": offset + limit < len(items)}

    # -------------------------------------------------------------- stage-3 reads
    def read_as_of(self, raw_domain: str, as_of: str) -> dict:
        when = _timestamp(as_of, "as_of")
        dossier = self._dossier(raw_domain)
        index = timeline.snapshot_index(dossier.builds, when)
        if index is None:
            raise errors.not_found("no build of this dossier completed ready at or before as_of")
        return dossier.view_as_of(index, timeline.spent_upto(dossier.builds, when))

    def values(self, raw_domain: str, true_at: str | None, as_of: str | None) -> dict:
        if true_at is None or not _is_date(true_at):
            raise errors.invalid("true_at must be a YYYY-MM-DD date")
        when = _timestamp(as_of, "as_of") if as_of is not None else self.clock.now()
        dossier = self._dossier(raw_domain)
        if timeline.snapshot_index(dossier.builds, when) is None:
            raise errors.not_found("no build of this dossier completed ready at or before as_of")
        return {"domain": dossier.domain, "true_at": true_at, "as_of": as_of if as_of is not None else format_ts(when),
                "fields": timeline.values_at(dossier.builds, true_at, when)}

    def history(self, raw_domain: str) -> dict:
        return self._dossier(raw_domain).history_view()

    def changes(self, since: int, limit: int) -> dict:
        return self.store.changes(since, limit)

    def _dossier(self, raw_domain: str) -> Dossier:
        dossier = self.store.dossiers.get(self.domain_or_422(raw_domain))
        if dossier is None:
            raise errors.not_found("no dossier for this domain")
        return dossier

    # -------------------------------------------------------------- builds
    def _start_build(self, dossier: Dossier, batch=None) -> None:
        dossier.state = "building"
        build_time = format_ts(self.clock.now())
        dossier.builds_started_at = build_time
        generation = self.store.generation
        if batch is not None:
            dossier.batch_id = batch.id
            batch.running.append(dossier.domain)
        self.store.save_dossier(dossier, batch=batch)
        dossier.task = asyncio.get_running_loop().create_task(self._build(dossier, generation, build_time, batch))

    def _current(self, dossier: Dossier, generation: int) -> bool:
        return self.store.generation == generation and self.store.dossiers.get(dossier.domain) is dossier

    async def _build(self, dossier: Dossier, generation: int, build_time: str, batch=None) -> None:
        base = dossier.spent_units

        def on_update() -> None:
            # settled spending and in-flight reservations, durable before the next call is made (D43)
            if self._current(dossier, generation):
                dossier.spent_units, dossier.inflight = base + meter.spent, meter.reserved
                self.store.save_dossier(dossier, batch=batch)

        meter = Meter(lambda cost: None, deadline=Deadline(self.gateway.live), batch=batch, on_update=on_update)
        try:
            result = await asyncio.wait_for(run_build(self.gateway, dossier.domain, meter, build_time), BUILD_HARD_LIMIT)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            log.error("build of %s hit the hard limit", dossier.domain)
            result = None
        except Exception:  # noqa: BLE001 - a build never takes the service down
            log.exception("build of %s crashed", dossier.domain)
            result = None
        if not self._current(dossier, generation):
            return
        if result is None and meter.budget_blocked:
            result = ([], {})   # stopped by its batch's budget: it completes with what it obtained (D41)
        feed = self._record_build(dossier, build_time, meter.spent, result)
        dossier.settled_state, dossier.settled_spent = dossier.state, dossier.spent_units
        dossier.task, dossier.inflight, dossier.batch_id = None, 0, None
        if batch is not None and dossier.domain in batch.running:
            batch.running.remove(dossier.domain)
        self.store.save_dossier(dossier, feed, batch=batch)

    def _record_build(self, dossier: Dossier, build_time: str, spent: int, result) -> list[dict]:
        """Append the build to the log; a ready one adds its history entries and feed entries (stage 3)."""
        if result is None:
            dossier.builds.append({"time": build_time, "outcome": "failed", "spent": spent, "candidates": [],
                                   "versions": {}})
            dossier.state = "failed"
            return []
        candidates, versions = result
        for c in candidates:
            c["learned_at"] = dossier.first_seen.setdefault(upgrade.first_seen_key(c), build_time)
        dossier.builds.append({"time": build_time, "outcome": "ready", "spent": spent, "candidates": candidates,
                               "versions": versions})
        dossier.state = "ready"
        entries = []
        for field, entry in timeline.new_entries(dossier.builds, len(dossier.builds) - 1):
            dossier.history[field].append(entry)
            if entry["type"] != "initial":
                entries.append({"domain": dossier.domain, "field": field, "type": entry["type"], "from": entry["from"],
                                "to": entry["value"], "true_from": entry["true_from"], "learned_at": build_time})
        return self.store.add_feed(entries)


def _timestamp(value: str, name: str):
    when = parse_rfc3339(value) if isinstance(value, str) else None
    if when is None:
        raise errors.invalid(f"{name} must be an RFC 3339 timestamp with an offset")
    return when


def _is_date(value: str) -> bool:
    import datetime as dt
    import re
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _object(body) -> dict:
    if not isinstance(body, dict):
        raise errors.malformed("body must be a JSON object")
    return body
