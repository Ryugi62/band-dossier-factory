#!/usr/bin/env python3
"""Verifier black-box probes for dossier stage 4 (API part and restart phases).

  python3 run4.py --phase main|pre-restart|post-restart|pre-kill|post-kill|s3-pre-restart|s3-post-restart \
     --service http://svc:8080 --service1 http://svc1:8080 --service2 http://svc2:8080 --service3 http://svc3:8080 \
     --mock http://web:8080 --admin local-admin --corpus /corpus --state /logs [--only D01]

Phase main re-runs every stage-1, stage-2 and stage-3 API probe with the stage-4 invariants (INV4),
then D01..D03 (origins, corroboration, investors), E01..E03 (batches), F01 (provider failure),
U5 (upgrades from real stage-1/2/3 exports), X1 (stage-4 export/import).
Each probe names the ledger rows (factory/ledger/stage-4.md) it covers. Standard library only.
"""
import argparse
import glob
import json
import os
import sys
import time
import traceback
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PROBES = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROBES, "stage-2"))
sys.path.insert(0, os.path.join(PROBES, "stage-3"))
sys.path.insert(0, HERE)
import run3  # noqa: E402  (imports run2 and the stage-1 probes)
import oracle4 as O4  # noqa: E402

run2, s1, O3 = run3.run2, run3.s1, run3.O
A = s1.A
FIELDS = list(A.FIELDS)
F8 = FIELDS + ["executives", "investors"]
T0 = s1.T0
ORBIT, LATTICE = "orbit-forge.test", "lattice-lineage.test"

# the stage-3 probes see eight fields; stage-2 kinds follow the stage-4 own-page rule (D36);
# the stage-3 /values oracle picks investors by the membership rule (stage-4 Investors)
run3.F7 = F8
run2.expected_kind = O4.page_kind
_select3 = O3.select


def _select4(cands):
    if cands and cands[0].get("field") == "investors":
        value, _, cits, tf, _, _ = O4.derive_investors(cands, run2.rank_key)
        return value, tf, cits
    return _select3(cands)


O3.select = _select4
_norm_members3 = O3.norm_members


def _norm_members4(v):
    # investors values are lists of names (strings); executives values are lists of {title, name}
    if isinstance(v, list) and v and isinstance(v[0], str):
        return [O4.norm(x) for x in v]
    return _norm_members3(v)


O3.norm_members = _norm_members4


def tsp(**kw):
    return s1.ts_plus(T0, **kw)


same_instant = run2.same_instant


