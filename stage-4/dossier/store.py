"""Service state: users, tokens, dossiers (with their build log and history), the change feed and
stored idempotent responses.

All mutation happens on the event loop without awaiting in between, so each request's
check-and-set is atomic. `generation` changes on reset and import; a build compares it before
writing so a build cut off by either never touches the state that follows. When a `Persistence`
is attached, every mutation is written through to it before the request answers (stage 3, Restarts).
"""
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field

from . import timeline
from .timeline import ALL_FIELDS


@dataclass
class User:
    id: str
    email: str
    display_name: str
    password_hash: str

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "display_name": self.display_name,
                "password_hash": self.password_hash}


@dataclass
class Batch:
    """A batch (stage 4): domains researched under one shared budget; it doubles as the Meter's batch budget."""
    id: str
    owner: str
    budget: int
    domains: list
    spent: int = 0
    running: list = field(default_factory=list)   # domains whose build this batch started (or queued) and that still run
    queued: list = field(default_factory=list)    # domains whose build waits for budget (D47), in the order given
    reserved: int = 0                              # in-flight reservations of its builds (in memory)
    meters: dict = field(default_factory=dict)    # domain -> Meter of each running build (in memory)

    def can_reserve(self, cost: int) -> bool:
        return self.spent + self.reserved + cost <= self.budget

    def to_dict(self) -> dict:
        return {"id": self.id, "owner": self.owner, "budget": self.budget, "domains": self.domains,
                "spent": self.spent, "running": self.running, "queued": self.queued}

    @classmethod
    def from_dict(cls, d: dict) -> Batch:
        return cls(id=d["id"], owner=d["owner"], budget=d["budget"], domains=list(d["domains"]), spent=d["spent"],
                   running=list(d.get("running", [])), queued=list(d.get("queued", [])))


def empty_history() -> dict:
    return {f: [] for f in ALL_FIELDS}


