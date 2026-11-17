"""Pages (§4): header lines, prose, and the sentences of prose that support field values."""
from __future__ import annotations

from . import support

MAX_EXCERPT = 500


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