class Ctx4(run3.Ctx3):
    def __init__(self, args):
        super().__init__(args)
        self.svc3 = urllib.parse.urlparse(args.service3) if getattr(args, "service3", "") else None
        self.allpages = {}
        for f in glob.glob(os.path.join(args.corpus, "*.json")):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except ValueError:
                continue
            for p in d.get("pages", []) if isinstance(d, dict) else []:
                self.allpages.setdefault(O4.url_key(p["url"]), []).append(p)
        self.window_calls = []

    def req3(self, method, path, body=None, token=None, key=None):
        h = {}
        if token is not None:
            h["Authorization"] = f"Bearer {token}"
        if key is not None:
            h["Idempotency-Key"] = key
        return self._http(self.svc3, method, path, body, h, None, 10.0 if path.startswith("/_test") else 5.0)

    def lookup(self, epoch):
        def f(url):
            for p in self.allpages.get(O4.url_key(url), []):
                if epoch in p.get("epochs", []):
                    return p
            return None
        return f

    # ------------------------------------------------------------ INV4
    def inv(self, d):
        if not isinstance(d, dict):
            self.check(False, f"INV4: dossier not an object: {d!r}")
            return
        dom, ra = d.get("domain"), d.get("researched_at")
        f = d.get("fields")
        if not isinstance(f, dict) or sorted(f) != sorted(F8):
            self.check(False, f"INV4 {dom}: fields keys {list(f) if isinstance(f, dict) else f!r} != eight [V1-01]")
            return
        # the original stage-2 class (browser4 later rebinds run2.Ctx2 to Ctx4)
        run3.Ctx3.__bases__[0].inv(self, dict(d, fields={k: f[k] for k in FIELDS}))
        for name in FIELDS:
            for m in self._inv_times(name, f[name], ra):
                self.check(False, f"INV4 {dom}: {name}: {m}")
        for m in self._inv_exec(dom, f["executives"], ra):
            self.check(False, f"INV4 {dom}: executives: {m}")
        for m in self._inv_investors(dom, f["investors"], ra):
            self.check(False, f"INV4 {dom}: investors: {m}")
        for name in F8:
            for m in self._inv_origins(name, f[name]):
                self.check(False, f"INV4 {dom}: {name}: {m}")

    def _inv_origins(self, name, fv):
        p = []
        cands = fv.get("candidates") or []
        for i, c in enumerate(cands):
            if not isinstance(c.get("origin"), str) or not c["origin"]:
                p.append(f"candidate {i} origin {c.get('origin')!r} [O3-01]")
        if p:
            return p
        for k in ("origins", "corroborated", "corroborated_since"):
            if k not in fv:
                return [f"lacks {k} [O4-01]"]
        v = fv.get("value")
        if v is None:
            if fv["origins"] != [] or fv["corroborated"] is not False or fv["corroborated_since"] is not None:
                p.append(f"unknown field: origins {fv['origins']}, corroborated {fv['corroborated']}, since "
                         f"{fv['corroborated_since']} [O4-02, O4-05, O4-07]")
            return p
        if name == "executives":
            groups = [[c for c in cands if c.get("title") == m.get("title") and O4.norm(c.get("value")) == O4.norm(m.get("name"))]
                      for m in v]
        elif name == "investors":
            groups = [[c for c in cands if O4.norm(c.get("value")) == O4.norm(n)] for n in v]
        else:
            groups = [[c for c in cands if O4.norm(c.get("value")) == O4.norm(v)]]
        want = sorted({c["origin"] for g in groups for c in g})
        if fv["origins"] != want:
            p.append(f"origins {fv['origins']} != {want} (distinct origins of the selected value's candidates, sorted) [O4-02, O4-08]")
        corr = all(len({c["origin"] for c in g}) >= 2 for g in groups) if name in ("executives", "investors") else len(want) >= 2
        if fv["corroborated"] is not corr:
            p.append(f"corroborated {fv['corroborated']} != {corr} [O4-03, O4-09]")
        cs = fv["corroborated_since"]
        if cs is not None and not (isinstance(cs, str) and O3.TS_RE.match(cs)):
            p.append(f"corroborated_since {cs!r} not RFC 3339 [O4-04]")
        if corr and cs is None:
            p.append("corroborated now, yet corroborated_since is null (current origins are standing origins) [O4-04, O4-10]")
        return p

    def _inv_investors(self, dom, fv, ra):
        p = []
        v, st, cits, cands = fv.get("value"), fv.get("status"), fv.get("citations"), fv.get("candidates")
        if not isinstance(cands, list) or not isinstance(cits, list):
            return ["candidates/citations not lists [V1-06]"]
        for i, c in enumerate(cands):
            if not isinstance(c, dict) or not isinstance(c.get("value"), str) or "title" in c:
                p.append(f"candidate {i} {c!r} [V1-06]")
                continue
            for k in ("url", "excerpt", "provider", "kind", "published_at", "retrieved_at", "selected", "true_from", "learned_at", "origin"):
                if k not in c:
                    p.append(f"candidate {i} lacks {k} [V1-06]")
            if isinstance(dom, str) and O4.norm(c["value"]) not in O4.investor_names(c.get("excerpt") or "", dom):
                p.append(f"candidate {i} {c['value']!r}: excerpt {c.get('excerpt')!r} does not support it [V1-03, V1-04, R1-05]")
            if c.get("kind") is None and dom not in self.imported:
                p.append(f"candidate {i} kind null")
            with self.lock:
                self.citations.setdefault((c.get("url"), c.get("excerpt"), c.get("provider")), (dom, "investors", c["value"], self.current))
        if p:
            return p
        keys = [run2.rank_key(c) for c in cands]
        if keys != sorted(keys):
            p.append("candidates not in selection-rule rank order [V1-12]")
        if len(set(keys)) != len(keys):
            p.append("duplicate candidate (url, provider, name) [QD-19]")
        value, status, exp_cits, tf, _, members = O4.derive_investors(cands, run2.rank_key)
        if (v is None) != (value is None) or [O4.norm(x) for x in (v or [])] != (value or []):
            p.append(f"value {v!r} != members sorted by code point {value!r} [V1-07, V1-08]")
        if st != status:
            p.append(f"status {st!r}, rule gives {status} (known exactly when a member exists; never contested) [V1-09]")
        for i, c in enumerate(cands):
            if c.get("selected") is not (O4.norm(c["value"]) in members):
                p.append(f"candidate {i} {c['value']!r} selected {c.get('selected')} but member={O4.norm(c['value']) in members} [V1-11]")
        got_cits = [{"url": c.get("url"), "excerpt": c.get("excerpt"), "provider": c.get("provider")} for c in cits]
        if got_cits != exp_cits:
            p.append(f"citations {got_cits} != per member (value order) candidates in rank order {exp_cits} [V1-13]")
        if fv.get("true_from") != tf:
            p.append(f"true_from {fv.get('true_from')!r} != latest member true_from {tf!r} [V1-14]")
        if v is None and fv.get("learned_at") is not None:
            p.append("unknown investors with learned_at [T1-09]")
        return p

    # ------------------------------------------------------------ EV4
    def ev(self, d, epoch, research_ok=True):
        super().ev(d, epoch, research_ok)
        dom = d.get("domain")
        corp = self.corpus.get(dom)
        if corp is None:
            return
        lk = self.lookup(epoch)
        claims = (corp.get("research", {}).get("nimble", {}) or {}).get(str(epoch), []) if research_ok else []
        cited = {r.get("url") for r in claims}
        pages = {p["url"]: p for p in corp["pages"] if epoch in p["epochs"] and (p.get("searchable", True) or p["url"] in cited)}
        fields = d.get("fields") or {}
        gathered = set()
        for fname in F8:
            for c in (fields.get(fname) or {}).get("candidates") or []:
                page = pages.get(c.get("url")) or lk(c.get("url") or "")
                if page is None:
                    continue
                gathered.add(page["url"])
                want_o = O4.origin(page, dom, lk)
                self.check(c.get("origin") == want_o, f"EV4 {dom} e{epoch}: {fname} candidate {c.get('url')} origin "
                                                      f"{c.get('origin')!r}, lineage gives {want_o!r} [O3-01..O3-06]")
                want_k = O4.page_kind(page, dom)
                self.check(c.get("kind") == want_k, f"EV4 {dom} e{epoch}: {fname} candidate {c.get('url')} kind "
                                                    f"{c.get('kind')!r}, own-page rule gives {want_k!r} [O2-01, O2-02]")
        inv = (fields.get("investors") or {}).get("candidates") or []
        for url, p in pages.items():
            for name, sent in O4.page_investors(p["text"], dom).items():
                hit = [c for c in inv if c.get("url") == url and O4.norm(c.get("value")) == name]
                if self.check(hit, f"EV4 {dom} e{epoch}: missing investors candidate {name!r} from {url} ({sent!r}) [V1-05]"):
                    self.check(A.collapse_ws(hit[0].get("excerpt") or "") == sent,
                               f"EV4 {dom}: investors excerpt is not the first supporting sentence [QD-19]")
        if self.renders is not None:
            for c in inv:
                texts = self.renders.get(c.get("url"), [])
                self.check(any(s1.excerpt_in(c.get("excerpt") or "", A.split_prose(t)[1]) for t in texts),
                           f"D13 {dom}: investors candidate not in a rendered extract of {c.get('url')} [QD-13]")
        if self.window_calls:
            fetched = set()
            for call in self.window_calls:
                if call.get("method") == "extract":
                    fetched |= {O4.url_key(u) for u in call.get("urls") or []}
            for url in gathered:
                for need in O4.needed_originals(pages.get(url) or lk(url), lk):
                    self.check(O4.url_key(need) in fetched, f"{dom}: original {need} (rule 2 for {url}) not obtained by the build "
                                                            f"[O3-07]")

    def window(self, domain, spent_before=0, spent_after=None, builds=1, what=""):
        calls, cost = super().window(domain, spent_before, spent_after, builds, what)
        self.window_calls = calls
        return calls, cost

    def mock_reset(self, epoch=0, quiet=True):
        super().mock_reset(epoch, quiet)
        self.window_calls = []


