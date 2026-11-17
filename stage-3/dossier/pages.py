"""Pages (§4): header lines, prose, and the sentences of prose that support field values."""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlparse

from . import domains, support

MAX_EXCERPT = 500
KINDS = ("own", "filing", "news", "aggregator")
_RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})")


def _is_header_name(name: str) -> bool:
    parts = name.split("-")
    return all(len(p) >= 2 and p.isalpha() and p[0].isupper() and all(c.islower() for c in p[1:]) for p in parts)


def is_header_line(line: str) -> bool:
    """`Name: value`, the name a capitalised word or several joined by `-`."""
    name, sep, rest = line.partition(":")
    if not sep or not name or not _is_header_name(name):
        return False
    return rest == "" or rest[0] == " "


def split_prose(text: str) -> tuple[str, str]:
    """(header, prose). A text whose first line is not a header line is all prose."""
    lines = support.split_lines(text)
    if not lines or not is_header_line(lines[0]):
        return "", text
    for i, line in enumerate(lines):
        if line.strip() == "":
            return "\n".join(lines[:i]), "\n".join(lines[i + 1:])
    return text, ""


def header_values(header: str) -> dict:
    """Header lines as {name: value}; the first line of a name counts."""
    out = {}
    for line in support.split_lines(header):
        if is_header_line(line):
            name, _, value = line.partition(":")
            out.setdefault(name, value.strip())
    return out


def page_kind(header: dict, url: str, domain: str) -> str:
    """The `Kind` line when it names a kind, else `own` on the company's host and `aggregator` elsewhere."""
    kind = header.get("Kind")
    if kind in KINDS:
        return kind
    host = urlparse(url).hostname or ""
    return "own" if domains.normalise(host) == domain else "aggregator"


def page_published(header: dict) -> str | None:
    """The `Published` instant as RFC 3339 with an offset, or None when absent or not RFC 3339."""
    value = header.get("Published")
    if not value or not _RFC3339.fullmatch(value):
        return None
    text = value[:-1] + "+00:00" if value[-1] in "Zz" else value
    try:
        return dt.datetime.fromisoformat(text.replace("t", "T")).isoformat()
    except ValueError:
        return None


def complete_sentences(prose: str, truncated: bool) -> list[str]:
    """Sentences of `prose`; a text cut short loses its last, possibly partial, sentence."""
    if not truncated:
        return support.split_sentences(prose)
    lines = support.split_lines(prose)
    out = []
    for line in lines[:-1]:
        out.extend(support.split_line(line))
    out.extend(support.split_line(lines[-1])[:-1])
    return out


def supporting_sentences(sentences: list[str], domain: str):
    """Yield (field, value, excerpt) for every sentence that supports a value."""
    for sentence in sentences:
        excerpt = support.collapse_ws(sentence)
        if not excerpt or len(excerpt) > MAX_EXCERPT or not support.names_company(excerpt, domain):
            continue
        for field in support.FIELDS:
            value = support.supported_value(excerpt, field, domain)
            if value is not None:
                yield field, value, excerpt


def contains_excerpt(prose: str, excerpt: str) -> bool:
    """True when `excerpt` is copied from `prose`, any whitespace run read as one space."""
    return support.collapse_ws(excerpt) in support.collapse_ws(prose)
