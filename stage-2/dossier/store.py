"""Service state: users, tokens, dossiers and stored idempotent responses.

All mutation happens on the event loop without awaiting in between, so each request's
check-and-set is atomic. `generation` changes on reset and import; a build compares it
before writing so a build cut off by either never touches the state that follows.
"""
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field

from .support import FIELDS


@dataclass
class User:
    id: str
    email: str
    display_name: str
    password_hash: str


def empty_field() -> dict:
    return {"value": None, "status": "unknown", "citations": [], "candidates": []}


def empty_fields() -> dict:
    return {f: empty_field() for f in FIELDS}


@dataclass
class Dossier:
    id: str
    domain: str
    state: str = "building"
    fields: dict = field(default_factory=empty_fields)
    researched_at: str | None = None
    spent_units: int = 0
    # what the dossier was before the running build, for exports taken mid-build (§10)
    settled_state: str = "failed"
    settled_spent: int = 0
    task: asyncio.Task | None = None

    def view(self) -> dict:
        return {
            "dossier_id": self.id,
            "domain": self.domain,
            "state": self.state,
            "researched_at": self.researched_at,
            "spent_units": self.spent_units,
            "fields": {f: field_view(self.fields[f]) for f in FIELDS},
        }

    def summary(self) -> dict:
        return {"dossier_id": self.id, "domain": self.domain, "state": self.state,
                "legal_name": self.fields["legal_name"]["value"], "researched_at": self.researched_at,
                "spent_units": self.spent_units}

    def ref(self) -> dict:
        return {"dossier_id": self.id, "domain": self.domain, "state": self.state}


def field_view(stored: dict) -> dict:
    return {"value": stored["value"], "status": stored["status"],
            "citations": [dict(c) for c in stored["citations"]],
            "candidates": [dict(c) for c in stored["candidates"]]}


class Store:
    def __init__(self) -> None:
        self.generation = 0
        self.users: dict[str, User] = {}
        self.emails: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self.dossiers: dict[str, Dossier] = {}
        # (user_id, method, path, key) -> {"request": canonical body, "response": body}
        self.idempotent: dict[tuple[str, str, str, str], dict] = {}

    # -------------------------------------------------------------- lifecycle
    def replace(self, users: list[User], tokens: dict[str, str], dossiers: list[Dossier],
                idempotent: dict) -> None:
        """Swap in a whole new state, cutting off every running build."""
        self.generation += 1
        for d in self.dossiers.values():
            if d.task is not None and not d.task.done():
                d.task.cancel()
        self.users = {u.id: u for u in users}
        self.emails = {u.email.lower(): u.id for u in users}
        self.tokens = dict(tokens)
        self.dossiers = {d.domain: d for d in dossiers}
        self.idempotent = dict(idempotent)

    # -------------------------------------------------------------- users
    def add_user(self, user: User) -> None:
        self.users[user.id] = user
        self.emails[user.email.lower()] = user.id

    def user_by_email(self, email: str) -> User | None:
        uid = self.emails.get(email.lower())
        return self.users.get(uid) if uid else None

    def issue_token(self, token: str, user_id: str) -> None:
        self.tokens[token] = user_id

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

    # -------------------------------------------------------------- export / import
    def export_state(self) -> dict:
        return {
            "users": [{"id": u.id, "email": u.email, "display_name": u.display_name,
                       "password_hash": u.password_hash} for u in self.users.values()],
            "tokens": [{"token": t, "user_id": uid} for t, uid in self.tokens.items()],
            "dossiers": [_export_dossier(d) for d in self.dossiers.values()],
            "idempotent": [{"user_id": k[0], "method": k[1], "path": k[2], "key": k[3],
                            "request": v["request"], "response": v["response"]}
                           for k, v in self.idempotent.items()],
        }


def _export_dossier(d: Dossier) -> dict:
    building = d.state == "building"
    return {
        "id": d.id,
        "domain": d.domain,
        "state": d.settled_state if building else d.state,
        "fields": {f: field_view(d.fields[f]) for f in FIELDS},
        "researched_at": d.researched_at,
        "spent_units": d.settled_spent if building else d.spent_units,
    }