# ---------------------------------------------------------------- oracles

def corr_oracle(c, dom, field="hq_city"):
    """standing origins / corroborated_since over the recorded builds, for one plain field."""
    since, standing, cur = None, set(), None
    for b in [b for b in c.builds.get(dom, []) if b["ok"]]:
        fv = b["snapshot"]["fields"].get(field) or {}
        v = fv.get("value")
        if not O3.same_value(v, cur):
            since, standing, cur = None, set(), v
        if v is not None:
            standing |= {x.get("origin") for x in fv.get("candidates") or [] if O4.norm(x["value"]) == O4.norm(v)}
            if since is None and len(standing) >= 2:
                since = b["time"]
    return since


def history4(c, tok, dom):
    """History/feed types for all eight fields over the recorded builds (investors typed by name)."""
    bs = [b for b in c.builds.get(dom, []) if b["ok"]]
    exp, feed, prev, first = {f: [] for f in F8}, [], {}, True
    for b in bs:
        snap = b["snapshot"]["fields"]
        for f in F8:
            new, ntf = snap[f]["value"], snap[f]["true_from"]
            old, otf, omt = prev.get(f, (None, None, None))
            if first:
                if new is not None:
                    exp[f].append("initial")
            elif not O3.same_value(old, new):
                if f == "investors":
                    typ = O4.investors_change_type(old, otf, new, snap[f]["candidates"])
                elif f == "executives":
                    typ = O3.change_type(f, old, new, None, None, omt, run3._member_tf(snap[f]))
                else:
                    typ = O3.change_type(f, old, new, otf, ntf)
                exp[f].append(typ)
                feed.append((f, typ))
            prev[f] = (new, ntf, run3._member_tf(snap[f]) if f == "executives" else None)
        first = False
    h = c.req("GET", f"/dossiers/{dom}/history", token=tok)
    if c.expect(h, 200, what="history"):
        hf = h.body.get("fields") or {}
        c.check(sorted(hf) == sorted(F8), f"history fields {sorted(hf)} (eight) [V1-01]")
        for f in F8:
            c.check([e.get("type") for e in hf.get(f) or []] == exp[f], f"history {dom} {f}: {[e.get('type') for e in hf.get(f) or []]} "
                                                                         f"!= {exp[f]} [V1-16, T3-*]")
    return feed


def check_fields(c, d, exp, what):
    for f, want in exp.items():
        fv = (d.get("fields") or {}).get(f) or {}
        for k, v in want.items():
            got = fv.get(k)
            ok = same_instant(got, v) if k == "corroborated_since" and v and got else (O3.norm_members(got) == O3.norm_members(v))
            c.check(ok, f"{what}: {f}.{k} = {got!r}, expected {v!r}")


# ---------------------------------------------------------------- probes

PROBES4 = []


def probe(pid, rows, title):
    def deco(fn):
        PROBES4.append((pid, rows, title, fn))
        return fn
    return deco


ORBIT_E0 = {
    "hq_city": {"value": "Lyon", "origins": ["dailyorbit.test", "orbit-forge.test"], "corroborated": True, "corroborated_since": T0},
    "ceo": {"value": "Lena Hart", "origins": ["orbit-forge.test"], "corroborated": False, "corroborated_since": None},
    "founded_year": {"value": 2016, "origins": ["wire.test"], "corroborated": False, "corroborated_since": None},
    "funding_total": {"value": 20000000, "origins": ["dealwire.test", "gone.test"], "corroborated": True, "corroborated_since": T0},
    "executives": {"value": [{"title": "cfo", "name": "Mia Kerr"}], "origins": ["orbit-forge.test"], "corroborated": False},
    "investors": {"value": ["General Atlantic", "Northwind Ventures"], "status": "known", "true_from": "2025-06-01",
                  "origins": ["dealwire.test", "gone.test", "orbit-forge.test"], "corroborated": False, "corroborated_since": None},
}
LATTICE_E0 = {
    "hq_city": {"value": "Ghent", "origins": ["lattice-lineage.test"], "corroborated": False},
    "headcount_range": {"value": "51-200", "origins": ["chain-e.test", "final-origin.test"], "corroborated": True,
                        "corroborated_since": T0},
    "legal_name": {"value": "Lattice Lineage S.A.S.", "origins": ["oddlines.test"]},
    "investors": {"value": ["Cobalt Equity"], "status": "known", "origins": ["loop-a.test", "loop-b.test"], "corroborated": True,
                  "corroborated_since": T0},
}


