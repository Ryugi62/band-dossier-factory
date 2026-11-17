#!/usr/bin/env python3
"""Verifier black-box probes for dossier stage 3 (API part, restart phases).

  python3 run3.py --phase main|pre-restart|post-restart|pre-kill|post-kill \
     --service http://svc:8080 --service1 http://svc1:8080 --service2 http://svc2:8080 \
     --mock http://web:8080 --admin local-admin --corpus /corpus --state /logs [--only C01]

Phase main re-runs every stage-1 and stage-2 API probe with the stage-3 invariants (INV3) patched in,
then the stage-3 probes C01..C05 and the upgrade probes U3 (stage-1 export) and U4 (stage-2 export).
The restart phases are run by run_all.sh around `docker kill` + `docker start` of the service.
Each probe names the ledger rows (factory/ledger/stage-3.md) it covers. Standard library only.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import traceback
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PROBES = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROBES, "stage-2"))
sys.path.insert(0, HERE)
import run2  # noqa: E402  (imports the stage-1 probes)
import oracle3 as O  # noqa: E402

s1, A = run2.s1, run2.A
FIELDS = list(A.FIELDS)
F7 = O.FIELDS7
TITLES = O.TITLES
LUMEN = "lumen-atlas.test"
T0 = s1.T0


def tsp(**kw):
    return s1.ts_plus(T0, **kw)


def same_instant(a, b):
    return run2.same_instant(a, b)


class Ctx3(run2.Ctx2):
    def __init__(self, args):
        super().__init__(args)
        self.svc2 = urllib.parse.urlparse(args.service2) if args.service2 else None
        self.builds = {}     # domain -> [{time, ok, spent, fields, versions, snapshot}]

    def req2(self, method, path, body=None, token=None, key=None):
        h = {}
        if token is not None:
            h["Authorization"] = f"Bearer {token}"
        if key is not None:
            h["Idempotency-Key"] = key
        return self._http(self.svc2, method, path, body, h, None, 10.0 if path.startswith("/_test") else 5.0)

    def reset(self, fixture=None):
        self.builds = {}
        self.imported = set()
        return super().reset(fixture)

    # ------------------------------------------------------------ INV3
    def inv(self, d):
        if not isinstance(d, dict):
            self.check(False, f"INV3: dossier not an object: {d!r}")
            return
        dom, ra = d.get("domain"), d.get("researched_at")
        f = d.get("fields")
        if not isinstance(f, dict) or list(f) != F7 and sorted(f) != sorted(F7):
            self.check(False, f"INV3 {dom}: fields keys {list(f) if isinstance(f, dict) else f!r} != seven [T2-01]")
            return
        six = dict(d, fields={k: f[k] for k in FIELDS})
        super().inv(six)
        for name in FIELDS:
            for m in self._inv_times(name, f[name], ra):
                self.check(False, f"INV3 {dom}: {name}: {m}")
        for m in self._inv_exec(dom, f["executives"], ra):
            self.check(False, f"INV3 {dom}: executives: {m}")

    def _inv_times(self, name, fv, ra):
        p = []
        cands = fv.get("candidates") or []
        for i, c in enumerate(cands):
            if not isinstance(c, dict):
                continue
            if "true_from" not in c or "learned_at" not in c:
                p.append(f"candidate {i} lacks true_from/learned_at [T1-05]")
                continue
            if c["true_from"] is not None and not O.valid_date(c["true_from"]):
                p.append(f"candidate {i} true_from {c['true_from']!r} not YYYY-MM-DD [T1-02]")
            la = c["learned_at"]
            if not (isinstance(la, str) and O.TS_RE.match(la)):
                p.append(f"candidate {i} learned_at {la!r} [T1-03]")
            elif c.get("retrieved_at") and O.parse_ts(la) > O.parse_ts(c["retrieved_at"]):
                p.append(f"candidate {i} learned_at {la} after retrieved_at {c['retrieved_at']} [T1-03, T1-06]")
        if "true_from" not in fv or "learned_at" not in fv:
            return p + ["field lacks true_from/learned_at [T1-08]"]
        if fv.get("value") is None:
            if fv["true_from"] is not None or fv["learned_at"] is not None:
                p.append(f"unknown field has true_from {fv['true_from']!r} / learned_at {fv['learned_at']!r} [T1-09]")
        else:
            if cands and isinstance(cands[0], dict) and name != "executives" and fv["true_from"] != cands[0].get("true_from"):
                p.append(f"true_from {fv['true_from']!r} != selected candidate's {cands[0].get('true_from')!r} [T1-07]")
            la = fv["learned_at"]
            if not (isinstance(la, str) and O.TS_RE.match(la)):
                p.append(f"learned_at {la!r} [T1-04]")
            elif ra and O.parse_ts(la) > O.parse_ts(ra):
                p.append(f"learned_at {la} after researched_at {ra} [T1-04]")
        return p

    def _inv_exec(self, dom, fv, ra):
        p = []
        if not isinstance(fv, dict):
            return ["not an object"]
        v, st, cits, cands = fv.get("value"), fv.get("status"), fv.get("citations"), fv.get("candidates")
        if not isinstance(cands, list) or not isinstance(cits, list):
            return [f"candidates/citations not lists [T2-07]"]
        for i, c in enumerate(cands):
            if not isinstance(c, dict) or c.get("title") not in TITLES or not isinstance(c.get("value"), str):
                p.append(f"candidate {i} {c!r}: needs title in cfo/coo/cto and a string name [T2-06]")
                continue
            for k in ("url", "excerpt", "provider", "kind", "published_at", "retrieved_at", "selected", "true_from", "learned_at"):
                if k not in c:
                    p.append(f"candidate {i} lacks {k} [T2-06]")
            if c.get("kind") is None and dom not in self.imported:
                p.append(f"candidate {i} kind null [Q5-09]")
            got = O.supported_title(c.get("excerpt") or "", c["title"], dom) if isinstance(dom, str) else None
            if got != O.norm(c["value"]):
                p.append(f"candidate {i} {c['title']}={c['value']!r}: excerpt {c.get('excerpt')!r} supports {got!r} [T2-05, R1-05]")
            if c.get("retrieved_at") and ra and not same_instant(c["retrieved_at"], ra):
                p.append(f"candidate {i} retrieved_at != researched_at [T1-06]")
            with self.lock:
                self.citations.setdefault((c.get("url"), c.get("excerpt"), c.get("provider")), (dom, "executives", c["value"], self.current))
        if p:
            return p
        p += self._inv_times("executives", fv, ra)
        order = [(TITLES.index(c["title"]),) + O.rank_key(c) for c in cands]
        if order != sorted(order):
            p.append("candidates not by title (cfo, coo, cto) then rank order [T2-09]")
        keys = [(c["title"], c["url"], c["provider"], O.norm(c["value"])) for c in cands]
        if len(keys) != len(set(keys)):
            p.append("duplicate candidate (title, url, provider, value) [QD-19]")
        members, exp_cits, tfs = [], [], []
        for t in TITLES:
            mine = [c for c in cands if c["title"] == t]
            if not mine:
                continue
            if not mine[0].get("selected") or any(c.get("selected") for c in mine[1:]):
                p.append(f"{t}: selected must be true on the highest-ranked candidate only [T2-08]")
            name = O.norm(mine[0]["value"])
            members.append({"title": t, "name": name})
            exp_cits += [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]}
                         for c in mine if O.norm(c["value"]) == name]
            tfs.append(mine[0].get("true_from"))
        if not members:
            if v is not None or st != "unknown" or cits != []:
                p.append(f"no candidates but value {v!r} status {st!r} [T2-04, T2-11]")
            return p
        if O.norm_members(v) != members:
            p.append(f"value {v!r} != members {members} (one per title with a selected person, order cfo, coo, cto) [T2-03]")
        got_cits = [{"url": c.get("url"), "excerpt": c.get("excerpt"), "provider": c.get("provider")} for c in cits]
        if got_cits != exp_cits:
            p.append(f"citations {got_cits} != per member candidates in rank order {exp_cits} [T2-10]")
        contested = any(len({O.norm(c["value"]) for c in cands if c["title"] == t}) > 1 for t in TITLES)
        want = "contested" if contested else "known"
        if st != want:
            p.append(f"status {st!r}, rule gives {want} [T2-11]")
        want_tf = None if any(x is None for x in tfs) else max(tfs)
        if fv.get("true_from") != want_tf:
            p.append(f"true_from {fv.get('true_from')!r} != latest member true_from {want_tf!r} [T2-13]")
        return p

    # ------------------------------------------------------------ EV3 (executives, true_from of every candidate)
    def ev(self, d, epoch, research_ok=True):
        super().ev(d, epoch, research_ok)
        dom = d.get("domain")
        corp = self.corpus.get(dom)
        if corp is None:
            return
        claims = (corp.get("research", {}).get("nimble", {}) or {}).get(str(epoch), []) if research_ok else []
        cited = {r.get("url") for r in claims}
        pages = {p["url"]: p for p in corp["pages"] if epoch in p["epochs"] and (p.get("searchable", True) or p["url"] in cited)}
        fields = d.get("fields") or {}
        ex = (fields.get("executives") or {}).get("candidates") or []
        for url, p in pages.items():
            for t, names in O.page_titles(p["text"], dom).items():
                for name, sent in names.items():
                    hit = [c for c in ex if c.get("title") == t and c.get("url") == url and O.norm(c.get("value")) == name]
                    if not self.check(hit, f"EV3 {dom} epoch {epoch}: missing executives candidate {t}={name!r} from {url} "
                                           f"({sent!r}) [T2-06, Q5-02]"):
                        continue
                    for c in hit:
                        self.check(A.collapse_ws(c.get("excerpt") or "") == sent, f"EV3 {dom}: {t} excerpt is not the first "
                                                                                 f"supporting sentence [QD-19]")
                        self.check(c.get("kind") == run2.expected_kind(p, dom), f"EV3 {dom}: {t} candidate kind [Q1-01]")
        for f in F7:
            for c in (fields.get(f) or {}).get("candidates") or []:
                p = pages.get(c.get("url"))
                if p is None:
                    continue
                want = O.page_true_from(p.get("true_from"), p.get("published_at"))
                self.check(c.get("true_from") == want, f"EV3 {dom} epoch {epoch}: {f} candidate {c.get('url')} true_from "
                                                       f"{c.get('true_from')!r}, page gives {want!r} (Effective "
                                                       f"{p.get('true_from')!r}, Published {p.get('published_at')!r}) [T1-02]")
        if self.renders is not None:
            for c in ex:
                texts = self.renders.get(c.get("url"), [])
                self.check(any(s1.excerpt_in(c.get("excerpt") or "", A.split_prose(t)[1]) for t in texts),
                           f"D13 {dom}: executives candidate not in a rendered extract of {c.get('url')} [QD-13]")

    # ------------------------------------------------------------ build log for the oracles
    def record(self, dom, d, spent_delta, ok=True, time_=None):
        versions = {}
        if ok:
            for f in F7:
                for c in (d["fields"].get(f) or {}).get("candidates") or []:
                    url = c.get("url")
                    tf = c.get("true_from")
                    if url in versions and versions[url][0] != tf:
                        self.check(False, f"{dom}: candidates of one page {url} carry different true_from [T1-02]")
                    versions.setdefault(url, (tf, []))[1].append(dict(c, field=f))
            for url, texts in (self.renders or {}).items():
                if url not in versions and texts:
                    hdr = {}
                    for line in A.split_prose(texts[-1])[0]:
                        k, _, v = line.partition(":")
                        hdr[k.strip()] = v.strip()
                    versions[url] = (O.page_true_from(hdr.get("Effective"), hdr.get("Published")), [])
        self.builds.setdefault(dom, []).append({"time": time_ or d.get("researched_at"), "ok": ok, "spent": spent_delta,
                                                "versions": versions, "snapshot": d})

    def build(self, token, dom, epoch, fresh, what, exact=None, mock_reset=True):
        if mock_reset:
            self.mock_reset(epoch)
        d = s1.build_and_check(self, token, dom, epoch, exact=exact, what=what, fresh=fresh)
        if d and d.get("state") == "ready":
            prev = sum(b["spent"] for b in self.builds.get(dom, []))
            self.record(dom, d, d["spent_units"] - prev)
        return d


# ---------------------------------------------------------------- oracles over the recorded builds

def history_oracle(c, token, dom):
    bs = [b for b in c.builds.get(dom, []) if b["ok"]]
    exp = {f: [] for f in F7}
    feed = []
    prev, first = {f: None for f in F7}, True
    for b in bs:
        snap = b["snapshot"]["fields"]
        per_build = []
        for f in F7:
            new = snap[f]["value"]
            if first:
                if new is not None:
                    exp[f].append(("initial", snap[f], b["time"]))
            elif not O.same_value(prev[f][0] if prev[f] else None, new):
                old = prev[f][0] if prev[f] else None
                if f == "executives":
                    omt = prev[f][2] if prev[f] else {}
                    nmt = _member_tf(snap[f])
                    typ = O.change_type(f, old, new, None, None, omt, nmt)
                else:
                    typ = O.change_type(f, old, new, prev[f][1] if prev[f] else None, snap[f]["true_from"])
                exp[f].append((typ, snap[f], b["time"]))
                per_build.append({"field": f, "type": typ, "from": old, "to": new, "true_from": snap[f]["true_from"],
                                  "learned_at": b["time"]})
            prev[f] = (new, snap[f]["true_from"], _member_tf(snap[f]) if f == "executives" else None) if new is not None else None
        first = False
        feed += per_build
    h = c.req("GET", f"/dossiers/{dom}/history", token=token)
    if not c.expect(h, 200, what=f"history {dom} [T6-01]"):
        return exp, feed
    hf = (h.body or {}).get("fields") or {}
    c.check(h.body.get("domain") == dom and sorted(hf) == sorted(F7), f"history shape {list(hf)} [T6-02]")
    for f in F7:
        got = hf.get(f) or []
        want = exp[f]
        c.check(len(got) == len(want) and all(g.get("type") == w[0] for g, w in zip(got, want)),
                f"history {dom} {f}: types {[g.get('type') for g in got]} != {[w[0] for w in want]} [T3-01..T3-06, T6-02]")
        for g, (typ, sf, bt) in zip(got, want):
            # learned_at is the time of the build that recorded the entry, also when the new value is null
            c.check(O.same_value(g.get("value"), sf["value"]) and g.get("true_from") == sf["true_from"]
                    and same_instant(g.get("learned_at"), bt) and g.get("citations") == sf["citations"],
                    f"history {dom} {f} {typ} entry {g} != selected value then {sf['value']!r} tf {sf['true_from']!r} "
                    f"learned {bt} [T6-03]")
        cur = bs[-1]["snapshot"]["fields"][f] if bs else None
        if cur and cur["value"] is not None and got:
            c.check(same_instant(cur["learned_at"], got[-1].get("learned_at")),
                    f"{dom} {f}: field learned_at {cur['learned_at']} != its latest history entry's [T1-04, TD-32]")
    return exp, feed


def _member_tf(fv):
    out = {}
    for cnd in fv.get("candidates") or []:
        if cnd.get("selected") and cnd.get("title") not in out:
            out[cnd["title"]] = cnd.get("true_from")
    return out


def feed_oracle(c, token, feed_by_dom, since0=0):
    """Feed entries must be exactly the expected ones: per build in field order, seq strictly increasing."""
    got = []
    since = since0
    while True:
        r = c.req("GET", f"/changes?since={since}&limit=200", token=token)
        if not c.expect(r, 200, what="GET /changes [T7-01]"):
            return []
        got += r.body.get("changes", [])
        if not r.body.get("has_more"):
            break
        since = got[-1]["seq"]
    seqs = [g.get("seq") for g in got]
    c.check(all(isinstance(s, int) and s > 0 for s in seqs) and seqs == sorted(set(seqs)),
            f"feed seq {seqs} not positive, unique and ascending [T7-02, T7-07]")
    key = lambda e: (e.get("domain"), e.get("field"), e.get("type"), json.dumps(O.norm_members(e.get("from"))),
                     json.dumps(O.norm_members(e.get("to"))), e.get("true_from"))
    total = 0
    for dom, entries in feed_by_dom.items():
        want = [dict(e, domain=dom) for e in entries]      # build order, then field order within a build
        mine = [g for g in got if g.get("domain") == dom]
        total += len(want)
        c.check([key(g) for g in mine] == [key(w) for w in want],
                f"feed of {dom} in seq order {[key(g)[1:3] for g in mine]} != expected {[key(w)[1:3] for w in want]} "
                f"(build order, then field order) [T7-01, T7-03, T3-04, T8-02]")
        for g, w in zip(mine, want):
            c.check(same_instant(g.get("learned_at"), w["learned_at"]), f"feed {g} learned_at != build time {w['learned_at']} [T7-04]")
    c.check(len(got) == total, f"feed holds {len(got)} entries, {total} expected [T8-02]")
    return got


def asof_oracle(c, token, dom, times):
    bs = c.builds.get(dom, [])
    for t in times:
        upto = [b for b in bs if b["time"] and O.parse_ts(b["time"]) <= O.parse_ts(t)]
        ready = [b for b in upto if b["ok"]]
        r = c.req("GET", f"/dossiers/{dom}?as_of=" + urllib.parse.quote(t), token=token)
        if not ready:
            c.expect(r, 404, "not_found", f"as_of {t} before any ready build [T4-03]")
            continue
        if not c.expect(r, 200, what=f"as_of {t} [T4-01]"):
            continue
        want = ready[-1]["snapshot"]
        got = r.body
        c.check(got.get("state") == "ready", f"as_of {t}: state {got.get('state')!r} [T4-01]")
        c.check(got.get("researched_at") and same_instant(got["researched_at"], want["researched_at"]),
                f"as_of {t}: researched_at {got.get('researched_at')} != {want['researched_at']} (last ready build at or "
                f"before as_of, last in build order) [T4-01, T4-02]")
        c.check(got.get("spent_units") == sum(b["spent"] for b in upto),
                f"as_of {t}: spent_units {got.get('spent_units')} != {sum(b['spent'] for b in upto)} [T4-01]")
        for f in F7:
            gf, wf = (got.get("fields") or {}).get(f) or {}, want["fields"][f]
            for k in ("value", "status", "citations", "candidates", "true_from", "learned_at"):
                ok = (same_instant(gf.get(k), wf.get(k)) if k == "learned_at" and wf.get(k) else gf.get(k) == wf.get(k))
                c.check(ok, f"as_of {t}: {f}.{k} {gf.get(k)!r:.120} != snapshot {wf.get(k)!r:.120} [T4-01, T1-10]")
        c.inv(got)


def values_oracle(c, token, dom, true_ats, as_ofs):
    bs = c.builds.get(dom, [])
    for as_of in as_ofs:
        known = [b for b in bs if b["ok"] and (as_of is None or O.parse_ts(b["time"]) <= O.parse_ts(as_of))]
        for ta in true_ats:
            path = f"/dossiers/{dom}/values?true_at={ta}" + (f"&as_of={urllib.parse.quote(as_of)}" if as_of else "")
            r = c.req("GET", path, token=token)
            if not known:
                c.expect(r, 404, "not_found", f"values as_of {as_of} before any ready build [T5-12]")
                continue
            if not c.expect(r, 200, what=f"GET {path} [T5-01]"):
                continue
            body = r.body or {}
            c.check(body.get("domain") == dom and body.get("true_at") == ta, f"values envelope {str(body)[:200]} [T5-08]")
            if as_of:
                c.check(body.get("as_of") and same_instant(body["as_of"], as_of), f"values as_of echo {body.get('as_of')} [T5-08]")
            gf = body.get("fields") or {}
            c.check(sorted(gf) == sorted(F7), f"values fields {sorted(gf)} [T5-08]")
            for f in F7:
                alts = []
                for nh in (False,):   # D33: a null-dated version holds on no date
                    cands = [x for x in O.candidates_at(known, ta, nh) if x["field"] == f]
                    alts.append(O.select_exec(cands) if f == "executives" else O.select(cands))
                g = gf.get(f) or {}
                got = (O.norm_members(g.get("value")), g.get("true_from"), g.get("citations"))
                ok = any(got == (O.norm_members(v), tf, cits) for v, tf, cits in alts)
                c.check(ok, f"values {dom} true_at {ta} as_of {as_of}: {f} = {got[0]!r} tf {got[1]!r} cits {len(got[2] or [])}; "
                            f"page versions give {[(a[0], a[1]) for a in alts]} [T5-02..T5-07]")
                if g.get("value") is None:
                    c.check(g.get("true_from") is None and g.get("citations") == [], f"values {f} null needs null true_from, [] [T5-10]")


# ---------------------------------------------------------------- probes

PROBES3 = []


def probe(pid, rows, title):
    def deco(fn):
        PROBES3.append((pid, rows, title, fn))
        return fn
    return deco


LUMEN_EXP = {
    0: {"legal_name": ("Lumen Atlas S.A.", "2020-05-01"), "hq_city": ("Porto", "2020-05-01"), "ceo": ("Rita Gomes", "2021-01-01"),
        "founded_year": (2019, "2020-05-01"), "headcount_range": ("11-50", "2025-03-01"), "funding_total": (8000000, "2025-06-10"),
        "executives": ([{"title": "cfo", "name": "Ana Silva"}, {"title": "cto", "name": "Bruno Costa"}], "2021-01-01")},
    1: {"ceo": ("Tiago Neves", "2026-02-01"), "headcount_range": (None, None), "funding_total": (9000000, "2025-06-01"),
        "executives": ([{"title": "cfo", "name": "Ana Silva"}, {"title": "coo", "name": "Marta Reis"},
                        {"title": "cto", "name": "Bruno Costa"}], "2026-02-01")},
    2: {"ceo": ("Rita Gomes", "2021-01-01"),
        "executives": ([{"title": "cfo", "name": "Ana Silva"}, {"title": "coo", "name": "Marta Reis"},
                        {"title": "cto", "name": "Bruna Costa"}], "2026-01-15")},
    3: {"hq_city": ("Braga", "2026-03-01"), "legal_name": ("Lumen Atlas S.A.", "2026-03-01"),
        "founded_year": (2019, "2026-03-01")},
}
LUMEN_FEED = [("ceo", "change"), ("headcount_range", "change"), ("funding_total", "correction"), ("executives", "change"),
              ("ceo", "correction"), ("executives", "correction"), ("hq_city", "change")]


def lumen_timeline(c, ada):
    """Builds lumen at epochs 0..4: T0, T0+1d, T0+2d, T0+2d (clock held still), T0+4d."""
    times = [T0, tsp(days=1), tsp(days=2), tsp(days=2), tsp(days=4)]
    exp = {}
    for e, t in enumerate(times):
        if e:
            c.req("POST", "/_test/clock", {"now": t})
        d = c.build(ada, LUMEN, e, e == 0, f"lumen e{e}")
        if not d:
            return None
        exp.update(LUMEN_EXP.get(e, {}))
        for f, (v, tf) in exp.items():
            fv = d["fields"].get(f) or {}
            c.check(O.same_value(fv.get("value"), v) and fv.get("true_from") == tf,
                    f"lumen epoch {e}: {f} = {fv.get('value')!r} tf {fv.get('true_from')!r}, expected {v!r} tf {tf!r} [T1-*, T2-*]")
        c.check((d["fields"].get("executives") or {}).get("status") == "contested", "lumen executives: two CTO names -> contested [T2-11]")
        c.check(same_instant(d["researched_at"], t), f"lumen e{e} researched_at {d['researched_at']} != {t}")
    return times


@probe("C01", "T1-* T2-* T3-* T4-* T5-* T6-* T7-* TD-32", "change over time on lumen-atlas.test: two times, executives, "
       "history, feed, as_of (equal times, offsets), values (page versions)")
def c01(c):
    c.reset()
    ada = c.login("ada@example.com")
    times = lumen_timeline(c, ada)
    if not times:
        return
    exp, feed = history_oracle(c, ada, LUMEN)
    c.check([(e["field"], e["type"]) for e in feed] == LUMEN_FEED,
            f"lumen feed from observed values {[(e['field'], e['type']) for e in feed]} != spec {LUMEN_FEED} [T3-01, T2-14]")
    got = feed_oracle(c, ada, {LUMEN: feed})
    c.check([(g.get("field"), g.get("type")) for g in got] == LUMEN_FEED, f"GET /changes {[(g.get('field'), g.get('type')) for g in got]} "
                                                                         f"!= {LUMEN_FEED} [T7-01, T7-03]")
    t2 = times[2]
    t2_other = O.parse_ts(t2).astimezone(__import__("datetime").timezone(__import__("datetime").timedelta(hours=-5))).isoformat()
    asof_oracle(c, ada, LUMEN, [s1.ts_plus(T0, seconds=-1), T0, tsp(hours=12), times[1], t2, t2_other, tsp(days=3), times[4],
                                tsp(days=30)])
    tas = ["2019-01-01", "2021-06-01", "2024-03-05", "2024-03-06", "2025-06-05", "2025-06-15", "2026-01-20", "2026-02-15",
           "2026-03-05"]
    values_oracle(c, ada, LUMEN, tas, [T0, times[1], t2, times[4], None])
    r = c.req("GET", f"/dossiers/{LUMEN}/values?true_at=2026-02-15&as_of=" + urllib.parse.quote(times[1]), token=ada)
    if r.status == 200:
        c.check(r.body["fields"]["ceo"]["value"] == "Tiago Neves", "values at 2026-02-15 as of T1: ceo should be Tiago Neves [T5-02]")
    r = c.req("GET", f"/dossiers/{LUMEN}/values?true_at=2026-02-15", token=ada)
    if r.status == 200:
        c.check(r.body["fields"]["headcount_range"]["value"] == "11-50",
                "values at 2026-02-15 now: the dated headcount page no later build gathered still holds -> 11-50 [T5-14]")
        c.check(r.body["fields"]["ceo"]["value"] == "Rita Gomes", "values at 2026-02-15 now: the 2021 team version replaced the "
                                                                  "2026 one -> Rita Gomes [T5-03]")
        c.check(r.body.get("as_of") and same_instant(r.body["as_of"], times[4]), f"values as_of default {r.body.get('as_of')} "
                                                                                 f"!= clock {times[4]} [T5-04]")


@probe("C02", "T4-04 T4-05 T5-11 T5-12 T6-04 T7-06 T7-08 TD-29 R5-10", "validation and errors of as_of, values, history, changes")
def c02(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    c.post(ada, s1.ZEPHYR)
    c.wait(ada, s1.ZEPHYR)
    q = urllib.parse.quote
    for path, st, code, why in [
        (f"/dossiers/{s1.ZEPHYR}?as_of=2026-03-01T09:00:00", 422, "validation_failed", "as_of without offset [T4-04]"),
        (f"/dossiers/{s1.ZEPHYR}?as_of=yesterday", 422, "validation_failed", "as_of not RFC 3339 [T4-04]"),
        (f"/dossiers/absent-co.test?as_of=bad", 422, "validation_failed", "bad as_of on unknown dossier: 422 before 404 [TD-29]"),
        (f"/dossiers/absent-co.test?as_of={q(T0)}", 404, "not_found", "as_of of unknown dossier [T4-05]"),
        (f"/dossiers/{s1.ZEPHYR}/values", 422, "validation_failed", "true_at missing [T5-11]"),
        (f"/dossiers/{s1.ZEPHYR}/values?true_at=2025-02-30", 422, "validation_failed", "true_at not a calendar date [TD-29]"),
        (f"/dossiers/{s1.ZEPHYR}/values?true_at=2025-6-1", 422, "validation_failed", "true_at not YYYY-MM-DD [T5-11]"),
        (f"/dossiers/{s1.ZEPHYR}/values?true_at=2025-06-01T00:00:00Z", 422, "validation_failed", "true_at with a time [T5-11]"),
        (f"/dossiers/{s1.ZEPHYR}/values?true_at=2025-06-01&as_of=2026-03-01", 422, "validation_failed", "values as_of a date [T5-11]"),
        (f"/dossiers/absent-co.test/values?true_at=2025-06-01", 404, "not_found", "values of unknown dossier [T5-12]"),
        (f"/dossiers/absent-co.test/values?true_at=nope", 422, "validation_failed", "bad true_at on unknown dossier [TD-29]"),
        (f"/dossiers/{s1.ZEPHYR}/values?true_at=2025-06-01&as_of={q(s1.ts_plus(T0, seconds=-1))}", 404, "not_found",
         "values as_of before the first ready build [T5-12]"),
        ("/dossiers/absent-co.test/history", 404, "not_found", "history of unknown dossier [T6-04]"),
        ("/dossiers/localhost/history", 422, "validation_failed", "history of an invalid domain [R4-11]"),
        ("/changes?since=-1", 422, "validation_failed", "since negative [T7-06]"),
        ("/changes?since=1e2", 422, "validation_failed", "since not plain digits [R5-10]"),
        ("/changes?since=abc", 422, "validation_failed", "since not an integer [T7-06]"),
        ("/changes?limit=0", 422, "validation_failed", "limit 0 [T7-08]"),
        ("/changes?limit=201", 422, "validation_failed", "limit 201 [T7-08]"),
        ("/changes?limit=%2B4", 422, "validation_failed", "limit +4 [R5-10]")]:
        c.expect(c.req("GET", path, token=ada), st, code, why)
    for path in (f"/dossiers/{s1.ZEPHYR}/history", "/changes", f"/dossiers/{s1.ZEPHYR}/values?true_at=2025-01-01",
                 f"/dossiers/{s1.ZEPHYR}?as_of={q(T0)}", "/changes?since=bad"):
        c.expect(c.req("GET", path), 401, "unauthenticated", f"{path} without token [R6-09, TD-29]")
    r = c.req("GET", "/changes", token=ada)
    c.check(r.status == 200 and r.body == {"changes": [], "has_more": False}, f"empty feed after a first build {r!r} [T3-04]")
    c.mock_reset(0)
    for path in (f"/dossiers/{s1.ZEPHYR}/history", "/changes", f"/dossiers/{s1.ZEPHYR}/values?true_at=2025-01-01",
                 f"/dossiers/{s1.ZEPHYR}?as_of={q(T0)}"):
        c.req("GET", path, token=ada)
    time.sleep(0.3)
    c.check(c.mock_log() == [], "history/changes/values/as_of made a provider call [R8-13]")


@probe("C03", "T8-01 T8-02 T3-07 R8-31", "burst of concurrent refreshes: one build, each change exactly once in the feed")
def c03(c):
    c.reset()
    ada = c.login("ada@example.com")
    c.build(ada, LUMEN, 0, True, "C03 e0")
    c.req("POST", "/_test/clock", {"now": tsp(days=1)})
    c.mock_reset(1)
    c.mock_fault("nimble", ["research"], "delay", 2)
    rs = run2.s1.par(12, lambda i: c.refresh(ada, LUMEN))
    c.check(all(r.status in (200, 202) for r in rs), f"burst statuses {[r.status for r in rs]}")
    d, _ = c.wait(ada, LUMEN, timeout=40)
    research = [x for x in c.mock_log() if x.get("method") == "research"]
    c.check(len(research) == 1, f"12 concurrent refreshes ran {len(research)} builds [T8-01, R8-31]")
    if d and d.get("state") == "ready":
        prev = sum(b["spent"] for b in c.builds.get(LUMEN, []))
        c.record(LUMEN, d, d["spent_units"] - prev)
        exp, feed = history_oracle(c, ada, LUMEN)
        got = feed_oracle(c, ada, {LUMEN: feed})
        c.check(len(got) == 4, f"feed after one changed build has {len(got)} entries, 4 expected exactly once [T8-02]")
    c.mock_reset(0)


@probe("C04", "QX3-* T9-05 TD-26 TD-28", "stage-3 export/import: builds, versions, history, feed survive; seq continues")
def c04(c):
    c.reset()
    ada = c.login("ada@example.com")
    times = lumen_timeline(c, ada)
    if not times:
        return
    q = urllib.parse.quote
    paths = [f"/dossiers/{LUMEN}", f"/dossiers/{LUMEN}/history", "/changes?limit=200", "/dossiers?limit=200"]
    paths += [f"/dossiers/{LUMEN}?as_of={q(t)}" for t in (T0, times[1], times[2], times[4])]
    paths += [f"/dossiers/{LUMEN}/values?true_at={ta}&as_of={q(t)}" for ta in ("2025-06-15", "2026-02-15")
              for t in (times[1], times[4])]
    before = {p: c.req("GET", p, token=ada).body for p in paths}
    x = c.req("GET", "/_test/export")
    if not c.expect(x, 200, what="stage-3 export"):
        return
    c.check(x.body.get("track") == "dossier" and x.body.get("format_version") == 1, "export envelope [TD-26]")
    c.reset()
    c.mock_reset(0)
    c.expect(c.req("POST", "/_test/import", x.body), 204, what="stage-3 import")
    for p in paths:
        c.check(c.req("GET", p, token=ada).body == before[p], f"{p} differs after a stage-3 export/import [T9-05, QX3-*]")
    time.sleep(0.3)
    c.check(c.mock_log() == [], "import made a provider call [R10-20]")
    maxseq = max(e["seq"] for e in before["/changes?limit=200"]["changes"])
    c.req("POST", "/_test/clock", {"now": tsp(days=5)})
    c.mock_reset(1)
    c.expect(c.refresh(ada, LUMEN), 202, what="refresh after import")
    c.wait(ada, LUMEN, timeout=30)
    r = c.req("GET", f"/changes?since={maxseq}", token=ada)
    c.check(r.status == 200 and r.body["changes"] and all(e["seq"] > maxseq for e in r.body["changes"]),
            f"new feed entries after a stage-3 import must continue after seq {maxseq}: {r!r} [TD-28, T7-02]")


@probe("C05", "T7-02 T7-05 T7-07 T7-08 T7-09", "GET /changes paging: since, limit, has_more")
def c05(c):
    c.reset()
    ada = c.login("ada@example.com")
    if not lumen_timeline(c, ada):
        return
    full = c.req("GET", "/changes", token=ada).body["changes"]
    c.check(len(full) == 7, f"default since=0 lists {len(full)} entries [T7-05]")
    r = c.req("GET", "/changes?limit=3", token=ada).body
    c.check(r["changes"] == full[:3] and r["has_more"] is True, "limit=3 [T7-08, T7-09]")
    r = c.req("GET", f"/changes?since={full[2]['seq']}&limit=3", token=ada).body
    c.check(r["changes"] == full[3:6] and r["has_more"] is True, "since + limit [T7-05, T7-09]")
    r = c.req("GET", f"/changes?since={full[5]['seq']}", token=ada).body
    c.check(r["changes"] == full[6:] and r["has_more"] is False, "last page has_more false [T7-09]")
    r = c.req("GET", f"/changes?since={full[-1]['seq']}", token=ada).body
    c.check(r == {"changes": [], "has_more": False}, "since the last seq [T7-05]")
    for e in full:
        c.check(set(e) >= {"seq", "domain", "field", "type", "from", "to", "true_from", "learned_at"}, f"feed entry keys {sorted(e)} [T7-01]")


@probe("U3", "T9-01..T9-04 T9-06 T9-07 T9-11 TD-25 TD-26 TD-28", "upgrade from a stage-1 export (service at 9166a28)")
def u3(c):
    if c.svc1 is None:
        return c.check(False, "no --service1")
    c.mock_reset(0)
    c.req1("POST", "/_test/reset", s1.FIXTURE)
    t1 = c.req1("POST", "/auth/login", {"email": "ada@example.com", "password": s1.PW}).body["token"]
    lost = c.req1("POST", "/dossiers", {"domain": LUMEN}, token=t1, key="u3-lumen")
    run2._wait1(c, t1, LUMEN)
    c.req1("POST", "/dossiers", {"domain": "nowhere-known.test"}, token=t1, key="u3-nw")
    run2._wait1(c, t1, "nowhere-known.test")
    c.mock_fault("nimble", ["search", "extract", "research"], "error")
    c.req1("POST", "/dossiers", {"domain": "ashgrove-solar.test"}, token=t1, key="u3-fail")
    run2._wait1(c, t1, "ashgrove-solar.test", 60)
    old = {d: c.req1("GET", f"/dossiers/{d}", token=t1).body for d in (LUMEN, "nowhere-known.test", "ashgrove-solar.test")}
    e = c.req1("GET", "/_test/export").body
    c.reset()
    c.mock_reset(0)
    c.imported |= set(old)
    if not c.expect(c.req("POST", "/_test/import", e), 204, what="stage-3 import of a stage-1 export [T9-01]"):
        return
    _check_upgraded(c, t1, old, stage=1)
    rp = c.req("POST", "/dossiers", {"domain": LUMEN}, token=t1, key="u3-lumen")
    c.check(rp.status == 200 and rp.body == lost.body, f"completed idempotent response after upgrade {rp!r} [T9-04]")
    r = c.req("GET", "/dossiers/ashgrove-solar.test?as_of=" + urllib.parse.quote(tsp(days=100)), token=t1)
    c.expect(r, 404, "not_found", "imported dossier with null researched_at answers every as_of with 404 [T9-07]")
    _first_build_after_import(c, t1, old[LUMEN])


@probe("U4", "T9-01..T9-04 T9-08..T9-11 TD-25 TD-26 TD-28", "upgrade from a stage-2 export (service at 3e32ac8)")
def u4(c):
    if c.svc2 is None:
        return c.check(False, "no --service2")
    c.mock_reset(0)
    c.req2("POST", "/_test/reset", s1.FIXTURE)
    t2 = c.req2("POST", "/auth/login", {"email": "ada@example.com", "password": s1.PW}).body["token"]
    lost = c.req2("POST", "/dossiers", {"domain": LUMEN}, token=t2, key="u4-lumen")
    _wait_svc(c.req2, t2, LUMEN)
    c.req2("POST", "/dossiers", {"domain": run2.KESTREL}, token=t2, key="u4-k")
    _wait_svc(c.req2, t2, run2.KESTREL)
    old = {d: c.req2("GET", f"/dossiers/{d}", token=t2).body for d in (LUMEN, run2.KESTREL)}
    e = c.req2("GET", "/_test/export").body
    c.reset()
    c.mock_reset(0)
    c.imported |= set(old)
    if not c.expect(c.req("POST", "/_test/import", e), 204, what="stage-3 import of a stage-2 export [T9-01]"):
        return
    _check_upgraded(c, t2, old, stage=2)
    rp = c.req("POST", "/dossiers", {"domain": LUMEN}, token=t2, key="u4-lumen")
    c.check(rp.status == 200 and rp.body == lost.body, f"completed idempotent response after upgrade {rp!r} [T9-04]")
    _first_build_after_import(c, t2, old[LUMEN])


def _wait_svc(fn, tok, dom, timeout=30):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        r = fn("GET", f"/dossiers/{dom}", token=tok)
        if r.status == 200 and r.body.get("state") != "building":
            return r.body
        time.sleep(0.3)


def _check_upgraded(c, tok, old, stage):
    c.expect(c.req("GET", "/dossiers", token=tok), 200, what=f"stage-{stage} token after upgrade [T9-04]")
    r = c.req("GET", "/changes", token=tok)
    c.check(r.status == 200 and r.body == {"changes": [], "has_more": False}, f"feed after upgrade not empty {r!r} [T9-03, TD-28]")
    for dom, od in old.items():
        nd = c.get(tok, dom).body or {}
        for k in ("dossier_id", "state", "researched_at", "spent_units"):
            c.check(nd.get(k) == od.get(k), f"{dom}: {k} {nd.get(k)!r} != exported {od.get(k)!r} [T9-04]")
        ex = (nd.get("fields") or {}).get("executives") or {}
        c.check(ex.get("value") is None and ex.get("status") == "unknown" and ex.get("candidates") == [],
                f"{dom}: executives after a stage-{stage} upgrade {ex} [T9-11, TD-26]")
        h = c.req("GET", f"/dossiers/{dom}/history", token=tok)
        hf = (h.body or {}).get("fields") or {}
        ra = od.get("researched_at")
        for f in FIELDS:
            ofv = od["fields"][f]
            got = hf.get(f)
            if ofv["value"] is None:
                c.check(got == [], f"{dom} {f}: history {got} for a field without value [T9-02]")
                continue
            if stage == 1:
                want_tf = None
            else:
                sel = (ofv.get("candidates") or [{}])[0]
                want_tf = O.page_true_from(None, sel.get("published_at"))
            ok = (isinstance(got, list) and len(got) == 1 and got[0].get("type") == "initial"
                  and O.same_value(got[0].get("value"), ofv["value"]) and same_instant(got[0].get("learned_at"), ra)
                  and got[0].get("true_from") == want_tf)
            c.check(ok, f"{dom} {f}: history after upgrade {got} != one initial, learned_at {ra}, true_from {want_tf!r} "
                        f"[T9-02, TD-25]")
            nf = nd["fields"][f]
            c.check(same_instant(nf.get("learned_at"), ra) and nf.get("true_from") == want_tf,
                    f"{dom} {f}: field learned_at/true_from {nf.get('learned_at')}/{nf.get('true_from')!r} [T9-10, TD-25]")
            for cand in nf.get("candidates") or []:
                c.check(same_instant(cand.get("learned_at"), cand.get("retrieved_at")),
                        f"{dom} {f}: imported candidate learned_at != retrieved_at [T9-06, TD-25]")
                want_c = None if stage == 1 else O.page_true_from(None, cand.get("published_at"))
                c.check(cand.get("true_from") == want_c, f"{dom} {f}: imported candidate true_from {cand.get('true_from')!r} "
                                                         f"!= {want_c!r} [TD-25]")
        c.check(hf.get("executives") == [], f"{dom}: executives history after upgrade {hf.get('executives')} [T9-11]")
        if ra:
            q = urllib.parse.quote
            r = c.req("GET", f"/dossiers/{dom}?as_of={q(ra)}", token=tok)
            c.check(r.status == 200 and all(O.same_value(r.body["fields"][f]["value"], od["fields"][f]["value"]) for f in FIELDS),
                    f"{dom}: as_of researched_at after upgrade {r!r:.200} [T9-06]")
            r = c.req("GET", f"/dossiers/{dom}?as_of={q(s1.ts_plus(ra, seconds=-1))}", token=tok)
            c.expect(r, 404, "not_found", f"{dom}: as_of before the imported build [T9-06]")
            r = c.req("GET", f"/dossiers/{dom}/values?true_at=2030-01-01&as_of={q(s1.ts_plus(ra, seconds=-1))}", token=tok)
            c.expect(r, 404, "not_found", f"{dom}: values as_of before the imported build [T5-12, T9-06]")
            if stage == 2:
                r = c.req("GET", f"/dossiers/{dom}/values?true_at=2030-01-01", token=tok)
                if c.expect(r, 200, what=f"{dom}: values after a stage-2 upgrade"):
                    for f in FIELDS:
                        cands = [dict(x, true_from=O.page_true_from(None, x.get("published_at")), field=f)
                                 for x in od["fields"][f].get("candidates") or []]
                        held = [x for x in cands if x["true_from"] is not None]   # null-dated versions: either reading
                        alts = [O.select(held)]   # D33: null-dated versions hold on no date
                        g = r.body["fields"][f]
                        c.check(any(O.same_value(g.get("value"), a[0]) for a in alts),
                                f"{dom}: values {f} {g.get('value')!r} after upgrade, versions give {[a[0] for a in alts]} [T9-09, TD-25]")


def _first_build_after_import(c, tok, old_lumen):
    c.req("POST", "/_test/clock", {"now": tsp(days=10)})
    c.mock_reset(0)
    c.imported.add(LUMEN)  # reads during the build still show the imported candidates
    c.expect(c.refresh(tok, LUMEN), 202, what="first refresh after upgrade")
    d, _ = c.wait(tok, LUMEN, timeout=40)
    c.imported.discard(LUMEN)
    if not c.check(d and d["state"] == "ready", f"first build after upgrade {d and d['state']}"):
        return
    r = c.req("GET", "/changes", token=tok).body["changes"]
    lum = [e for e in r if e["domain"] == LUMEN]
    six_changed = [f for f in FIELDS if not O.same_value(d["fields"][f]["value"], old_lumen["fields"][f]["value"])]
    want = six_changed + ["executives"]
    c.check([e["field"] for e in lum] == want and lum and lum[0]["seq"] == 1,
            f"first build after upgrade: feed {[(e['seq'], e['field'], e['type']) for e in lum]}, expected fields {want} from seq 1 "
            f"[T9-03, T9-11, TD-28]")
    ex = [e for e in lum if e["field"] == "executives"]
    c.check(ex and ex[0]["type"] == "change" and ex[0]["from"] is None, f"executives after upgrade: first value is a change {ex} [T9-11]")
    h = c.req("GET", f"/dossiers/{LUMEN}/history", token=tok).body["fields"]["executives"]
    c.check([x.get("type") for x in h] == ["change"], f"executives history after upgrade + build {h} [T9-11]")


# ---------------------------------------------------------------- restart phases

def restart_paths(times):
    q = urllib.parse.quote
    p = [f"/dossiers/{LUMEN}", f"/dossiers/{LUMEN}/history", "/changes?limit=200", "/dossiers?limit=200",
         f"/dossiers/{s1.ZEPHYR}", f"/dossiers/{s1.ZEPHYR}/history"]
    p += [f"/dossiers/{LUMEN}?as_of={q(t)}" for t in times]
    p += [f"/dossiers/{LUMEN}/values?true_at={ta}" for ta in ("2025-06-15", "2026-02-15", "2026-03-05")]
    p += [f"/dossiers/{LUMEN}/values?true_at=2026-02-15&as_of={q(times[1])}"]
    return p


def phase_pre_restart(c):
    c.reset()
    ada = c.login("ada@example.com")
    times = lumen_timeline(c, ada)
    c.mock_reset(0)
    zr = c.req("POST", "/dossiers", {"domain": s1.ZEPHYR}, token=ada, key="restart-z")
    c.wait(ada, s1.ZEPHYR)
    tok, email, uid = c.signup(pw="restart-pw-123", name="Rhea")
    t9 = tsp(days=9)
    c.req("POST", "/_test/clock", {"now": t9})
    state = {"ada": ada, "tok": tok, "email": email, "uid": uid, "times": times, "t9": t9, "zr": zr.body,
             "snap": {p: c.req("GET", p, token=ada).body for p in restart_paths(times)}}
    json.dump(state, open(os.path.join(c.args.state, "restart-state.json"), "w"))


def phase_post_restart(c):
    st = json.load(open(os.path.join(c.args.state, "restart-state.json")))
    ada = st["ada"]
    r = c.req("POST", "/auth/login", {"email": st["email"], "password": "restart-pw-123"})
    c.check(r.status == 200 and r.body.get("user_id") == st["uid"], f"account after restart {r!r} [T10-03]")
    for t in (ada, st["tok"]):
        c.expect(c.req("GET", "/dossiers", token=t), 200, what="token after restart [T10-03]")
    for p, before in st["snap"].items():
        after = c.req("GET", p, token=ada).body
        c.check(after == before, f"{p} differs after restart [T10-04]")
    rp = c.req("POST", "/dossiers", {"domain": s1.ZEPHYR}, token=ada, key="restart-z")
    c.check(rp.status == 200 and rp.body == st["zr"], f"replay after restart {rp!r} [T10-06]")
    c.mock_reset(0)
    r = c.post(ada, s1.NORDLICHT)
    d, _ = c.wait(ada, s1.NORDLICHT, timeout=30)
    c.check(d and same_instant(d.get("researched_at"), st["t9"]), f"clock after restart: build time {d and d.get('researched_at')} "
                                                                  f"!= clock before the stop {st['t9']} [T10-07, TD-27]")
    maxseq = max(e["seq"] for e in st["snap"]["/changes?limit=200"]["changes"])
    c.mock_reset(1)
    c.expect(c.refresh(ada, LUMEN), 202, what="refresh after restart")
    c.wait(ada, LUMEN, timeout=30)
    new = c.req("GET", f"/changes?since={maxseq}", token=ada).body["changes"]
    c.check(new and all(e["seq"] > maxseq for e in new), f"entries after restart {new} must have seq > {maxseq} [T10-05]")
    st["snap2"] = {p: c.req("GET", p, token=ada).body for p in (f"/dossiers/{LUMEN}", f"/dossiers/{LUMEN}/history", "/changes?limit=200")}
    json.dump(st, open(os.path.join(c.args.state, "restart-state.json"), "w"))


def phase_pre_kill(c):
    st = json.load(open(os.path.join(c.args.state, "restart-state.json")))
    ada = st["ada"]
    c.mock_reset(2)
    c.mock_fault("nimble", ["research"], "delay", 8)
    c.mock_fault("nimble", ["extract"], "delay", 3)
    c.expect(c.refresh(ada, LUMEN), 202, what="refresh to be killed")
    time.sleep(1.5)
    g = c.get(ada, LUMEN)
    st["kill_spent"] = (g.body or {}).get("spent_units")
    c.check(g.body and g.body.get("state") == "building", "build not running when the container is killed")
    json.dump(st, open(os.path.join(c.args.state, "restart-state.json"), "w"))


def phase_post_kill(c):
    st = json.load(open(os.path.join(c.args.state, "restart-state.json")))
    ada = st["ada"]
    before = st["snap2"]
    g = c.get(ada, LUMEN).body or {}
    b = before[f"/dossiers/{LUMEN}"]
    c.check(g.get("state") == b["state"] and g.get("fields") == b["fields"] and g.get("researched_at") == b["researched_at"],
            f"after a kill during a build the dossier is not in its last completed state: {g.get('state')} [T10-08, TD-27]")
    c.check(isinstance(g.get("spent_units"), int) and g["spent_units"] >= (st.get("kill_spent") or b["spent_units"])
            and g["spent_units"] <= b["spent_units"] + 80,
            f"spent_units after the kill {g.get('spent_units')} (before stop {st.get('kill_spent')}) [TD-27]")
    for p in (f"/dossiers/{LUMEN}/history", "/changes?limit=200"):
        c.check(c.req("GET", p, token=ada).body == before[p], f"{p} changed by an abandoned build [TD-27]")
    c.mock_reset(2)
    c.req("POST", "/_test/clock", {"now": tsp(days=12)})
    c.expect(c.refresh(ada, LUMEN), 202, what="refresh after the kill")
    d, _ = c.wait(ada, LUMEN, timeout=40)
    c.check(d and d.get("state") == "ready", f"build after restart {d and d.get('state')} [T10-08]")


PHASES = {"pre-restart": phase_pre_restart, "post-restart": phase_post_restart, "pre-kill": phase_pre_kill,
          "post-kill": phase_post_kill}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="main")
    ap.add_argument("--service", default="http://svc:8080")
    ap.add_argument("--service1", default="")
    ap.add_argument("--service2", default="")
    ap.add_argument("--mock", default="http://web:8080")
    ap.add_argument("--admin", default="local-admin")
    ap.add_argument("--corpus", default="/corpus")
    ap.add_argument("--state", default="/logs")
    ap.add_argument("--only", default=os.environ.get("PROBE_ONLY", ""))
    args = ap.parse_args()
    c = Ctx3(args)
    for target in (c.mock, c.svc):
        t = time.monotonic()
        path = "/_mock/health" if target is c.mock else "/health"
        while time.monotonic() - t < 60:
            if c._http(target, "GET", path, timeout=2.0).status == 200:
                break
            time.sleep(0.5)
    if args.phase != "main":
        plan = [(f"R-{args.phase}", "T10-*", f"restart phase {args.phase}", PHASES[args.phase])]
    else:
        import test_appendix_a
        if test_appendix_a.main() != 0:
            return 2
        plan = [("S1-" + p, r, t, f) for p, r, t, f in s1.PROBES] + [("S2-" + p, r, t, f) for p, r, t, f in run2.PROBES2] + PROBES3
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    results = []
    for pid, rows, title, fn in plan:
        if only and pid not in only and args.phase == "main":
            continue
        c.current, c.fail = pid, []
        t = time.monotonic()
        try:
            fn(c)
        except Exception:
            c.fail.append("probe crashed: " + traceback.format_exc(limit=4).replace("\n", " | "))
        results.append((pid, not c.fail))
        print(f"{'PASS' if not c.fail else 'FAIL'} {pid} ({time.monotonic() - t:.0f}s) {title}  [{rows}]", flush=True)
        for m in c.fail[:40]:
            print(f"     - {m}", flush=True)
    if args.phase == "main":
        c.current = "SERVED"
        bad = s1.served_check(c)
        results.append(("SERVED", not bad))
        print(f"{'PASS' if not bad else 'FAIL'} SERVED every excerpt served for its url, from prose ({len(c.citations)}) [R1-05 Q2-04]")
        for m in bad[:40]:
            print("     - " + m)
    results.append(("G", not c.global_viol))
    print(f"{'PASS' if not c.global_viol else 'FAIL'} G global response checks")
    for m in c.global_viol[:40]:
        print("     - " + m)
    if c.notes:
        print("NOTES (non-blocking):")
        for i, n in enumerate(c.notes, 1):
            print(f"  {i}. {n}")
    np_ = sum(1 for _, ok in results if ok)
    print(f"TOTAL: {np_} passed, {len(results) - np_} failed")
    return 0 if np_ == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
