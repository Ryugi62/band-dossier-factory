"""Verifier oracle for stage-4 rules, written from spec/stage-4.md (and decisions D36, D37, D39) only.

- normalise_domain / url_host / same_url: lineage normalisation.
- page_lineage(page, domain, lookup): registrant, kind (own rewrite), lookalike, origin (rules 1-4,
  at most three Canonical hops; fourth hop, unreachable original or cycle -> host of that URL).
- investor_names(excerpt, domain): Appendix A with the investors phrases and name rules.
- derive_investors(candidates): members, value, status, selected, citations, true_from.
- investors_change_type(old_names, old_tf, new_names, new_member_tf).
"""
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.environ.get("S1_PROBES", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stage-1")))
import appendix_a as A  # noqa: E402

KINDS = ("own", "filing", "news", "aggregator")
INV_PHRASES = ["investor", "investors", "led by", "backed by", "participated"]
INV_LAST = ("Ventures", "Capital", "Partners", "Fund", "Investments", "Holdings", "Equity")
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalise_domain(raw):
    if not isinstance(raw, str):
        return None
    d = raw.strip().lower()
    if d.endswith("."):
        d = d[:-1]
    if d.startswith("www."):
        d = d[4:]
    if len(d) > 253:
        return None
    labels = d.split(".")
    if len(labels) < 2 or not all(_LABEL.match(x) for x in labels):
        return None
    return d


def valid_url(u):
    if not isinstance(u, str):
        return False
    p = urllib.parse.urlparse(u.strip())
    return p.scheme.lower() in ("http", "https") and bool(p.hostname)


def url_host(u):
    h = urllib.parse.urlparse(u.strip()).hostname or ""
    return normalise_domain(h) or h.lower()


def url_key(u):
    """Comparable form: trimmed, scheme and host lower-cased, fragment dropped."""
    p = urllib.parse.urlparse(u.strip())
    netloc = p.netloc.lower()
    return urllib.parse.urlunparse((p.scheme.lower(), netloc, p.path, p.params, p.query, ""))


def registrant_of(page):
    r = normalise_domain((page.get("lineage") or {}).get("registrant"))
    return r or url_host(page["url"])


def stated_kind(page):
    return page.get("kind")


def page_kind(page, domain):
    """Stage-2 kind with defaults, then stage-4: `own` only when the registrant is the company's domain."""
    k = page.get("kind")
    if k not in KINDS:
        k = "own" if url_host(page["url"]) == domain else "aggregator"
    if k == "own" and registrant_of(page) != domain:
        k = "aggregator"
    return k


def is_lookalike(page):
    return page.get("kind") == "own" and registrant_of(page) != url_host(page["url"])


def origin(page, domain, lookup, depth=0, seen=None):
    """lookup(url) -> corpus page served in this epoch, or None."""
    seen = (seen or set()) | {url_key(page["url"])}
    lin = page.get("lineage") or {}
    fpb = normalise_domain(lin.get("first_published_by"))
    if fpb:
        return fpb
    can = lin.get("canonical")
    if valid_url(can) and url_key(can) != url_key(page["url"]):
        if depth >= 3 or url_key(can) in seen:
            return url_host(can)
        orig = lookup(can)
        if orig is None:
            return url_host(can)
        return origin(orig, domain, lookup, depth + 1, seen)
    if is_lookalike(page):
        return domain
    return registrant_of(page)


def needed_originals(page, lookup, depth=0, seen=None):
    """URLs a build must obtain to decide the page's origin (rule 2), in order."""
    seen = (seen or set()) | {url_key(page["url"])}
    lin = page.get("lineage") or {}
    if normalise_domain(lin.get("first_published_by")):
        return []
    can = lin.get("canonical")
    if valid_url(can) and url_key(can) != url_key(page["url"]) and depth < 3 and url_key(can) not in seen:
        orig = lookup(can)
        return [can] + (needed_originals(orig, lookup, depth + 1, seen) if orig else [])
    return []


# ---------------------------------------------------------------- investors (Appendix A variant)

def investor_names(excerpt, domain):
    s = A.collapse_ws(excerpt).strip()
    if not s or not A.is_single_sentence(s) or not A.names_company(s, domain):
        return set()
    if not any(A.has_phrase(s, p) for p in INV_PHRASES):
        return set()
    if any(A.has_phrase(s, p) for p in A.NEGATIONS):
        return set()
    spans = A.find_phrase(s, A.company_name(domain))
    for ph in INV_PHRASES:
        spans += A.find_phrase(s, ph)
    chars = list(s)
    for a, b in spans:
        for k in range(a, b):
            chars[k] = "\x00"
    t = "".join(chars)
    has_amount = any(v is not None for _, _, v in A.find_amounts(s)) or bool(A.find_amounts(s))
    after = set()
    if has_amount:
        for ph in ("led by", "backed by"):
            for a, b in A.find_phrase(s, ph):
                if b < len(s) and s[b] == " ":
                    after.add(b + 1)
    names, i = set(), 0
    while i < len(t):
        e = A.capitalised_end_at(t, i)
        if e is None:
            i += 1
            continue
        words = [(i, e)]
        while e < len(t) and t[e] == " ":
            e2 = A.capitalised_end_at(t, e + 1)
            if e2 is None:
                break
            words.append((e + 1, e2))
            e = e2
        text = s[words[0][0]:words[-1][1]]
        last = s[words[-1][0]:words[-1][1]]
        if (len(words) >= 2 and last in INV_LAST) or words[0][0] in after:
            names.add(text)
        i = e
    return names


def page_investors(prose, domain):
    """{name: first supporting sentence} over whole sentences of the prose."""
    out = {}
    for sent in A.split_sentences(prose):
        if len(sent) > 500:
            continue
        for n in investor_names(sent, domain):
            out.setdefault(n, A.collapse_ws(sent))
    return out


def norm(v):
    return v.strip() if isinstance(v, str) else v


def members_of(cands):
    names = {}
    for c in cands:
        names.setdefault(norm(c["value"]), []).append(c)
    out = []
    for n, cs in names.items():
        if any(c.get("kind") in ("own", "filing") for c in cs) or len({c.get("origin") for c in cs}) >= 2:
            out.append(n)
    return sorted(out)


def derive_investors(cands, rank_key):
    """Expected (value, status, citations, true_from, selected flags by index) from the candidates (any order)."""
    ranked = sorted(cands, key=rank_key)
    members = members_of(cands)
    if not members:
        return None, "unknown", [], None, ranked, members
    cits, tfs = [], []
    for m in members:
        mine = [c for c in ranked if norm(c["value"]) == m]
        cits += [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]} for c in mine]
        nn = [c.get("true_from") for c in mine if c.get("true_from") is not None]
        tfs.append(min(nn) if nn else None)
    tf = None if any(x is None for x in tfs) else max(tfs)
    return members, "known", cits, tf, ranked, members


def member_true_from(cands, name):
    nn = [c.get("true_from") for c in cands if norm(c["value"]) == name and c.get("true_from") is not None]
    return min(nn) if nn else None


def investors_change_type(old_names, old_tf, new_names, new_cands):
    old, new = set(old_names or []), set(new_names or [])
    sym = (old - new) | (new - old)
    for n in sym:
        if n not in new:
            return "change"
        ntf = member_true_from(new_cands, n)
        if ntf is None or old_tf is None or not ntf <= old_tf:
            return "change"
    return "correction"