@probe("D01", "O1-* O2-* O3-* O4-* V1-* TD-36 TD-37 TD-39", "orbit-forge.test: kinds, origins, corroboration, investors")
def d01(c):
    c.reset()
    ada = c.login("ada@example.com")
    d = c.build(ada, ORBIT, 0, True, "D01")
    if d:
        check_fields(c, d, ORBIT_E0, "orbit e0")
        red = [x for x in d["fields"]["investors"]["candidates"] if x["value"] == "Redwood Partners"]
        c.check(red and red[0]["kind"] == "aggregator" and red[0]["origin"] == ORBIT and not red[0]["selected"],
                f"lookalike candidate {red} must be aggregator, origin the company domain, not a member [O2-03, O3-04, V1-10]")
        ember = [x for x in d["fields"]["investors"]["candidates"] if x["value"] == "Ember Fund"]
        c.check(len(ember) == 2 and not any(x["selected"] for x in ember),
                "two syndicated copies of one origin do not make Ember Fund a member [O3-08, V1-10]")
        log_urls = {O4.url_key(u) for x in c.window_calls if x.get("method") == "extract" for u in x.get("urls") or []}
        c.check(O4.url_key("https://gone.test/original") in log_urls, "unreachable original not requested from a provider [O3-07]")


@probe("D02", "O1-01..O1-03 O3-02 O3-05 O3-06 O3-07 V1-*", "lattice-lineage.test: canonical chains (3 hops / 4th hop), cycle, "
       "invalid lineage lines, lookalike-free own rule")
def d02(c):
    c.reset()
    ada = c.login("ada@example.com")
    d = c.build(ada, LATTICE, 0, True, "D02")
    if d:
        check_fields(c, d, LATTICE_E0, "lattice e0")


@probe("D03", "O4-04 O4-06 O4-10 V1-16 V1-17 T3-* T4-01 TD-38", "orbit timeline: standing origins, corroborated_since, "
       "investors typed by name, as_of carries the new keys")
def d03(c):
    c.reset()
    ada = c.login("ada@example.com")
    times = [T0, tsp(days=1), tsp(days=2)]
    for e, t in enumerate(times):
        if e:
            c.req("POST", "/_test/clock", {"now": t})
        d = c.build(ada, ORBIT, e, e == 0, f"D03 e{e}")
        if not d:
            return
        hq, ceo = d["fields"]["hq_city"], d["fields"]["ceo"]
        if e == 1:
            c.check(hq["corroborated"] is False and same_instant(hq["corroborated_since"], T0),
                    f"e1 hq: dailyorbit page gone, yet its origin still stands: corroborated false, since T0; got "
                    f"{hq['corroborated']}/{hq['corroborated_since']} [O4-04, O4-06]")
            c.check(ceo["corroborated"] is True and same_instant(ceo["corroborated_since"], times[1]),
                    f"e1 ceo: second origin ceowire.test -> corroborated since T1; got {ceo['corroborated_since']} [O4-04]")
        if e == 2:
            c.check(hq["value"] == "Grenoble" and hq["corroborated_since"] is None,
                    f"e2 hq: a new selected value starts with no standing origins; got {hq['value']}/{hq['corroborated_since']} [O4-06]")
            inv = d["fields"]["investors"]
            c.check(inv["value"] == ["Atlas Capital", "General Atlantic", "Northwind Ventures"],
                    f"e2 investors {inv['value']} [V1-07]")
        for f in ("hq_city", "ceo", "funding_total"):
            want = corr_oracle(c, ORBIT, f)
            got = d["fields"][f]["corroborated_since"]
            c.check((want is None and got is None) or (want and got and same_instant(want, got)),
                    f"e{e} {f}: corroborated_since {got}, standing-origin oracle gives {want} [O4-04, TD-38]")
    feed = history4(c, ada, ORBIT)
    c.check(feed == [("hq_city", "change"), ("investors", "correction")],
            f"orbit feed types {feed}: hq change, investors correction (Atlas Capital dated 2023-01-01 <= 2025-06-01) [V1-16, V1-17]")
    got = [(e["field"], e["type"]) for e in c.req("GET", "/changes", token=ada).body["changes"]]
    c.check(got == feed, f"GET /changes {got} != {feed} (investors numbered last) [V1-02, T7-03]")
    for t in times:
        r = c.req("GET", f"/dossiers/{ORBIT}?as_of=" + urllib.parse.quote(t), token=ada)
        snap = [b for b in c.builds[ORBIT] if same_instant(b["time"], t)][-1]["snapshot"]
        if c.expect(r, 200, what=f"as_of {t}"):
            for f in F8:
                for k in ("origins", "corroborated", "corroborated_since"):
                    c.check(r.body["fields"][f].get(k) == snap["fields"][f].get(k),
                            f"as_of {t}: {f}.{k} {r.body['fields'][f].get(k)!r} != snapshot {snap['fields'][f].get(k)!r} [TD-38]")
    r = c.req("GET", f"/dossiers/{ORBIT}/values?true_at=2025-12-01", token=ada)
    if c.expect(r, 200, what="values"):
        c.check(sorted(r.body["fields"]) == sorted(F8), f"values fields {sorted(r.body['fields'])} [V1-15]")


