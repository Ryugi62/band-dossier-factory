"""Independent implementation of stage-1 Appendix A ("When an excerpt supports a value").

Written by the verifier from the specification text only. Used by the probes as an oracle:
  supported_value(excerpt, field, domain) -> normalised value or None
  page_supports(prose, domain) -> {field: {value, ...}} over whole sentences of the prose
  split_prose(served_text) -> (header_lines, prose)
Pure standard library; no service or network access.
"""
import re
from decimal import Decimal, InvalidOperation

FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")

STATEMENT = {
    "legal_name": ["legal name", "registered name", "registered as", "registered company",
                   "legal entity", "name of record"],
    "hq_city": ["headquartered in", "headquarters in", "head office in", "based in",
                "registered office in", "registered seat in"],
    "ceo": ["chief executive officer", "chief executive", "CEO"],
    "founded_year": ["founded", "founding", "established", "incorporated"],
    "headcount_range": ["employs", "employees", "staff", "people", "headcount", "workforce"],
    "funding_total": ["raised", "funding", "invested", "investment"],
}
NEGATIONS = ["in talks to", "plans to", "planning to", "wants to", "expects to", "hopes to",
             "aims to", "seeking", "could", "would", "might", "reportedly", "rumoured",
             "former", "formerly", "will become", "not"]
LEGAL_SUFFIXES = ["Inc.", "Corp.", "LLC", "LLP", "L.P.", "Ltd", "Limited", "Pty Ltd", "plc", "PLC",
                  "GmbH", "AG", "KG", "SE", "AS", "A/S", "ASA", "AB", "Oy", "Oyj", "B.V.", "N.V.",
                  "S.A.", "S.A.S.", "S.L.", "S.r.l.", "S.p.A.", "s.r.o.", "a.s.", "K.K."]
DOT_SUFFIXES = [s for s in LEGAL_SUFFIXES if s.endswith(".")]
HEADCOUNT_RANGES = [(1, 10, "1-10"), (11, 50, "11-50"), (51, 200, "51-200"), (201, 500, "201-500"),
                    (501, 1000, "501-1000"), (1001, 5000, "1001-5000"), (5001, 10000, "5001-10000")]
HEADCOUNT_VALUES = [r[2] for r in HEADCOUNT_RANGES] + ["10001+"]
SCALES = {"k": 1000, "thousand": 1000, "m": 10**6, "mn": 10**6, "million": 10**6,
          "bn": 10**9, "billion": 10**9}


def _alnum(ch):
    return ch.isalpha() or ch.isdigit()


def _before_ok(s, i):
    return i == 0 or not _alnum(s[i - 1])


def _after_ok(s, j):
    return j >= len(s) or not _alnum(s[j])


def find_phrase(s, phrase):
    """All (start, end) whole-word, case-insensitive matches of phrase in s."""
    out = []
    pat = re.compile(re.escape(phrase).replace(r"\ ", " "), re.IGNORECASE)
    for m in pat.finditer(s):
        if _before_ok(s, m.start()) and _after_ok(s, m.end()):
            out.append((m.start(), m.end()))
    # overlapping matches are not possible for the phrases used here except via finditer skipping;
    # rescan from every start to be safe
    i = 0
    seen = set(out)
    low = s.lower()
    p = phrase.lower()
    while True:
        k = low.find(p, i)
        if k < 0:
            break
        if _before_ok(s, k) and _after_ok(s, k + len(p)) and (k, k + len(p)) not in seen:
            out.append((k, k + len(p)))
            seen.add((k, k + len(p)))
        i = k + 1
    return sorted(out)


def has_phrase(s, phrase):
    return bool(find_phrase(s, phrase))


# ---------------------------------------------------------------- A.1 sentences

