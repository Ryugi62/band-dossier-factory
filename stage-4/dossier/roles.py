"""Appendix A variants for people and backers: the executives' titles (stage 3) and investors (stage 4).

Pure functions built on the Appendix A machinery of `support.py`.
"""
from __future__ import annotations

from .support import (NEGATING_PHRASES, _capitalised_at, collapse_ws, company_name, find_amounts, find_phrase,
                      names_company, person_names, split_line)

# Stage 3: the executives' titles, each an Appendix A field with the format and normalisation of `ceo`.
TITLES = ("cfo", "coo", "cto")
TITLE_PHRASES = {
    "cfo": ("chief financial officer", "CFO"),
    "coo": ("chief operating officer", "COO"),
    "cto": ("chief technology officer", "CTO"),
}

# Stage 4: investors.
INVESTOR_PHRASES = ("investor", "investors", "led by", "backed by", "participated")
INVESTOR_LAST_WORDS = ("Ventures", "Capital", "Partners", "Fund", "Investments", "Holdings", "Equity")


def supported_title(excerpt: str, title: str, domain: str):
    """The person `excerpt` supports for an executive `title` (stage 3), or None."""
    s = collapse_ws(excerpt)
    if not s or len(split_line(s)) != 1 or not names_company(s, domain):
        return None
    phrases = TITLE_PHRASES[title]
    if not any(find_phrase(s, p) for p in phrases) or any(find_phrase(s, p) for p in NEGATING_PHRASES):
        return None
    values = person_names(s, domain, phrases)
    if not values or any(v != values[0] for v in values):
        return None
    return values[0]


def investor_names(excerpt: str, domain: str) -> list[str]:
    """Every investor name `excerpt` supports (stage 4): rules 1-4 of A.2 and the investor-name rules."""
    s = collapse_ws(excerpt)
    if not s or len(split_line(s)) != 1 or not names_company(s, domain):
        return []
    if not any(find_phrase(s, p) for p in INVESTOR_PHRASES) or any(find_phrase(s, p) for p in NEGATING_PHRASES):
        return []
    masked = list(s)
    for phrase in (company_name(domain),) + INVESTOR_PHRASES:
        for a, b in find_phrase(s, phrase):
            for k in range(a, b):
                masked[k] = "\x00"
    m = "".join(masked)
    after = set()
    if find_amounts(s):
        for phrase in ("led by", "backed by"):
            after |= {b + 1 for _, b in find_phrase(s, phrase) if s[b:b + 1] == " "}
    names, i, n = [], 0, len(m)
    while i < n:
        end = _capitalised_at(m, i)
        if end is None:
            i += 1
            continue
        words, j = [(i, end)], end
        while j < n and m[j] == " ":
            nxt = _capitalised_at(m, j + 1)
            if nxt is None:
                break
            words.append((j + 1, nxt))
            j = nxt
        last = s[words[-1][0]:words[-1][1]]
        if (len(words) >= 2 and last in INVESTOR_LAST_WORDS) or i in after:
            name = s[i:j]
            if name not in names:
                names.append(name)
        i = j
    return names