# ---------------------------------------------------------------- batches

def post_batch(c, tok, domains, budget, key=None, raw=None):
    body = None if raw is not None else {"domains": domains, "budget_units": budget}
    return c.req("POST", "/batches", body, token=tok, key=key or s1.uid(), raw=raw)


def wait_batch(c, tok, bid, timeout=90):
    t = time.monotonic()
    last = None
    while time.monotonic() - t < timeout:
        r = c.req("GET", f"/batches/{bid}", token=tok)
        if r.status == 200:
            last = r.body
            c.check(last["spent_units"] <= last["budget_units"], f"batch {bid} spent {last['spent_units']} > budget [B1-09, I5-01]")
            if last.get("state") == "done":
                return last
        time.sleep(0.4)
    return last


def batch_shape(c, b, domains, budget, what):
    ok = (isinstance(b, dict) and isinstance(b.get("batch_id"), str) and 0 < len(b["batch_id"]) <= 64
          and b.get("state") in ("running", "done") and b.get("budget_units") == budget and isinstance(b.get("spent_units"), int)
          and [x.get("domain") for x in b.get("dossiers", [])] == domains
          and all(x.get("state") in ("building", "ready", "failed") for x in b.get("dossiers", [])))
    c.check(ok, f"{what}: batch body {b} [B1-04, B1-05, TD-40]")


@probe("E01", "B1-01..B1-08 B2-01 B2-02 B1-13 TD-40", "batches: validation, shape, ownership, idempotency, existing dossiers")
def e01(c):
    c.reset()
    c.mock_reset(0)
    ada, bob = c.login("ada@example.com"), c.login("bob@example.com")
    for body, why in [({"budget_units": 10}, "domains missing"), ({"domains": [], "budget_units": 10}, "domains empty"),
                      ({"domains": [f"d{i}.test" for i in range(51)], "budget_units": 10}, "51 domains"),
                      ({"domains": ["ok.test", "not a domain"], "budget_units": 10}, "invalid entry"),
                      ({"domains": ["Acme.test", "www.acme.test"], "budget_units": 10}, "duplicate after normalisation"),
                      ({"domains": ["a1.test"]}, "budget missing"), ({"domains": ["a1.test"], "budget_units": 0}, "budget 0"),
                      ({"domains": ["a1.test"], "budget_units": 100001}, "budget 100001"),
                      ({"domains": ["a1.test"], "budget_units": "10"}, "budget a string"),
                      ({"domains": ["a1.test"], "budget_units": True}, "budget true"),
                      ({"domains": ["a1.test"], "budget_units": 1.5}, "budget 1.5")]:
        c.expect(c.req("POST", "/batches", body, token=ada, key=s1.uid()), 422, "validation_failed", f"POST /batches {why} [B1-06..B1-08]")
    c.expect(c.req("POST", "/batches", {"domains": ["a1.test"], "budget_units": 10}, key="k"), 401, "unauthenticated", "no token")
    c.expect(c.req("POST", "/batches", {"domains": ["a1.test"], "budget_units": 10}, token=ada), 400, "missing_idempotency_key",
             "no key [B1-02]")
    c.expect(c.req("GET", "/batches/nope"), 401, "unauthenticated", "GET batch without token")
    c.expect(c.req("GET", "/batches/nope", token=ada), 404, "not_found", "unknown batch [B2-02]")
    c.post(ada, s1.ZEPHYR)
    c.wait(ada, s1.ZEPHYR)
    c.mock_reset(0)
    key = "E01-" + s1.uid()
    r = post_batch(c, ada, ["  WWW.Zephyr-Quantum.TEST ", s1.NORDLICHT], 100, key)
    if not c.expect(r, 202, what="POST /batches [B1-04]"):
        return
    batch_shape(c, r.body, [s1.ZEPHYR, s1.NORDLICHT], 100, "202")
    c.check(r.body["dossiers"][0]["state"] == "ready", "existing dossier listed with its own state [B1-10]")
    bid = r.body["batch_id"]
    rp = post_batch(c, ada, ["  WWW.Zephyr-Quantum.TEST ", s1.NORDLICHT], 100, key)
    c.check(rp.status == 200 and rp.body == r.body, f"batch replay {rp!r} [B1-03, TD-40]")
    c.expect(post_batch(c, ada, [s1.NORDLICHT], 100, key), 409, "idempotency_key_reuse", "same key other body [B1-03]")
    c.expect(c.req("GET", f"/batches/{bid}", token=bob), 404, "not_found", "another user's batch [B2-01]")
    b = wait_batch(c, ada, bid)
    if c.check(b and b["state"] == "done", f"batch never done {b}"):
        batch_shape(c, b, [s1.ZEPHYR, s1.NORDLICHT], 100, "GET")
        calls = c.mock_log()
        research = [x for x in calls if x.get("method") == "research"]
        c.check(len(research) == 1 and s1.NORDLICHT in research[0].get("query", ""), "existing dossier researched by the batch [B1-10]")
        c.check(b["spent_units"] == sum(x.get("cost") or 0 for x in calls), f"batch spent {b['spent_units']} != call log "
                f"{sum(x.get('cost') or 0 for x in calls)} [B1-09]")
        z = c.get(ada, s1.ZEPHYR).body
        n = c.get(ada, s1.NORDLICHT).body
        c.check(n["spent_units"] == b["spent_units"], "nordlicht's build cost counts in its dossier [B1-11]")
    k2 = "E01b-" + s1.uid()
    c.expect(post_batch(c, ada, ["bad domain"], 10, k2), 422, "validation_failed", "4xx first")
    r = post_batch(c, ada, [s1.ZEPHYR], 10, k2)
    c.check(r.status == 202 and r.body.get("state") == "done" and r.body.get("spent_units") == 0,
            f"key after a 4xx is a first use; a batch of existing dossiers is done and costs nothing: {r!r} [B1-10, TD-40]")