def split_sentences_line(line):
    out = []
    start = 0
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in ".!?":
            j = i + 1
            while j < n and line[j] in "\"”’)":
                j += 1
            if j >= n or line[j].isspace():
                ends = True
                if ch == ".":
                    upto = line[:i + 1]
                    for suf in DOT_SUFFIXES:
                        if upto.endswith(suf) and _before_ok(line, i + 1 - len(suf)):
                            ends = False
                            break
                if ends:
                    out.append(line[start:j])
                    start = j
                    i = j
                    continue
        i += 1
    out.append(line[start:])
    return [t.strip() for t in out if t.strip()]


def split_sentences(prose):
    res = []
    for line in re.split(r"\r\n|\r|\n", prose):
        res.extend(split_sentences_line(line))
    return res


def collapse_ws(s):
    return re.sub(r"\s+", " ", s)


def is_single_sentence(excerpt):
    return len(split_sentences(collapse_ws(excerpt))) == 1


# ---------------------------------------------------------------- pages

HEADER_LINE = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)*: ?")


def split_prose(text):
    """Return (header_lines, prose) per stage-1 §4 Pages."""
    lines = text.split("\n")
    if not lines or not HEADER_LINE.match(lines[0]):
        return [], text
    header = []
    for idx, line in enumerate(lines):
        if line.strip() == "":
            return header, "\n".join(lines[idx + 1:])
        header.append(line)
    return header, ""


# ---------------------------------------------------------------- A.2 naming

def company_name(domain):
    return domain.split(".")[0].replace("-", " ")


def names_company(s, domain):
    return has_phrase(s, domain) or has_phrase(s, company_name(domain))


# ---------------------------------------------------------------- A.4 words, numbers, amounts

def word_end_at(s, i):
    """If a capitalised or uppercase word starts at i, return its end index, else None."""
    if i >= len(s) or not s[i].isalpha() or not s[i].isupper() or not _before_ok(s, i):
        return None
    j = i + 1
    if j < len(s) and s[j].isalpha() and s[j].islower():
        while j < len(s) and s[j].isalpha() and s[j].islower():
            j += 1
        return j if _after_ok(s, j) else None
    while j < len(s) and s[j].isalpha() and s[j].isupper():
        j += 1
    if j - i >= 2 and _after_ok(s, j):
        return j
    return None


def capitalised_end_at(s, i):
    if i >= len(s) or not s[i].isalpha() or not s[i].isupper() or not _before_ok(s, i):
        return None
    j = i + 1
    if not (j < len(s) and s[j].isalpha() and s[j].islower()):
        return None
    while j < len(s) and s[j].isalpha() and s[j].islower():
        j += 1
    return j if _after_ok(s, j) else None


NUM_RE = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_NUM = re.compile(NUM_RE)
_PREFIX = re.compile(r"US\$|USD|\$", re.IGNORECASE)
_SCALE_ATTACHED = ("mn", "bn", "k", "m")
_SCALE_WORDS = ("thousand", "million", "billion")


def _num_at(s, i):
    """End of a number token starting at i (not joined to other digits), else None."""
    if i > 0 and (s[i - 1].isdigit() or (s[i - 1] in ".," and i > 1 and s[i - 2].isdigit())):
        return None
    m = _NUM.match(s, i)
    if not m:
        return None
    e = m.end()
    if e < len(s) and (s[e].isdigit() or (s[e] in ".," and e + 1 < len(s) and s[e + 1].isdigit())):
        return None
    return e


def _istarts(s, pos, word):
    return s[pos:pos + len(word)].lower() == word.lower()


