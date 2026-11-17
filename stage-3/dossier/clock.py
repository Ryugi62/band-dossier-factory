"""The service clock (§3.4): system time until the first reset, then moved only by reset and clock calls."""
from __future__ import annotations

import datetime as dt
import re

_RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})")


def parse_rfc3339(value: str) -> dt.datetime | None:
    """An aware datetime for an RFC 3339 timestamp with an explicit offset, else None."""
    if not _RFC3339.fullmatch(value):
        return None
    text = value.replace("t", "T").replace(" ", "T")
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def format_ts(value: dt.datetime) -> str:
    return value.isoformat()


class Clock:
    def __init__(self) -> None:
        self._fixed: dt.datetime | None = None

    def now(self) -> dt.datetime:
        if self._fixed is None:
            return dt.datetime.now(dt.timezone.utc)
        return self._fixed

    def set(self, value: dt.datetime) -> None:
        self._fixed = value

    def is_earlier(self, value: dt.datetime) -> bool:
        return value < self.now()