@probe("E02", "B1-09 B1-11 B1-12 I5-01 TD-41", "batch budget exhaustion: never above budget, each build <= 80, mock log as the oracle")
def e02(c):
    for budget, doms in ((30, ["halvorsen-robotics.test", "quillmate.test", "tidemark-energy.test"]),
                         (75, ["windrush-bakery.test", "corvid-security.test", "mosaic-freight.test"]),
                         (1, ["ostrava-mobility.test", "pemberton-analytics.test"])):
        c.reset()
        c.mock_reset(0)
        ada = c.login("ada@example.com")
        r = post_batch(c, ada, doms, budget)
        if not c.expect(r, 202, what=f"batch budget {budget}"):
            continue
        b = wait_batch(c, ada, r.body["batch_id"])
        if not c.check(b and b["state"] == "done", f"budget {budget}: batch not done {b}"):
            continue
        calls = c.mock_log()
        total = sum(x.get("cost") or 0 for x in calls)
        c.check(total <= budget, f"budget {budget}: provider calls cost {total} [B1-09, I5-01]")
        c.check(b["spent_units"] == total, f"budget {budget}: batch spent {b['spent_units']} != billed {total} [B1-09]")
        spent = 0
        for dom in doms:
            d = c.get(ada, dom).body
            c.check(d["state"] in ("ready", "failed") and d["spent_units"] <= 80, f"{dom}: {d['state']} spent {d['spent_units']} [B1-11]")
            c.check(d["state"] == "ready", f"{dom}: a build stopped by the budget ends ready [B1-12, TD-41]")
            spent += d["spent_units"]
        c.check(spent == b["spent_units"], f"budget {budget}: dossiers spent {spent} != batch {b['spent_units']} [B1-11]")


