"""Durable state on the container's filesystem (stage 3, Restarts; decision D27).

SQLite in WAL mode with synchronous=FULL: every write is one committed transaction, flushed to
disk before the request that made it answers. Rows hold JSON documents: one per user, token,
idempotent record, dossier (with its build log and history) and feed entry, plus the clock and
the next feed number.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager

_TABLES = ("users", "tokens", "idempotent", "dossiers", "feed", "batches")


class Persistence:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        for table in _TABLES:
            key = "INTEGER" if table == "feed" else "TEXT"
            self.db.execute(f"CREATE TABLE IF NOT EXISTS {table} (k {key} PRIMARY KEY, v TEXT NOT NULL)")

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        self.db.execute("COMMIT")

    @staticmethod
    def _put(db, table: str, key, value) -> None:
        db.execute(f"INSERT OR REPLACE INTO {table} (k, v) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))

    # -------------------------------------------------------------- writes
    def replace_all(self, state: dict, clock: str | None) -> None:
        with self._tx() as db:
            for table in _TABLES:
                db.execute(f"DELETE FROM {table}")
            for u in state["users"]:
                self._put(db, "users", u["id"], u)
            for t in state["tokens"]:
                self._put(db, "tokens", t["token"], t)
            for e in state["idempotent"]:
                self._put(db, "idempotent", json.dumps([e["user_id"], e["method"], e["path"], e["key"]]), e)
            for d in state["dossiers"]:
                self._put(db, "dossiers", d["domain"], d)
            for f in state["feed"]:
                self._put(db, "feed", f["seq"], f)
            for b in state.get("batches", []):
                self._put(db, "batches", b["id"], b)
            self._put(db, "meta", "next_seq", state["next_seq"])
            self._put(db, "meta", "clock", clock)
            self._put(db, "meta", "initialised", True)

    def put_user(self, user: dict) -> None:
        with self._tx() as db:
            self._put(db, "users", user["id"], user)

    def put_token(self, token: str, user_id: str) -> None:
        with self._tx() as db:
            self._put(db, "tokens", token, {"token": token, "user_id": user_id})

    def put_idempotent(self, slot: list, record: dict) -> None:
        with self._tx() as db:
            self._put(db, "idempotent", json.dumps(slot), {"user_id": slot[0], "method": slot[1], "path": slot[2],
                                                          "key": slot[3], **record})

    def put_dossier(self, dossier: dict, feed: list[dict], next_seq: int, batch: dict | None = None) -> None:
        with self._tx() as db:
            self._put(db, "dossiers", dossier["domain"], dossier)
            if batch is not None:
                self._put(db, "batches", batch["id"], batch)
            for f in feed:
                self._put(db, "feed", f["seq"], f)
            if feed:
                self._put(db, "meta", "next_seq", next_seq)

    def put_batch(self, batch: dict) -> None:
        with self._tx() as db:
            self._put(db, "batches", batch["id"], batch)

    def put_clock(self, value: str | None) -> None:
        with self._tx() as db:
            self._put(db, "meta", "clock", value)

    # -------------------------------------------------------------- read at start-up
    def load(self) -> tuple[dict, str | None] | None:
        """(state in the export shape, clock) or None when nothing was ever stored."""
        meta = {k: json.loads(v) for k, v in self.db.execute("SELECT k, v FROM meta")}
        if not meta.get("initialised"):
            return None
        rows = {t: [json.loads(v) for (v,) in self.db.execute(f"SELECT v FROM {t} ORDER BY k")] for t in _TABLES}
        state = {"schema": "dossier-stage-4", "users": rows["users"], "tokens": rows["tokens"],
                 "idempotent": rows["idempotent"], "dossiers": rows["dossiers"], "feed": rows["feed"],
                 "next_seq": meta.get("next_seq", 1), "batches": rows["batches"]}
        return state, meta.get("clock")
