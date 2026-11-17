"""Appendix A: when an excerpt supports a value for a field of a company.

Pure functions only. `supported_value(excerpt, field, domain)` returns the one value the
excerpt supports for the field (or None); `split_sentences(prose)` splits prose by A.1.
"""
from __future__ import annotations

import re

FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")

STATEMENT_PHRASES = {
    "legal_name": ("legal name", "registered name", "registered as", "registered company", "legal entity",
                   "name of record"),
    "hq_city": ("headquartered in", "headquarters in", "head office in", "based in", "registered office in",
                "registered seat in"),
    "ceo": ("chief executive officer", "chief executive", "CEO"),
    "founded_year": ("founded", "founding", "established", "incorporated"),
    "headcount_range": ("employs", "employees", "staff", "people", "headcount", "workforce"),
    "funding_total": ("raised", "funding", "invested", "investment"),
}

NEGATING_PHRASES = ("in talks to", "plans to", "planning to", "wants to", "expects to", "hopes to", "aims to",
                    "seeking", "could", "would", "might", "reportedly", "rumoured", "former", "formerly",
                    "will become", "not")

LEGAL_SUFFIXES = ("Inc.", "Corp.", "LLC", "LLP", "L.P.", "Ltd", "Limited", "Pty Ltd", "plc", "PLC", "GmbH", "AG",
                  "KG", "SE", "AS", "A/S", "ASA", "AB", "Oy", "Oyj", "B.V.", "N.V.", "S.A.", "S.A.S.", "S.L.",
                  "S.r.l.", "S.p.A.", "s.r.o.", "a.s.", "K.K.")
_DOT_SUFFIXES = tuple(s for s in LEGAL_SUFFIXES if s.endswith("."))

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

HEADCOUNT_RANGES = ((1, 10, "1-10"), (11, 50, "11-50"), (51, 200, "51-200"), (201, 500, "201-500"),
                    (501, 1000, "501-1000"), (1001, 5000, "1001-5000"), (5001, 10000, "5001-10000"))
HEADCOUNT_VALUES = tuple(r[2] for r in HEADCOUNT_RANGES) + ("10001+",)