def find_amounts(s):
    """[(start, end, value_or_None)]; value None when not a whole number of dollars."""
    out = []
    for start in range(len(s)):
        if not _before_ok(s, start):
            continue
        # form 1: $ / US$ / USD, optional space, number, optional scale
        pm = _PREFIX.match(s, start)
        if pm:
            for ns in ((pm.end() + 1, pm.end()) if s[pm.end():pm.end() + 1] == " " else (pm.end(),)):
                if ns >= len(s) or not s[ns].isdigit():
                    continue
                ne = _num_at(s, ns)
                if ne is None:
                    continue
                num = s[ns:ne]
                done = False
                for sc in _SCALE_ATTACHED:
                    if _istarts(s, ne, sc) and _after_ok(s, ne + len(sc)):
                        out.append(_amount(start, ne + len(sc), num, sc)); done = True; break
                if not done:
                    for sc in _SCALE_WORDS:
                        if s[ne:ne + 1] == " " and _istarts(s, ne + 1, sc) and _after_ok(s, ne + 1 + len(sc)):
                            out.append(_amount(start, ne + 1 + len(sc), num, sc)); done = True; break
                if not done and _after_ok(s, ne):
                    out.append(_amount(start, ne, num, None))
                break
        # form 2: number, optional scale word, then dollars / US dollars
        if s[start].isdigit():
            ne = _num_at(s, start)
            if ne is not None:
                num = s[start:ne]
                opts = [(ne, None)]
                for sc in _SCALE_WORDS:
                    if s[ne:ne + 1] == " " and _istarts(s, ne + 1, sc):
                        opts.insert(0, (ne + 1 + len(sc), sc))
                for pos, sc in opts:
                    hit = False
                    for cur in ("dollars", "US dollars"):
                        if s[pos:pos + 1] == " " and _istarts(s, pos + 1, cur) and _after_ok(s, pos + 1 + len(cur)):
                            out.append(_amount(start, pos + 1 + len(cur), num, sc)); hit = True; break
                    if hit:
                        break
    return sorted(set(out))


def _amount(start, end, num, scale):
    try:
        v = Decimal(num.replace(",", "")) * SCALES.get((scale or "").lower(), 1)
    except InvalidOperation:
        return (start, end, None)
    return (start, end, int(v) if v == v.to_integral_value() else None)


def find_numbers(s, masked_spans=()):
    """[(start, end, text)] numbers per A.4 outside the masked spans."""
    res = []
    for m in re.finditer(r"[\d.,]+", s):
        tok = m.group(0)
        a, b = m.start(), m.end()
        while a < b and not s[a].isdigit():
            a += 1
        while b > a and not s[b - 1].isdigit():
            b -= 1
        if a >= b:
            continue
        core = s[a:b]
        if not re.fullmatch(NUM_RE, core):
            continue
        if a > 0 and s[a - 1].isalpha():
            continue
        if b < len(s) and s[b].isalpha():
            continue
        if any(x <= a and b <= y for x, y in masked_spans):
            continue
        res.append((a, b, core))
    return res


def headcount_range(n):
    for lo, hi, label in HEADCOUNT_RANGES:
        if lo <= n <= hi:
            return label
    return "10001+" if n >= 10001 else None


# ---------------------------------------------------------------- per-field value extraction

def values_legal_name(s, domain):
    vals = set()
    occ = find_phrase(s, domain) + find_phrase(s, company_name(domain))
    for a, b in occ:
        pos = b
        while True:
            # try suffix here (shortest first: fewer words, then shortest suffix text)
            hit = None
            for suf in sorted(LEGAL_SUFFIXES, key=len):
                for lead in (", ", " "):
                    if s.startswith(lead + suf, pos) and _after_ok(s, pos + len(lead) + len(suf)):
                        end = pos + len(lead) + len(suf)
                        if hit is None or end < hit:
                            hit = end
            if hit is not None:
                vals.add(s[a:hit])
                break
            if pos < len(s) and s[pos] == " ":
                e = word_end_at(s, pos + 1)
                if e is not None:
                    pos = e
                    continue
            break
    return vals


def values_hq_city(s, domain):
    vals = set()
    for ph in STATEMENT["hq_city"]:
        for a, b in find_phrase(s, ph):
            if b >= len(s) or s[b] != " ":
                continue
            st = b + 1
            e = capitalised_end_at(s, st)
            if e is None:
                continue
            # not part of a longer run: the word before must not be a capitalised word joined by ' ' or '-'
            k = a
            prev_ws = s[:b].rstrip()
            last = re.search(r"(\S+)$", prev_ws)
            if last:
                w = last.group(1)
                ws = b - len(w)
                if capitalised_end_at(s, ws) == b:
                    continue
            while e < len(s) and s[e] in " -":
                e2 = capitalised_end_at(s, e + 1)
                if e2 is None:
                    break
                e = e2
            vals.add(s[st:e])
    return vals


