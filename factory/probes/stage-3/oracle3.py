"""Verifier oracle for stage-3 rules, written from spec/stage-3.md only.

- supported_title(excerpt, title, domain): executives titles as Appendix A fields (format and
  normalisation of `ceo`, the title's statement phrases replacing those of `ceo`).
- page_true_from(effective, published): Two times per value.
- change_type(field, old, new, old_tf, new_tf): Changes and corrections (+ executives by title).
- values_at(builds, true_at, null_holds): page versions, replacement and end rules.
"""
import datetime as dt
import json
import re
import sys
import os

sys.path.insert(0, os.environ.get("S1_PROBES", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stage-1")))
import appendix_a as A  # noqa: E402

TITLES = ("cfo", "coo", "cto")
TITLE_PHRASES = {"cfo": ["chief financial officer", "CFO"], "coo": ["chief operating officer", "COO"],
                 "cto": ["chief technology officer", "CTO"]}
FIELDS7 = list(A.FIELDS) + ["executives"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PROVIDERS = ("nimble", "tavily", "kernel", "browserbase")


def _title_values(s, domain, title):
    spans = A.find_phrase(s, A.company_name(domain))
    for ph in TITLE_PHRASES[title]:
        spans += A.find_phrase(s, ph)
    chars = list(s)
    for a, b in spans:
        for k in range(a, b):
            chars[k] = "\x00"
    t = "".join(chars)
    vals, i = set(), 0
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
        if 2 <= len(words) <= 3:
            vals.add(s[words[0][0]:words[-1][1]])
        i = e
    return vals


def supported_title(excerpt, title, domain):
    s = A.collapse_ws(excerpt).strip()
    if not s or not A.is_single_sentence(s) or not A.names_company(s, domain):
        return None
    if not any(A.has_phrase(s, p) for p in TITLE_PHRASES[title]):
        return None
    if any(A.has_phrase(s, p) for p in A.NEGATIONS):
        return None
    vals = _title_values(s, domain, title)
    return next(iter(vals)) if len(vals) == 1 else None


def page_titles(prose, domain):
    """{title: {name: first_sentence}} over whole sentences of the prose."""
    out = {t: {} for t in TITLES}
    for sent in A.split_sentences(prose):
        if len(sent) > 500:
            continue
        for t in TITLES:
            v = supported_title(sent, t, domain)
            if v is not None and v not in out[t]:
                out[t][v] = A.collapse_ws(sent)
    return out


def valid_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00").replace("z", "+00:00").replace("t", "T"))


TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


def page_true_from(effective, published):
    """`Effective` when it is a valid YYYY-MM-DD date, else the UTC date of a valid `Published`, else None."""
    if valid_date(effective):
        return effective
    if isinstance(published, str) and TS_RE.match(published):
        try:
            return parse_ts(published).astimezone(dt.timezone.utc).date().isoformat()
        except ValueError:
            return None
    return None


def norm(v):
    return v.strip() if isinstance(v, str) else v


def same_value(a, b):
    return json.dumps(norm_members(a), sort_keys=True) == json.dumps(norm_members(b), sort_keys=True)


def norm_members(v):
    if isinstance(v, list):
        return [{"title": m.get("title"), "name": norm(m.get("name"))} for m in v]
    return norm(v)


def change_type(field, old, new, old_tf, new_tf, old_members_tf=None, new_members_tf=None):
    """'correction' or 'change' for a differing selected value (old/new may be None)."""
    if field != "executives":
        if old is not None and new is not None and old_tf is not None and new_tf is not None and new_tf <= old_tf:
            return "correction"
        return "change"
    om = {m["title"]: norm(m["name"]) for m in (old or [])}
    nm = {m["title"]: norm(m["name"]) for m in (new or [])}
    differing = [t for t in TITLES if (t in om) != (t in nm) or (t in om and om[t] != nm[t])]
    for t in differing:
        if not (t in om and t in nm):
            return "change"
        otf, ntf = (old_members_tf or {}).get(t), (new_members_tf or {}).get(t)
        if otf is None or ntf is None or not ntf <= otf:
            return "change"
    return "correction"


def versions_known(builds):
    """builds: [{'versions': {url: (true_from, [cand...])}}] in build order -> {url: [(from, until, cands)]}."""
    out = {}
    for b in builds:
        for url, (tf, cands) in b["versions"].items():
            vs = out.setdefault(url, [])
            if tf is None:
                vs.clear()
            else:
                vs[:] = [v for v in vs if not (v[0] is not None and v[0] >= tf)]
                # the latest earlier version it does not replace stops holding on tf
                if vs:
                    last = vs[-1]
                    if last[1] is None or last[1] > tf:
                        vs[-1] = (last[0], tf, last[2])
            vs.append((tf, None, cands))
    return out


def candidates_at(builds, true_at, null_holds):
    """Candidates of every version holding on true_at. null_holds: a null-dated version holds on every date
    (True) or on none (False) -- the spec's 'holds from no date' is read both ways by the probes."""
    res = []
    for url, vs in versions_known(builds).items():
        for frm, until, cands in vs:
            if frm is None:
                if not null_holds:
                    continue
                if until is not None and true_at >= until:
                    continue
            else:
                if true_at < frm or (until is not None and true_at >= until):
                    continue
            res.extend(cands)
    return res


AUTH = {"own": 0, "filing": 0, "news": 1, "aggregator": 2}


def rank_key(c):
    pub = c.get("published_at")
    rec = (1, 0.0) if pub is None else (0, -parse_ts(pub).timestamp())
    prov = PROVIDERS.index(c["provider"]) if c.get("provider") in PROVIDERS else 9
    v = norm(c.get("value"))
    return (AUTH.get(c.get("kind"), 2), rec, c.get("url") or "", prov,
            (0, v, "") if isinstance(v, int) else (1, 0, v or ""))


def select(cands):
    """(value, true_from, citations) by the stage-2 selection rule; None value when no candidate."""
    if not cands:
        return None, None, []
    r = sorted(cands, key=rank_key)
    top = norm(r[0]["value"])
    cits = [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]} for c in r if norm(c["value"]) == top]
    return top, r[0].get("true_from"), cits


def select_exec(cands):
    members, cits, tfs = [], [], []
    for t in TITLES:
        mine = [c for c in cands if c.get("title") == t]
        if not mine:
            continue
        v, tf, cs = select(mine)
        members.append({"title": t, "name": v})
        cits.extend(cs)
        tfs.append(tf)
    if not members:
        return None, None, []
    return members, (None if any(x is None for x in tfs) else max(tfs)), cits