_SENTENCE_END = ".!?"
_CLOSERS = "\"”’)"
_WS_RUN = re.compile(r"\s+")
_NUMBER_TOKEN = re.compile(r"\d+(?:[.,]\d+)*")
_VALID_NUMBER = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_SCALES = {"k": 1_000, "m": 1_000_000, "mn": 1_000_000, "bn": 1_000_000_000,
           "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}


# ---------------------------------------------------------------- characters and phrases

def _alnum(ch: str) -> bool:
    return ch.isalnum()


def _clear_before(s: str, i: int) -> bool:
    return i <= 0 or not _alnum(s[i - 1])


def _clear_after(s: str, j: int) -> bool:
    return j >= len(s) or not _alnum(s[j])


def collapse_ws(s: str) -> str:
    """Every run of whitespace written as one space, surrounding whitespace removed."""
    return _WS_RUN.sub(" ", s).strip()


def find_phrase(s: str, phrase: str) -> list[tuple[int, int]]:
    """Spans of `phrase` in `s`, case-insensitive and as a whole word."""
    out = []
    for m in re.finditer("(?=(" + re.escape(phrase) + "))", s, re.IGNORECASE):
        i, j = m.start(1), m.end(1)
        if _clear_before(s, i) and _clear_after(s, j):
            out.append((i, j))
    return out


def company_name(domain: str) -> str:
    return domain.split(".")[0].replace("-", " ")


def names_company(s: str, domain: str) -> bool:
    return bool(find_phrase(s, domain) or find_phrase(s, company_name(domain)))


# ---------------------------------------------------------------- A.1 sentences

def _ends_legal_suffix(line: str, i: int) -> bool:
    """True when the `.` at `i` ends a legal-form suffix written as a whole word."""
    for suffix in _DOT_SUFFIXES:
        start = i + 1 - len(suffix)
        if start >= 0 and line[start:i + 1] == suffix and _clear_before(line, start):
            return True
    return False


def split_line(line: str) -> list[str]:
    sentences, start, i, n = [], 0, 0, len(line)
    while i < n:
        ch = line[i]
        if ch in _SENTENCE_END:
            j = i + 1
            while j < n and line[j] in _CLOSERS:
                j += 1
            if j < n and line[j].isspace() and not (ch == "." and _ends_legal_suffix(line, i)):
                sentences.append(line[start:j])
                start = j
                i = j
                continue
            i = j if j > i + 1 else i + 1
            continue
        i += 1
    sentences.append(line[start:])
    return [s.strip() for s in sentences if s.strip()]


def split_lines(prose: str) -> list[str]:
    return prose.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def split_sentences(prose: str) -> list[str]:
    out = []
    for line in split_lines(prose):
        out.extend(split_line(line))
    return out


def is_single_sentence(excerpt: str) -> bool:
    return len(split_line(collapse_ws(excerpt))) == 1


# ---------------------------------------------------------------- A.4 words and numbers

def _alnum_runs(s: str):
    i, n = 0, len(s)
    while i < n:
        if _alnum(s[i]):
            j = i
            while j < n and _alnum(s[j]):
                j += 1
            yield i, j
            i = j
        else:
            i += 1


def _is_capitalised(word: str) -> bool:
    return len(word) >= 2 and word.isalpha() and word[0].isupper() and all(c.islower() for c in word[1:])


def _is_uppercase(word: str) -> bool:
    return len(word) >= 2 and word.isalpha() and all(c.isupper() for c in word)


def _word_at(s: str, i: int) -> int | None:
    """End of the alnum run starting exactly at `i`, when `i` starts one."""
    if i >= len(s) or not _alnum(s[i]) or not _clear_before(s, i):
        return None
    j = i
    while j < len(s) and _alnum(s[j]):
        j += 1
    return j


def _number_tokens(s: str):
    """(start, end, value) of every well-formed digit token; letters next to it are checked by callers."""
    for m in _NUMBER_TOKEN.finditer(s):
        if _VALID_NUMBER.fullmatch(m.group()):
            yield m.start(), m.end(), float(m.group().replace(",", ""))


def _letter(s: str, i: int) -> bool:
    return 0 <= i < len(s) and s[i].isalpha()


def _starts_ci(s: str, pos: int, word: str) -> bool:
    return s[pos:pos + len(word)].lower() == word.lower()


def find_amounts(s: str) -> list[tuple[int, int, float]]:
    """(start, end, dollars) of every amount (A.4); dollars may be fractional."""
    out = []
    for start, end, num in _number_tokens(s):
        if _letter(s, start - 1):
            continue
        out.extend(_currency_prefixed(s, start, end, num))
        out.extend(_dollars_suffixed(s, start, end, num))
    return out


def _prefix_starts(s: str, start: int) -> list[int]:
    """Starts of a `$`, `US$` or `USD` prefix (and its optional space) ending at the number at `start`."""
    starts = []
    for gap in (0, 1):
        p = start
        if gap:
            if p - 1 < 0 or s[p - 1] != " ":
                continue
            p -= 1
        if p - 1 >= 0 and s[p - 1] == "$":
            if p - 3 >= 0 and s[p - 3:p - 1].upper() == "US":
                starts.append(p - 3)
            starts.append(p - 1)
        if p - 3 >= 0 and s[p - 3:p].upper() == "USD":
            starts.append(p - 3)
    return starts


def _currency_prefixed(s: str, start: int, end: int, num: float):
    starts = [p for p in _prefix_starts(s, start) if _clear_before(s, p)]
    if not starts:
        return []
    best = None
    for scale in ("bn", "mn", "k", "m"):
        if _starts_ci(s, end, scale) and _clear_after(s, end + len(scale)):
            best = (end + len(scale), _SCALES[scale])
            break
    if best is None:
        for scale in ("thousand", "million", "billion"):
            j = end + 1 + len(scale)
            if s[end:end + 1] == " " and _starts_ci(s, end + 1, scale) and _clear_after(s, j):
                best = (j, _SCALES[scale])
                break
    if best is None and _clear_after(s, end):
        best = (end, 1)
    if best is None:
        return []
    return [(min(starts), best[0], num * best[1])]


def _dollars_suffixed(s: str, start: int, end: int, num: float):
    if not _clear_before(s, start):
        return []
    options = [(end, 1)]
    for scale in ("thousand", "million", "billion"):
        if s[end:end + 1] == " " and _starts_ci(s, end + 1, scale):
            options.append((end + 1 + len(scale), _SCALES[scale]))
    out = []
    for pos, mult in options:
        for unit in ("dollars", "US dollars"):
            j = pos + 1 + len(unit)
            if s[pos:pos + 1] == " " and _starts_ci(s, pos + 1, unit) and _clear_after(s, j):
                out.append((start, j, num * mult))
    return out[:1] if out else []


def find_numbers(s: str) -> list[tuple[int, int, float]]:
    """Numbers (A.4) not next to a letter and not part of an amount."""
    amounts = find_amounts(s)
    out = []
    for start, end, num in _number_tokens(s):
        if _letter(s, start - 1) or _letter(s, end):
            continue
        if any(a <= start and end <= b for a, b, _ in amounts):
            continue
        out.append((start, end, num))
    return out


def headcount_range(n: int) -> str:
    for lo, hi, label in HEADCOUNT_RANGES:
        if lo <= n <= hi:
            return label
    return "10001+"


# ---------------------------------------------------------------- A.4 values per field

def values_legal_name(s: str, domain: str) -> list[str]:
    out = []
    for begin, pos in find_phrase(s, company_name(domain)) + find_phrase(s, domain):
        end = _shortest_legal_end(s, pos)
        if end is not None:
            out.append(s[begin:end])
    return out


def _suffix_end(s: str, pos: int) -> int | None:
    """End of the shortest `[,] SUFFIX` starting at `pos` with no letter or digit after it."""
    best = None
    for comma in ("", ","):
        p = pos + len(comma)
        if comma and s[pos:p] != comma:
            continue
        if s[p:p + 1] != " ":
            continue
        for suffix in LEGAL_SUFFIXES:
            j = p + 1 + len(suffix)
            if s[p + 1:j] == suffix and _clear_after(s, j):
                if best is None or j < best:
                    best = j
    return best


def _shortest_legal_end(s: str, pos: int) -> int | None:
    while True:
        end = _suffix_end(s, pos)
        if end is not None:
            return end
        if s[pos:pos + 1] != " ":
            return None
        j = _word_at(s, pos + 1)
        if j is None:
            return None
        word = s[pos + 1:j]
        if not (_is_capitalised(word) or _is_uppercase(word)):
            return None
        pos = j


def values_hq_city(s: str, domain: str) -> list[str]:
    out = []
    for phrase in STATEMENT_PHRASES["hq_city"]:
        for _, end in find_phrase(s, phrase):
            if s[end:end + 1] != " ":
                continue
            span = _place_run(s, end + 1)
            if span is not None:
                out.append(s[span[0]:span[1]])
    return out


def _capitalised_at(s: str, i: int) -> int | None:
    j = _word_at(s, i)
    return j if j is not None and _is_capitalised(s[i:j]) else None


def _place_run(s: str, start: int):
    end = _capitalised_at(s, start)
    if end is None:
        return None
    # not part of a longer run: no capitalised word joined to it from the left
    if start >= 2 and s[start - 1] in " -":
        k = start - 1
        b = k
        while b > 0 and _alnum(s[b - 1]):
            b -= 1
        if b < k and _is_capitalised(s[b:k]) and _clear_before(s, b):
            return None
    while end < len(s) and s[end] in " -":
        nxt = _capitalised_at(s, end + 1)
        if nxt is None:
            break
        end = nxt
    return start, end


def values_ceo(s: str, domain: str) -> list[str]:
    return person_names(s, domain, STATEMENT_PHRASES["ceo"])


def person_names(s: str, domain: str, phrases) -> list[str]:
    """Runs of two or three capitalised words, the company's name and `phrases` taken out first."""
    masked = list(s)
    for phrase in (company_name(domain),) + tuple(phrases):
        for a, b in find_phrase(s, phrase):
            for k in range(a, b):
                masked[k] = "\x00"
    m = "".join(masked)
    out, i, n = [], 0, len(m)
    while i < n:
        end = _capitalised_at(m, i)
        if end is None:
            i += 1
            continue
        words, j = 1, end
        while j < n and m[j] == " ":
            nxt = _capitalised_at(m, j + 1)
            if nxt is None:
                break
            words, j = words + 1, nxt
        if 2 <= words <= 3:
            out.append(s[i:j])
        i = j
    return out


def values_founded_year(s: str, domain: str) -> list[int]:
    return [int(num) for a, b, num in find_numbers(s) if b - a == 4 and s[a:b].isdigit() and 1800 <= num <= 2099]


def values_headcount(s: str, domain: str) -> list[str]:
    return [headcount_range(int(num)) for a, b, num in find_numbers(s)
            if "." not in s[a:b] and num >= 1]


def values_funding(s: str, domain: str) -> list[int]:
    out = []
    for _, _, dollars in find_amounts(s):
        whole = round(dollars)
        if abs(dollars - whole) < 1e-6:
            out.append(int(whole))
    return out


_VALUES = {"legal_name": values_legal_name, "hq_city": values_hq_city, "ceo": values_ceo,
           "founded_year": values_founded_year, "headcount_range": values_headcount,
           "funding_total": values_funding}


# ---------------------------------------------------------------- A.2 the rule

def supported_value(excerpt: str, field: str, domain: str):
    """The value `excerpt` supports for `field` of the company at `domain`, or None."""
    s = collapse_ws(excerpt)
    if not s or len(split_line(s)) != 1:
        return None
    if not names_company(s, domain):
        return None
    if not any(find_phrase(s, p) for p in STATEMENT_PHRASES[field]):
        return None
    if any(find_phrase(s, p) for p in NEGATING_PHRASES):
        return None
    values = _VALUES[field](s, domain)
    if not values or any(v != values[0] for v in values):
        return None
    return values[0]


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


def supports(excerpt: str, field: str, value, domain: str) -> bool:
    return value is not None and supported_value(excerpt, field, domain) == value


def normalise_claim(field: str, value):
    """A research answer's claimed value in the API's form, or None when it has none."""
    if value is None or isinstance(value, bool):
        return None
    if field in ("founded_year", "funding_total"):
        if isinstance(value, (int, float)) and float(value) == int(value):
            return int(value)
        if isinstance(value, str) and re.fullmatch(r"\d[\d,]*", value.strip()):
            return int(value.strip().replace(",", ""))
        return None
    if field == "headcount_range":
        if isinstance(value, (int, float)) and float(value) == int(value) and value >= 1:
            return headcount_range(int(value))
        if isinstance(value, str):
            v = value.strip()
            if v in HEADCOUNT_VALUES:
                return v
            if re.fullmatch(r"\d[\d,]*", v) and int(v.replace(",", "")) >= 1:
                return headcount_range(int(v.replace(",", "")))
        return None
    return value.strip() or None if isinstance(value, str) else None