def values_ceo(s, domain):
    spans = find_phrase(s, company_name(domain))
    for ph in STATEMENT["ceo"]:
        spans += find_phrase(s, ph)
    chars = list(s)
    for a, b in spans:
        for k in range(a, b):
            chars[k] = "\x00"
    t = "".join(chars)
    vals = set()
    i = 0
    while i < len(t):
        e = capitalised_end_at(t, i)
        if e is None:
            i += 1
            continue
        words = [(i, e)]
        while e < len(t) and t[e] == " ":
            e2 = capitalised_end_at(t, e + 1)
            if e2 is None:
                break
            words.append((e + 1, e2))
            e = e2
        if 2 <= len(words) <= 3:
            vals.add(s[words[0][0]:words[-1][1]])
        i = e
    return vals


def values_founded_year(s, domain):
    spans = [(a, b) for a, b, _ in find_amounts(s)]
    vals = set()
    for a, b, tok in find_numbers(s, spans):
        if re.fullmatch(r"\d{4}", tok) and 1800 <= int(tok) <= 2099:
            vals.add(int(tok))
    return vals


def values_headcount(s, domain):
    spans = [(a, b) for a, b, _ in find_amounts(s)]
    vals = set()
    for a, b, tok in find_numbers(s, spans):
        if "." in tok:
            continue
        n = int(tok.replace(",", ""))
        if n >= 1:
            vals.add(headcount_range(n))
    return vals


def values_funding(s, domain):
    return {v for _, _, v in find_amounts(s) if v is not None}


EXTRACT = {"legal_name": values_legal_name, "hq_city": values_hq_city, "ceo": values_ceo,
           "founded_year": values_founded_year, "headcount_range": values_headcount,
           "funding_total": values_funding}


def supported_value(excerpt, field, domain):
    """The value the excerpt supports for field of the company at domain, or None."""
    s = collapse_ws(excerpt).strip()
    if not s or not is_single_sentence(s):
        return None
    if not names_company(s, domain):
        return None
    if not any(has_phrase(s, p) for p in STATEMENT[field]):
        return None
    if any(has_phrase(s, p) for p in NEGATIONS):
        return None
    vals = EXTRACT[field](s, domain)
    if len(vals) != 1:
        return None
    return next(iter(vals))


def supports(excerpt, field, value, domain):
    v = supported_value(excerpt, field, domain)
    return v is not None and v == value


def page_supports(prose, domain):
    """{field: {value: [sentence, ...]}} for every whole sentence of the prose."""
    out = {f: {} for f in FIELDS}
    for sent in split_sentences(prose):
        if len(sent) > 500:
            continue
        for f in FIELDS:
            v = supported_value(sent, f, domain)
            if v is not None:
                out[f].setdefault(v, []).append(sent)
    return out


def normalise_claim_value(field, value):
    """Normalise a research claim value for comparison with supported_value output."""
    if value is None:
        return None
    if field in ("founded_year", "funding_total"):
        try:
            if isinstance(value, bool):
                return None
            if isinstance(value, (int, float)) and float(value) == int(value):
                return int(value)
            if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
                return int(value.strip())
        except (ValueError, TypeError):
            return None
        return None
    if field == "headcount_range":
        if isinstance(value, int) and not isinstance(value, bool):
            return headcount_range(value)
        if isinstance(value, str):
            v = value.strip()
            if v in HEADCOUNT_VALUES:
                return v
            if re.fullmatch(r"[\d,]+", v):
                return headcount_range(int(v.replace(",", "")))
        return None
    return value.strip() if isinstance(value, str) else None
