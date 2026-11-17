"""Batches (stage 4): several companies researched under one shared budget (decisions D40, D41).

A batch creates a dossier for each domain that has none and runs its first build; a domain that
already has a dossier is not researched and costs the batch nothing. Every call of a batch build
reserves its worst-case cost against both the build's 80 units and the batch's `budget_units`
(provider.Meter with the batch as its budget), so the batch never spends more than its budget.
"""
from __future__ import annotations

from . import domains, errors
from .service import Service, canonical
from .store import Batch, Dossier

MAX_DOMAINS = 50
MAX_BUDGET = 100000


def fingerprint(body: dict) -> str:
    """The request as a replay compares it: the known fields only (§7)."""
    return canonical({k: body[k] for k in ("domains", "budget_units") if k in body})


def validate(body: dict) -> tuple[list[str], int]:
    raw = body.get("domains")
    if raw is None:
        raise errors.invalid("domains is required")
    if not isinstance(raw, list):
        raise errors.malformed("domains must be a list")
    if not raw or len(raw) > MAX_DOMAINS:
        raise errors.invalid("domains must hold 1 to 50 entries")
    if not all(isinstance(d, str) for d in raw):
        raise errors.malformed("every entry of domains must be a string")
    normalised = [domains.normalise(d) for d in raw]
    if any(d is None for d in normalised):
        raise errors.invalid("an entry of domains is not a valid host name")
    if len(set(normalised)) != len(normalised):
        raise errors.invalid("two entries of domains name the same company")
    budget = body.get("budget_units")
    # any non-integer is 422, whatever its JSON type (stage-4 table takes precedence over §5's 400)
    if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= MAX_BUDGET:
        raise errors.invalid("budget_units must be an integer from 1 to 100000")
    return normalised, budget


def view(service: Service, batch: Batch) -> dict:
    store = service.store
    return {
        "batch_id": batch.id,
        "state": "running" if batch.running else "done",
        "budget_units": batch.budget,
        "spent_units": batch.spent,
        "dossiers": [{"domain": d, "state": store.dossiers[d].state if d in store.dossiers else "failed"}
                     for d in batch.domains],
    }


def create(service: Service, user_id: str, body: dict) -> tuple[int, dict]:
    """Start the batch: new dossiers get their first build under the batch's budget. Synchronous, so atomic."""
    names, budget = validate(body)
    store = service.store
    batch = Batch(id=store.new_batch_id(), owner=user_id, budget=budget, domains=names)
    store.batches[batch.id] = batch
    for domain in names:
        if domain in store.dossiers:
            continue
        dossier = Dossier(id=store.new_dossier_id(), domain=domain)
        store.dossiers[domain] = dossier
        service._start_build(dossier, batch)
    store.save_batch(batch)
    return 202, view(service, batch)


def read(service: Service, user_id: str, batch_id: str) -> dict:
    batch = service.store.batches.get(batch_id)
    if batch is None or batch.owner != user_id:
        raise errors.not_found("no such batch")
    return view(service, batch)