@probe("E03", "B1-03 B1-13 R8-18 T8-01 TD-41", "burst of identical and overlapping batches; refresh during a batch build")
def e03(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    c.mock_fault("nimble", ["research"], "delay", 2)
    key = "E03-" + s1.uid()
    rs = s1.par(8, lambda i: post_batch(c, ada, [s1.ZEPHYR, ORBIT], 160, key))
    st = sorted(x.status for x in rs)
    c.check(st.count(202) == 1 and st.count(200) == 7, f"8 identical batch posts: {st} [B1-03]")
    c.check(len({json.dumps(x.body, sort_keys=True) for x in rs}) == 1, "identical batch posts returned different bodies [B1-03]")
    rr = c.refresh(ada, ORBIT)
    c.check(rr.status == 202, f"refresh during the batch build {rr!r}")
    rs2 = s1.par(4, lambda i: post_batch(c, ada, [ORBIT, LATTICE], 100))
    bids = [x.body["batch_id"] for x in rs + rs2 if x.status in (200, 202)]
    for bid in set(bids):
        wait_batch(c, ada, bid, 120)
    for dom in (s1.ZEPHYR, ORBIT, LATTICE):
        c.wait(ada, dom, timeout=60)
    research = [x for x in c.mock_log() if x.get("method") == "research"]
    per = {d: sum(1 for x in research if d in (x.get("query") or "")) for d in (s1.ZEPHYR, ORBIT, LATTICE)}
    c.check(all(v == 1 for v in per.values()), f"research runs per domain {per}: one build each despite overlapping batches and a "
                                               f"refresh [B1-13, R8-18, TD-41]")
    c.mock_reset(0)


@probe("F01", "P1-01..P1-04 TD-42", "provider failure: other providers failing, research failing, every call failing (time bound)")
def f01(c):
    c.reset()
    ada = c.login("ada@example.com")
    c.mock_reset(0)
    for prov in ("tavily", "kernel", "browserbase"):
        c.mock_fault(prov, ["search", "extract", "session", "browse"], "error")
    t = time.monotonic()
    c.expect(c.post(ada, ORBIT), 202, what="POST with other providers failing")
    d, el = c.wait(ada, ORBIT, timeout=30, start=t)
    if c.check(d and d["state"] == "ready", f"other providers failing: {d and d['state']} [P1-01]"):
        c.window(ORBIT, 0, d["spent_units"], 1, "F01")
        c.ev(d, 0)
    for mode in ("error", "rate_limit"):
        c.mock_reset(0)
        c.mock_fault("nimble", ["research"], mode)
        t = time.monotonic()
        c.expect(c.refresh(ada, ORBIT), 202, what=f"refresh with research {mode}")
        d, el = c.wait(ada, ORBIT, timeout=60, start=t)
        if c.check(d and d["state"] == "ready", f"research {mode}: {d and d['state']} [P1-02]"):
            c.ev(d, 0, research_ok=mode != "error")
    c.mock_reset(0)
    c.mock_fault("nimble", ["search", "extract", "research"], "error")
    t = time.monotonic()
    c.expect(c.post(ada, LATTICE), 202, what="POST with every nimble call failing")
    d, el = c.wait(ada, LATTICE, timeout=40, start=t)
    c.check(d and d["state"] == "failed", f"every call failing: {d and d['state']} [P1-03]")
    c.check(el <= 10.5, f"every call failing (5xx answered at once): build took {el:.1f}s > 10 s [P1-03, R8-09]")
    c.check(d and d["spent_units"] == 0, "refused calls cost nothing [P1-04]")
    c.mock_reset(0)


@probe("U5", "U4-01..U4-05 TD-44", "upgrades from real stage-1, stage-2 and stage-3 exports")
def u5(c):
    for label, svc_req in (("stage-1", c.req1 if c.svc1 else None), ("stage-2", c.req2 if c.svc2 else None),
                           ("stage-3", c.req3 if c.svc3 else None)):
        if svc_req is None:
            c.check(False, f"no {label} service")
            continue
        c.mock_reset(0)
        svc_req("POST", "/_test/reset", s1.FIXTURE)
        tok = svc_req("POST", "/auth/login", {"email": "ada@example.com", "password": s1.PW}).body["token"]
        lost = svc_req("POST", "/dossiers", {"domain": ORBIT}, token=tok, key=f"u5-{label}")
        run3._wait_svc(svc_req, tok, ORBIT)
        if label == "stage-3":
            svc_req("POST", "/_test/clock", {"now": tsp(days=1)})
            c.mock_reset(1)
            svc_req("POST", f"/dossiers/{ORBIT}/refresh", token=tok, key="u5-r")
            run3._wait_svc(svc_req, tok, ORBIT)
        old = svc_req("GET", f"/dossiers/{ORBIT}", token=tok).body
        old_hist = svc_req("GET", f"/dossiers/{ORBIT}/history", token=tok).body if label == "stage-3" else None
        old_feed = svc_req("GET", "/changes", token=tok).body if label == "stage-3" else None
        e = svc_req("GET", "/_test/export").body
        c.reset()
        c.mock_reset(0)
        c.imported.add(ORBIT)
        if not c.expect(c.req("POST", "/_test/import", e), 204, what=f"import of a {label} export [U4-01]"):
            continue
        d = c.get(tok, ORBIT).body or {}
        inv = (d.get("fields") or {}).get("investors") or {}
        c.check(inv.get("value") is None and inv.get("status") == "unknown" and inv.get("candidates") == [],
                f"{label}: investors after upgrade {inv} [U4-04]")
        for f in FIELDS:
            for x in d["fields"][f].get("candidates") or []:
                if True:
                    c.check(x.get("origin") == O4.url_host(x["url"]), f"{label}: imported candidate without origin takes its URL host: "
                                                                     f"{x.get('url')} -> {x.get('origin')} [U4-03, O4-11]")
            fv, ofv = d["fields"][f], old["fields"][f]
            c.check(O3.same_value(fv["value"], ofv["value"]), f"{label}: {f} value changed by the upgrade [U4-01]")
            if fv["value"] is not None:
                n = len(fv.get("origins") or [])
                ok = (n >= 2) <= (fv.get("corroborated_since") is not None) if label == "stage-3" else \
                    (n >= 2) == (fv.get("corroborated_since") is not None)
                c.check(ok,
                        f"{label}: {f} origins {fv.get('origins')} vs corroborated_since {fv.get('corroborated_since')} (imported candidates "
                        f"count as gathered at the imported build) [O4-05, TD-44]")
        h = c.req("GET", f"/dossiers/{ORBIT}/history", token=tok).body["fields"]
        c.check(h.get("investors") == [], f"{label}: investors history after upgrade {h.get('investors')} [U4-04]")
        if label == "stage-3":
            for f in run3.FIELDS + ["executives"]:
                c.check(h.get(f) == old_hist["fields"].get(f), f"stage-3 history of {f} changed by the upgrade [U4-02]")
            c.check(c.req("GET", "/changes", token=tok).body == old_feed, "stage-3 feed changed by the upgrade [U4-02]")
            r = c.req("GET", f"/dossiers/{ORBIT}?as_of=" + urllib.parse.quote(T0), token=tok)
            c.check(r.status == 200 and "origins" in r.body["fields"]["hq_city"], f"as_of from a kept stage-3 build {r!r:.200} [U4-02]")
        rp = c.req("POST", "/dossiers", {"domain": ORBIT}, token=tok, key=f"u5-{label}")
        c.check(rp.status == 200 and rp.body == lost.body, f"{label}: completed idempotent response after upgrade [U4-01]")
        c.req("POST", "/_test/clock", {"now": tsp(days=5)})
        c.mock_reset(0)
        c.expect(c.refresh(tok, ORBIT), 202, what=f"{label}: first refresh after upgrade")
        d2, _ = c.wait(tok, ORBIT, timeout=40)
        c.imported.discard(ORBIT)
        feed = c.req("GET", "/changes?limit=200", token=tok).body["changes"]
        invs = [x for x in feed if x["field"] == "investors"]
        c.check(len(invs) == 1 and invs[0]["type"] == "change" and invs[0]["from"] is None,
                f"{label}: first build after upgrade adds an investors change {invs} [U4-05]")


@probe("X1", "QX4-* TD-44", "stage-4 export/import round trip: batches, origins, standing origins, investors, feed")
def x1(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    r = post_batch(c, ada, [ORBIT, LATTICE], 200)
    if not c.expect(r, 202, what="batch"):
        return
    bid = r.body["batch_id"]
    wait_batch(c, ada, bid)
    c.req("POST", "/_test/clock", {"now": tsp(days=1)})
    c.mock_reset(1)
    c.refresh(ada, ORBIT)
    c.wait(ada, ORBIT, timeout=40)
    q = urllib.parse.quote
    paths = [f"/batches/{bid}", f"/dossiers/{ORBIT}", f"/dossiers/{LATTICE}", f"/dossiers/{ORBIT}/history", "/changes?limit=200",
             f"/dossiers/{ORBIT}?as_of={q(T0)}", f"/dossiers/{ORBIT}/values?true_at=2025-12-01&as_of={q(tsp(days=1))}"]
    before = {p: c.req("GET", p, token=ada).body for p in paths}
    x = c.req("GET", "/_test/export")
    if not c.expect(x, 200, what="export"):
        return
    c.check(x.body.get("track") == "dossier" and x.body.get("format_version") == 1, "export envelope [TD-44]")
    c.reset()
    c.mock_reset(0)
    c.expect(c.req("POST", "/_test/import", x.body), 204, what="stage-4 import")
    for p in paths:
        c.check(c.req("GET", p, token=ada).body == before[p], f"{p} differs after a stage-4 export/import [QX4-*]")


# ---------------------------------------------------------------- restart phases (builds and a batch running)

def phase_pre_kill(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    c.mock_fault("nimble", ["research"], "delay", 8)
    c.mock_fault("nimble", ["extract"], "delay", 2)
    r = post_batch(c, ada, [ORBIT, LATTICE, "halvorsen-robotics.test"], 120)
    c.expect(r, 202, what="batch to be killed")
    time.sleep(2.5)
    st = {"ada": ada, "batch": r.body, "doms": [ORBIT, LATTICE, "halvorsen-robotics.test"]}
    json.dump(st, open(os.path.join(c.args.state, "restart4.json"), "w"))


def phase_post_kill(c):
    st = json.load(open(os.path.join(c.args.state, "restart4.json")))
    ada, bid = st["ada"], st["batch"]["batch_id"]
    t0 = time.monotonic()   # run4 main() returns here only after /health answered 200
    while time.monotonic() - t0 < 10.5:
        ds = [c.get(ada, d).body for d in st["doms"]]
        b = c.req("GET", f"/batches/{bid}", token=ada).body
        if all(d and d["state"] != "building" for d in ds) and b and b.get("state") == "done":
            break
        time.sleep(0.3)
    ds = [c.get(ada, d).body for d in st["doms"]]
    b = c.req("GET", f"/batches/{bid}", token=ada).body
    c.check(all(d and d["state"] in ("ready", "failed") for d in ds), f"builds still building 10 s after health: "
                                                                      f"{[d and d['state'] for d in ds]} [R4-01]")
    c.check(b and b.get("state") == "done", f"batch after restart {b and b.get('state')} [R4-01, B2-03]")
    calls = c.mock_log()
    billed = sum(x.get("cost") or 0 for x in calls)
    if b:
        c.check(billed <= b["spent_units"] <= b["budget_units"], f"batch spent {b['spent_units']}: billed {billed}, budget "
                                                                 f"{b['budget_units']} [R4-02, R4-03, I5-01]")
        c.check(sum(d["spent_units"] for d in ds if d) == b["spent_units"], "dossier spending != batch spending [R4-03]")
    c.check(all(d and d["spent_units"] <= 80 for d in ds), f"a build across the stop spent more than 80 [R4-02]")
    c.mock_reset(0)
    c.expect(c.refresh(ada, ORBIT), 202, what="refresh after the restart [R4-04]")
    d, _ = c.wait(ada, ORBIT, timeout=40)
    c.check(d and d["state"] == "ready", f"refresh after the restart {d and d['state']} [R4-04]")


PHASES = {"pre-kill": phase_pre_kill, "post-kill": phase_post_kill,
          "s3-pre-restart": run3.phase_pre_restart, "s3-post-restart": run3.phase_post_restart}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="main")
    for k, dflt in (("service", "http://svc:8080"), ("service1", ""), ("service2", ""), ("service3", ""),
                    ("mock", "http://web:8080"), ("admin", "local-admin"), ("corpus", "/corpus"), ("state", "/logs")):
        ap.add_argument("--" + k, default=dflt)
    ap.add_argument("--only", default=os.environ.get("PROBE_ONLY", ""))
    args = ap.parse_args()
    c = Ctx4(args)
    for target, path in ((c.mock, "/_mock/health"), (c.svc, "/health")):
        t = time.monotonic()
        while time.monotonic() - t < 60:
            if c._http(target, "GET", path, timeout=2.0).status == 200:
                break
            time.sleep(0.2)
    if args.phase != "main":
        plan = [(f"R-{args.phase}", "R4-* T10-*", f"restart phase {args.phase}", PHASES[args.phase])]
    else:
        import test_appendix_a
        if test_appendix_a.main() != 0:
            return 2
        plan = ([("S1-" + p, r, t, f) for p, r, t, f in s1.PROBES] + [("S2-" + p, r, t, f) for p, r, t, f in run2.PROBES2]
                + [("S3-" + p, r, t, f) for p, r, t, f in run3.PROBES3] + PROBES4)
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
        print(f"{'PASS' if not bad else 'FAIL'} SERVED every excerpt served for its url, from prose ({len(c.citations)})")
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