@dataclass
class Dossier:
    id: str
    domain: str
    state: str = "building"
    spent_units: int = 0
    builds: list = field(default_factory=list)
    history: dict = field(default_factory=empty_history)
    first_seen: dict = field(default_factory=dict)
    # what the dossier was before the running build, for exports taken mid-build (§10) and restarts (D27)
    settled_state: str = "failed"
    settled_spent: int = 0
    inflight: int = 0                 # worst-case cost of calls made and not yet answered (write-ahead, D43)
    batch_id: str | None = None       # the batch whose build is running, if any
    builds_started_at: str | None = None  # time of the running build
    task: asyncio.Task | None = None

    # -------------------------------------------------------------- reading
    def ready_index(self) -> int | None:
        for i in range(len(self.builds) - 1, -1, -1):
            if self.builds[i]["outcome"] == "ready":
                return i
        return None

    @property
    def researched_at(self) -> str | None:
        i = self.ready_index()
        return self.builds[i]["time"] if i is not None else None

    def fields_at(self, index: int | None) -> dict:
        return timeline.view_fields(self.builds, index, self.history)

    def view(self) -> dict:
        return {"dossier_id": self.id, "domain": self.domain, "state": self.state,
                "researched_at": self.researched_at, "spent_units": self.spent_units,
                "fields": self.fields_at(self.ready_index())}

    def view_as_of(self, index: int, spent: int) -> dict:
        return {"dossier_id": self.id, "domain": self.domain, "state": "ready",
                "researched_at": self.builds[index]["time"], "spent_units": spent, "fields": self.fields_at(index)}

    def summary(self) -> dict:
        legal = self.fields_at(self.ready_index())["legal_name"]["value"]
        return {"dossier_id": self.id, "domain": self.domain, "state": self.state, "legal_name": legal,
                "researched_at": self.researched_at, "spent_units": self.spent_units}

    def ref(self) -> dict:
        return {"dossier_id": self.id, "domain": self.domain, "state": self.state}

    def history_view(self) -> dict:
        return {"domain": self.domain,
                "fields": {f: [timeline.public_entry(e) for e in self.history.get(f, [])] for f in ALL_FIELDS}}

    # -------------------------------------------------------------- (de)serialisation
    def to_dict(self, settled: bool = False) -> dict:
        """The persisted form; `settled` gives the dossier as it was before a running build (exports)."""
        building = self.state == "building"
        return {
            "id": self.id, "domain": self.domain,
            "state": self.settled_state if (settled and building) else self.state,
            "spent_units": self.settled_spent if (settled and building) else self.spent_units,
            "settled_state": self.settled_state, "settled_spent": self.settled_spent,
            "inflight": 0 if settled else self.inflight, "batch_id": None if settled else self.batch_id,
            "build_time": None if settled else self.builds_started_at,
            "builds": self.builds, "history": self.history,
            "first_seen": [[k, v] for k, v in self.first_seen.items()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Dossier:
        return cls(id=d["id"], domain=d["domain"], state=d["state"], spent_units=d["spent_units"],
                   builds=d["builds"], history={f: list(d["history"].get(f, [])) for f in ALL_FIELDS},
                   first_seen={k: v for k, v in d["first_seen"]}, settled_state=d.get("settled_state", d["state"]),
                   settled_spent=d.get("settled_spent", d["spent_units"]), inflight=d.get("inflight", 0),
                   batch_id=d.get("batch_id"), builds_started_at=d.get("build_time"))


class Store:
    def __init__(self, persistence=None) -> None:
        self.generation = 0
        self.persistence = persistence
        self.users: dict[str, User] = {}
        self.emails: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self.dossiers: dict[str, Dossier] = {}
        # (user_id, method, path, key) -> {"request": canonical body, "response": body}
        self.idempotent: dict[tuple[str, str, str, str], dict] = {}
        self.feed: list[dict] = []
        self.next_seq = 1
        self.batches: dict[str, Batch] = {}

    # -------------------------------------------------------------- lifecycle
    def replace(self, users: list[User], tokens: dict[str, str], dossiers: list[Dossier], idempotent: dict,
                feed: list[dict] | None = None, next_seq: int = 1, clock: str | None = None,
                batches: list[Batch] | None = None) -> None:
        """Swap in a whole new state, cutting off every running build, and persist it."""
        self.generation += 1
        for d in self.dossiers.values():
            if d.task is not None and not d.task.done():
                d.task.cancel()
        self.users = {u.id: u for u in users}
        self.emails = {u.email.lower(): u.id for u in users}
        self.tokens = dict(tokens)
        self.dossiers = {d.domain: d for d in dossiers}
        self.idempotent = dict(idempotent)
        self.feed = list(feed or [])
        self.next_seq = next_seq
        self.batches = {b.id: b for b in batches or []}
        if self.persistence:
            self.persistence.replace_all(self.snapshot(), clock)

    # -------------------------------------------------------------- users
    def add_user(self, user: User) -> None:
        self.users[user.id] = user
        self.emails[user.email.lower()] = user.id
        if self.persistence:
            self.persistence.put_user(user.to_dict())

    def user_by_email(self, email: str) -> User | None:
        uid = self.emails.get(email.lower())
        return self.users.get(uid) if uid else None

    def issue_token(self, token: str, user_id: str) -> None:
        self.tokens[token] = user_id
        if self.persistence:
            self.persistence.put_token(token, user_id)

    def put_idempotent(self, slot: tuple, record: dict) -> None:
        self.idempotent[slot] = record
        if self.persistence:
            self.persistence.put_idempotent(list(slot), record)

    def save_dossier(self, dossier: Dossier, feed: list[dict] | None = None, batch: Batch | None = None) -> None:
        if self.persistence:
            self.persistence.put_dossier(dossier.to_dict(), feed or [], self.next_seq,
                                         batch.to_dict() if batch else None)

    def save_batch(self, batch: Batch) -> None:
        if self.persistence:
            self.persistence.put_batch(batch.to_dict())

    def new_batch_id(self) -> str:
        while True:
            bid = "b_" + secrets.token_hex(8)
            if bid not in self.batches:
                return bid

    def save_clock(self, value: str | None) -> None:
        if self.persistence:
            self.persistence.put_clock(value)

    def new_dossier_id(self) -> str:
        taken = {d.id for d in self.dossiers.values()}
        while True:
            did = "d_" + secrets.token_hex(8)
            if did not in taken:
                return did

    def unused_user_id(self, make) -> str:
        while True:
            uid = make()
            if uid not in self.users:
                return uid

    # -------------------------------------------------------------- feed
    def add_feed(self, entries: list[dict]) -> list[dict]:
        out = []
        for e in entries:
            out.append(dict(e, seq=self.next_seq))
            self.next_seq += 1
        self.feed.extend(out)
        return out

    def changes(self, since: int, limit: int) -> dict:
        after = [e for e in self.feed if e["seq"] > since]
        return {"changes": after[:limit], "has_more": len(after) > limit}

    # -------------------------------------------------------------- export (stage-3 shape)
    def snapshot(self, settled: bool = False) -> dict:
        return {
            "schema": "dossier-stage-4",
            "users": [u.to_dict() for u in self.users.values()],
            "tokens": [{"token": t, "user_id": uid} for t, uid in self.tokens.items()],
            "dossiers": [d.to_dict(settled) for d in self.dossiers.values()],
            "idempotent": [{"user_id": k[0], "method": k[1], "path": k[2], "key": k[3],
                            "request": v["request"], "response": v["response"]} for k, v in self.idempotent.items()],
            "feed": self.feed,
            "next_seq": self.next_seq,
            "batches": [dict(b.to_dict(), running=[] if settled else b.running, queued=[] if settled else b.queued)
                        for b in self.batches.values()],
        }
