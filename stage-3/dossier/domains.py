"""Domain normalisation and validation (§4 Domains)."""
from __future__ import annotations

import re

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def normalise(raw: str) -> str | None:
    """The normalised domain, or None when it is not a valid host name."""
    d = raw.strip().lower()
    if d.endswith("."):
        d = d[:-1]
    if d.startswith("www."):
        d = d[4:]
    if len(d) > 253:
        return None
    labels = d.split(".")
    if len(labels) < 2 or not all(_LABEL.fullmatch(label) for label in labels):
        return None
    return d
