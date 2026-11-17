#!/usr/bin/env python3
"""Verifier black-box probes for dossier stage 2: the API part.

1. Re-runs every stage-1 probe (factory/probes/stage-1/run.py, imported, never edited) with the
   stage-2 dossier invariants (INV2) and the stage-2 evidence oracle (EV2) patched in.
2. Runs the stage-2 API probes A01..A08 and the stage-1-export upgrade probe U01.
Each probe names the ledger rows (factory/ledger/stage-2.md) it covers. Standard library only.

  python3 run2.py --service http://svc:8080 --service1 http://svc1:8080 --mock http://web:8080 \
                  --admin local-admin --corpus /corpus [--only S1-P06,A02]
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
import time
import traceback
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
S1_DIR = os.environ.get("S1_PROBES", os.path.join(os.path.dirname(HERE), "stage-1"))
sys.path.insert(0, S1_DIR)
_spec = importlib.util.spec_from_file_location("s1run", os.path.join(S1_DIR, "run.py"))
s1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s1)
A = s1.A
FIELDS = list(A.FIELDS)
KINDS = ("own", "filing", "news", "aggregator")
PROVIDERS = ("nimble", "tavily", "kernel", "browserbase")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")
KESTREL = "kestrel-dynamics.test"
KESTREL_SEL = {"legal_name": "Kestrel Dynamics AS", "hq_city": "Bergen", "ceo": "Mara Lind",
               "founded_year": 2002, "headcount_range": "51-200", "funding_total": 15000000}
KESTREL_VALUES = {"legal_name": {"Kestrel Dynamics AS", "Kestrel Dynamics Holding AS"},
                  "hq_city": {"Bergen", "Oslo", "Tromsø"}, "ceo": {"Mara Lind", "Tomas Berg"},
                  "founded_year": {2002, 2001}, "headcount_range": {"51-200", "501-1000"},
                  "funding_total": {15000000, 20000000, 99000000}}


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00").replace("z", "+00:00").replace("t", "T"))


def same_instant(a, b):
    if a is None or b is None:
        return a is None and b is None
    try:
        return parse_ts(a) == parse_ts(b)
    except ValueError:
        return False


def norm_val(v):
    return v.strip() if isinstance(v, str) else v


def authority(kind):
    return 0 if kind in ("own", "filing") else 1 if kind == "news" else 2


def rank_key(c):
    pub = c.get("published_at")
    rec = (1, 0.0) if pub is None else (0, -parse_ts(pub).timestamp())
    prov = PROVIDERS.index(c["provider"]) if c.get("provider") in PROVIDERS else 9
    v = norm_val(c.get("value"))
    return (authority(c.get("kind")), rec, c.get("url") or "", prov, (0, v, "") if isinstance(v, int) else (1, 0, v or ""))


def expected_kind(page, domain):
    k = page.get("kind")
    if k in KINDS:
        return k
    host = (urllib.parse.urlparse(page["url"]).hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return "own" if host == domain else "aggregator"


def expected_published(page):
    p = page.get("published_at")
    if isinstance(p, str) and TS_RE.match(p):
        try:
            parse_ts(p)
            return p
        except ValueError:
            return None
    return None


def first_support(text, field, value, domain):
    for sent in A.split_sentences(text):
        if len(sent) <= 500 and A.supported_value(sent, field, domain) == value:
            return A.collapse_ws(sent)
    return None


def expected_candidates(corpus, domain, epoch, research_ok=True):
    """{(field, url, value): (excerpt, kind, published)} the evidence certainly yields."""
    d = corpus.get(domain)
    if d is None:
        return None
    claims = (d.get("research", {}).get("nimble", {}) or {}).get(str(epoch), []) if research_ok else []
    cited = {r.get("url") for r in claims}
    out = {}
    for p in d.get("pages", []):
        if epoch not in p.get("epochs", []):
            continue
        if not (p.get("searchable", True) or p["url"] in cited):
            continue
        for f, vals in A.page_supports(p.get("text", ""), domain).items():
            for v in vals:
                out[(f, p["url"], v)] = (first_support(p["text"], f, v, domain), expected_kind(p, domain),
                                         expected_published(p))
    return out


class Ctx2(s1.Ctx):
    def __init__(self, args):
        super().__init__(args)
        self.svc1 = urllib.parse.urlparse(args.service1) if args.service1 else None
        self.imported = set()      # domains whose candidates may have kind null (imported, not rebuilt)
        self.renders = None        # {url: [texts]} of rendered extracts in the current cost window

    def mock_reset(self, epoch=0, quiet=True):
        super().mock_reset(epoch, quiet)
        self.renders = None

    def check(self, cond, msg):
        if not cond:
            with self.lock:
                if msg not in self.fail:
                    self.fail.append(msg)
        return cond

    def req1(self, method, path, body=None, token=None, key=None, raw=None):
        h = {}
        if token is not None:
            h["Authorization"] = f"Bearer {token}"
        if key is not None:
            h["Idempotency-Key"] = key
        return self._http(self.svc1, method, path, body, h, raw,
                          10.0 if path.startswith("/_test") else 5.0)

    # ------------------------------------------------------------ INV2
    def inv(self, d):
        if not isinstance(d, dict):
            self.check(False, f"INV2: dossier not an object: {d!r}")
            return
        dom = d.get("domain")
        p = []
        for k in ("dossier_id", "domain", "state", "researched_at", "spent_units", "fields"):
            if k not in d:
                p.append(f"missing key {k}")
        if not (isinstance(d.get("dossier_id"), str) and 0 < len(d["dossier_id"]) <= 64):
            p.append("dossier_id not a string of 1..64 chars [R3-28]")
        if d.get("state") not in ("building", "ready", "failed"):
            p.append(f"state {d.get('state')!r}")
        ra = d.get("researched_at")
        if ra is not None and not (isinstance(ra, str) and TS_RE.match(ra)):
            p.append(f"researched_at {ra!r} [R3-25]")
        su = d.get("spent_units")
        if not (isinstance(su, int) and not isinstance(su, bool) and su >= 0):
            p.append(f"spent_units {su!r}")
        f = d.get("fields")
        if not isinstance(f, dict) or sorted(f) != sorted(FIELDS):
            p.append("fields keys != six [QC-06]")
            f = {}
        for name in FIELDS:
            fv = f.get(name)
            if not isinstance(fv, dict):
                continue
            p.extend(f"{name}: {m}" for m in self._inv_field(dom, name, fv, ra))
        for m in p:
            self.check(False, f"INV2 {dom}: {m}")

    def _inv_field(self, dom, name, fv, researched_at):
        p = []
        v, st, cits, cands = fv.get("value"), fv.get("status"), fv.get("citations"), fv.get("candidates")
        if not isinstance(cands, list):
            return [f"candidates missing or not a list: {cands!r} [Q5-06, QC-06]"]
        if not isinstance(cits, list):
            return [f"citations not a list [R4-50]"]
        for i, c in enumerate(cands):
            if not isinstance(c, dict):
                p.append(f"candidate {i} not an object")
                continue
            keys = {"value", "url", "excerpt", "provider", "kind", "published_at", "retrieved_at", "selected"}
            if not keys <= set(c):
                p.append(f"candidate {i} lacks {sorted(keys - set(c))} [Q5-06]")
                continue
            if c["provider"] not in PROVIDERS:
                p.append(f"candidate {i} provider {c['provider']!r} [Q5-07]")
            if c["kind"] is None:
                if dom not in self.imported:
                    p.append(f"candidate {i} kind null on a built dossier [Q5-09]")
            elif c["kind"] not in KINDS:
                p.append(f"candidate {i} kind {c['kind']!r} [Q1-01]")
            for tk in ("published_at", "retrieved_at"):
                if c[tk] is not None and not (isinstance(c[tk], str) and TS_RE.match(c[tk])):
                    p.append(f"candidate {i} {tk} {c[tk]!r} not RFC 3339 [R3-25]")
            if c["retrieved_at"] is None:
                p.append(f"candidate {i} retrieved_at null [Q5-10]")
            elif researched_at is not None and not same_instant(c["retrieved_at"], researched_at):
                p.append(f"candidate {i} retrieved_at {c['retrieved_at']} != researched_at {researched_at} "
                         f"(time of the last ready build) [Q5-10]")
            if not isinstance(c["selected"], bool):
                p.append(f"candidate {i} selected {c['selected']!r}")
            ex = c["excerpt"]
            if not isinstance(ex, str) or not (1 <= len(ex) <= 500):
                p.append(f"candidate {i} excerpt length [R4-34]")
            elif isinstance(dom, str):
                got = A.supported_value(ex, name, dom)
                if got != norm_val(c["value"]):
                    p.append(f"candidate {i} value {c['value']!r}: excerpt {ex!r} supports {got!r} [Q5-01, R1-05]")
                with self.lock:
                    self.citations.setdefault((c["url"], ex, c["provider"]), (dom, name, c["value"], self.current))
        if p:
            return p
        if not cands:
            if v is not None or st != "unknown" or cits != []:
                p.append(f"no candidates but value {v!r} status {st!r} citations {cits!r} [Q5-14, Q7-03]")
            return p
        keys = [rank_key(c) for c in cands]
        for i in range(len(cands) - 1):
            if keys[i] > keys[i + 1]:
                p.append(f"candidates {i + 1} and {i + 2} out of rank order: {cands[i]['url']} {cands[i]['value']!r} "
                         f"before {cands[i + 1]['url']} {cands[i + 1]['value']!r} [Q5-13, Q6-*]")
            if keys[i] == keys[i + 1]:
                p.append(f"duplicate candidate (url, provider, value) {cands[i]['url']} {cands[i]['value']!r} [Q5-02, QD-19]")
        sel = [c for c in cands if c["selected"]]
        if len(sel) != 1 or not cands[0]["selected"]:
            p.append(f"selected flags {[c['selected'] for c in cands]}: exactly one, the first [Q5-11, Q5-13]")
        top = norm_val(cands[0]["value"])
        if norm_val(v) != top:
            p.append(f"value {v!r} != selected candidate value {cands[0]['value']!r} [Q6-08, Q0-03]")
        exp_cits = [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]}
                    for c in cands if norm_val(c["value"]) == top]
        got_cits = [{"url": c.get("url"), "excerpt": c.get("excerpt"), "provider": c.get("provider")}
                    for c in cits if isinstance(c, dict)]
        if got_cits != exp_cits:
            p.append(f"citations {got_cits} != candidates with the selected value in rank order {exp_cits} [Q6-09, QC-02]")
        distinct = {json.dumps(norm_val(c["value"]), sort_keys=True) for c in cands}
        want = "known" if len(distinct) == 1 else "contested"
        if st != want:
            p.append(f"status {st!r} but {len(distinct)} distinct candidate values -> {want} [Q7-01, Q7-02]")
        if name in ("founded_year", "funding_total") and not (isinstance(v, int) and not isinstance(v, bool)):
            p.append(f"value {v!r} not an integer [R4-18, R4-20]")
        if name == "headcount_range" and v not in A.HEADCOUNT_VALUES:
            p.append(f"headcount_range {v!r} [R4-19]")
        return p

    # ------------------------------------------------------------ EV2 (+ stage-1 EV, D13)
    def ev(self, d, epoch, research_ok=True):
        super().ev(d, epoch, research_ok)
        dom = d.get("domain")
        exp = expected_candidates(self.corpus, dom, epoch, research_ok)
        if exp is None:
            return
        got = {}
        for f in FIELDS:
            for c in (d.get("fields") or {}).get(f, {}).get("candidates") or []:
                if isinstance(c, dict):
                    got.setdefault((f, c.get("url"), norm_val(c.get("value"))), []).append(c)
        for (f, url, v), (ex, kind, pub) in sorted(exp.items(), key=lambda kv: str(kv[0])):
            cs = got.get((f, url, v))
            if not cs:
                self.check(False, f"EV2 {dom} epoch {epoch}: missing candidate {f}={v!r} from {url} "
                                  f"(page supports it: {ex!r}) [Q5-02, Q5-03, R8-08]")
                continue
            for c in cs:
                self.check(c.get("kind") == kind, f"EV2 {dom}: {f} candidate {url} kind {c.get('kind')!r} != {kind!r} "
                                                  f"[Q1-01, Q1-03, Q1-04, Q5-08]")
                self.check(same_instant(c.get("published_at"), pub),
                           f"EV2 {dom}: {f} candidate {url} published_at {c.get('published_at')!r} != {pub!r} [Q1-02, Q1-05]")
                self.check(A.collapse_ws(c.get("excerpt") or "") == ex,
                           f"EV2 {dom}: {f} candidate {url} excerpt {c.get('excerpt')!r} is not the first supporting "
                           f"sentence {ex!r} [QD-19]")
        for key in got:
            if key not in exp:
                self.note_once(f"{dom} epoch {epoch}: candidate {key} is not from a searchable or claim-cited page "
                               f"of the company in the corpus")
        if self.renders is not None:
            for (f, url, v), cs in got.items():
                for c in cs:
                    texts = self.renders.get(url, [])
                    ok = any(s1.excerpt_in(c.get("excerpt") or "", A.split_prose(t)[1]) for t in texts)
                    self.check(ok, f"D13 {dom}: candidate {f}={v!r} excerpt not found in a rendered extract of {url} "
                                   f"made by this build [QD-13, Q2-01]")

    # ------------------------------------------------------------ LOG window with render costs
    def window(self, domain, spent_before=0, spent_after=None, builds=1, what=""):
        calls = self.mock_log()
        cost = sum(c.get("cost") or 0 for c in calls)
        self.check(cost <= 80 * builds, f"{what} {domain}: {builds} build(s) cost {cost} > {80 * builds} [R1-07]")
        if spent_after is not None:
            self.check(spent_after - spent_before == cost,
                       f"{what} {domain}: spent_units grew by {spent_after - spent_before}, call log cost {cost} "
                       f"[R8-27, Q3-06, Q4-02]")
        doms = [c for c in calls if c.get("method") == "search" and c.get("status") == 200 and c.get("query") == domain]
        self.check(len(doms) == builds, f"{what} {domain}: {len(doms)} successful searches with query == domain "
                                        f"for {builds} build(s) [R4-29, Q4-06]")
        renders = {}
        for c in calls:
            m, prov, n = c.get("method"), c.get("provider"), len(c.get("urls") or [])
            if m == "research":
                self.check(domain in (c.get("query") or ""), f"{what}: research query lacks {domain} [R9-17]")
                self.check(c.get("fields") == sorted(FIELDS), f"{what}: research fields {c.get('fields')} [R9-18]")
            if m == "extract" and prov == "nimble":
                self.check(c.get("cost") in (0, n, 3 * n), f"{what}: nimble extract cost {c.get('cost')} for {n} urls "
                                                            f"[R9-07, Q3-06]")
                if c.get("status") == 200 and c.get("cost") == 3 * n and n:
                    for s in c.get("served") or []:
                        renders.setdefault(s.get("url"), []).append(s.get("text") or "")
            if c.get("status") == 429:
                self.check((c.get("cost") or 0) == 0, f"{what}: a 429 answer cost {c.get('cost')} [Q4-02]")
            if prov not in ("nimble",):
                self.note_once(f"call to provider {prov!r} (decisions D1/D14 say Nimble only)")
        self.renders = renders
        return calls, cost



# ---------------------------------------------------------------- stage-2 probes

PROBES2 = []


def probe(pid, rows, title):
    def deco(fn):
        PROBES2.append((pid, rows, title, fn))
        return fn
    return deco


def fresh(c):
    c.reset()
    c.mock_reset(0)
    return c.login("ada@example.com")


@probe("A01", "Q5-02 Q5-03 Q5-04 QC-04 QD-12", "candidates from claim-cited pages; unsupported claims are not candidates")
def a01(c):
    ada = fresh(c)
    d = s1.build_and_check(c, ada, s1.NORDLICHT, 0, what="A01")
    if not d:
        return
    f = d["fields"]
    c.check(f["funding_total"].get("candidates") == [] and f["headcount_range"].get("candidates") == [],
            "unsupported research claims became candidates [Q5-04]")
    c.check(any(x.get("url") == "https://registry.test/nordlicht-optics" for x in f["ceo"].get("candidates") or []),
            "the non-searchable page cited by a research claim was not read [Q5-03]")


@probe("A02", "Q1-03 Q1-04 Q1-05 Q5-08 Q5-10 Q6-01..Q6-11 Q7-02 Q7-05 Q0-04",
       "selection rule on the verifier company kestrel-dynamics.test")
def a02(c):
    ada = fresh(c)
    c.mock_fault("nimble", ["research"], "delay", 2)
    r = c.post(ada, KESTREL)
    c.expect(r, 202, what="POST kestrel")
    c.req("POST", "/_test/clock", {"now": s1.ts_plus(s1.T0, hours=1)})
    d, _ = c.wait(ada, KESTREL, timeout=30)
    if not c.check(d and d.get("state") == "ready", f"kestrel build {d and d.get('state')}"):
        return
    c.window(KESTREL, 0, d["spent_units"], 1, "A02")
    c.ev(d, 0)
    c.check(same_instant(d["researched_at"], s1.T0), f"researched_at {d['researched_at']} != time of the POST [R8-03]")
    for f in FIELDS:
        fv = d["fields"][f]
        c.check(fv["value"] == KESTREL_SEL[f], f"kestrel {f}: selected {fv['value']!r}, the rule picks "
                                              f"{KESTREL_SEL[f]!r} [Q6-*]")
        c.check(fv["status"] == "contested", f"kestrel {f}: status {fv['status']!r} [Q7-02]")
        vals = {norm_val(x.get("value")) for x in fv.get("candidates") or []}
        c.check(vals == KESTREL_VALUES[f], f"kestrel {f}: candidate values {vals} != {KESTREL_VALUES[f]} [Q5-02]")
        for x in fv.get("candidates") or []:
            c.check(same_instant(x.get("retrieved_at"), s1.T0), f"kestrel {f}: retrieved_at {x.get('retrieved_at')} is not the "
                                                            f"build time {s1.T0} (clock moved during the build) [Q5-10]")
    l = c.req("GET", "/dossiers?q=kestrel", token=ada)
    c.check(l.status == 200 and l.body["dossiers"] and l.body["dossiers"][0].get("legal_name") == "Kestrel Dynamics AS",
            f"list legal_name {l!r} [Q7-05]")
    c.mock_reset(0)
    d2 = s1.build_and_check(c, ada, KESTREL, 0, what="A02 refresh", fresh=False)
    if d2:
        c.check({f: d2["fields"][f]["value"] for f in FIELDS} == KESTREL_SEL,
                "same web, different selection after a refresh [Q0-04]")


@probe("A04", "QD-13 Q2-01 Q3-06", "every candidate excerpt comes from a rendered extract of its page (D13)")
def a04(c):
    ada = fresh(c)
    for dom in (s1.ZEPHYR, "halvorsen-robotics.test"):
        s1.build_and_check(c, ada, dom, 0, what="A04")


@probe("A05", "Q5-12 R8-25 R8-07", "candidates are those of the last ready build (during a refresh, after a failed one)")
def a05(c):
    ada = fresh(c)
    dom = "halvorsen-robotics.test"
    d0 = s1.build_and_check(c, ada, dom, 0, what="A05")
    if not d0:
        return
    c.mock_reset(0)
    c.mock_fault("nimble", ["research"], "delay", 3)
    c.expect(c.refresh(ada, dom), 202, what="refresh")
    g = c.get(ada, dom)
    c.check(g.status == 200 and g.body["state"] == "building" and g.body["fields"] == d0["fields"],
            "fields/candidates changed while a refresh runs [Q5-12]")
    d1, _ = c.wait(ada, dom, timeout=30)
    c.mock_reset(0)
    c.mock_fault("nimble", ["search", "extract", "research"], "error")
    c.expect(c.refresh(ada, dom), 202, what="refresh with providers failing")
    d2, _ = c.wait(ada, dom, timeout=60)
    c.mock_reset(0)
    if c.check(d1 and d2 and d2["state"] == "failed", f"state {d2 and d2['state']}"):
        c.check(d2["fields"] == d1["fields"], "failed refresh changed the candidates [Q5-12, R8-07]")


@probe("A06", "Q4-01..Q4-06 QD-15 Q4-02", "rate limits: weather and permanent 429s; still every candidate, one domain search")
def a06(c):
    ada = fresh(c)
    c.madmin("POST", "/_mock/weather", {"on": True})
    t = time.monotonic()  # by hand: build_and_check would reset the mock and turn the weather off
    r = c.post(ada, "halvorsen-robotics.test")
    c.expect(r, 202, what="POST under weather")
    d, el = c.wait(ada, "halvorsen-robotics.test", timeout=90, start=t)
    if c.check(d and d.get("state") == "ready", f"weather build {d and d.get('state')}"):
        c.window("halvorsen-robotics.test", 0, d["spent_units"], 1, "A06 weather")
        c.ev(d, 0)
    for methods, dom, exact in ((["extract"], s1.ZEPHYR, s1.ZEPHYR_E0), (["search", "research"], s1.NORDLICHT, s1.NORDLICHT_E)):
        c.mock_reset(0)
        c.mock_fault("nimble", methods, "rate_limit")
        t = time.monotonic()
        c.expect(c.post(ada, dom), 202, what=f"POST with permanent 429 on {methods}")
        d, el = c.wait(ada, dom, timeout=120, start=t)
        if c.check(d and d.get("state") == "ready", f"{dom} with 429 on {methods}: {d and d.get('state')} [Q4-04, QD-15]"):
            c.window(dom, 0, d["spent_units"], 1, f"A06 429 {methods}")
            c.ev(d, 0)
            got = {f: d["fields"][f]["value"] for f in FIELDS}
            c.check(got == exact, f"{dom} under permanent 429 on {methods}: {got} != {exact} [Q4-04, QD-15]")
    c.mock_reset(0)


@probe("A07", "QX-01..QX-05 QD-17 R10-27", "stage-2 export/import keeps candidates; mid-build export")
def a07(c):
    ada = fresh(c)
    k = s1.build_and_check(c, ada, KESTREL, 0, what="A07")
    z = s1.build_and_check(c, ada, s1.ZEPHYR, 0, what="A07")
    if not (k and z):
        return
    x = c.req("GET", "/_test/export")
    if not c.expect(x, 200, what="export"):
        return
    c.check(x.body.get("track") == "dossier" and x.body.get("format_version") == 1, "export envelope [QX-05]")
    c.mock_reset(0)
    c.mock_fault("nimble", ["research"], "delay", 4)
    c.expect(c.refresh(ada, KESTREL), 202, what="refresh during export")
    time.sleep(0.5)
    y = c.req("GET", "/_test/export")
    c.wait(ada, KESTREL, timeout=30)
    c.mock_reset(0)
    for exp, why in ((x, "export"), (y, "mid-build export")):
        c.expect(c.req("POST", "/_test/import", exp.body), 204, what=f"import {why}")
        for dom, before in ((KESTREL, k), (s1.ZEPHYR, z)):
            after = c.get(ada, dom).body or {}
            c.check(after.get("fields") == before["fields"] and after.get("state") == "ready",
                    f"{why}: {dom} fields/candidates differ after import [QX-01, QX-02, QX-03]")


@probe("A08", "Q8-01 Q8-09 QC-10 QD-18 QD-21", "Accept: text/html gets the UI on every browser route; API stays JSON and authenticated")
def a08(c):
    ada = fresh(c)
    c.post(ada, s1.ZEPHYR)
    c.wait(ada, s1.ZEPHYR)
    html_routes = ["/", "/signup", "/login", f"/dossiers/{s1.ZEPHYR}", f"/dossiers/{s1.ZEPHYR}/evidence", "/contested",
                   "/dossiers/WWW.Zephyr-Quantum.TEST", "/dossiers/absent-company.test"]
    accept = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    for path in html_routes:
        r = c._http(c.svc, "GET", path, headers={"Accept": accept})
        ok = r.status == 200 and r.headers.get("content-type", "").lower().startswith("text/html")
        c.check(ok, f"GET {path} with Accept: text/html -> {r.status} {r.headers.get('content-type')} [Q8-01, Q8-09, QD-18]")
        if ok and path == "/":
            for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", r.text):
                u = m.group(1)
                if re.match(r"^(https?:)?//", u):
                    c.check(False, f"UI document references an external asset {u} [QD-21, R2-27]")
    r = c.req("GET", f"/dossiers/{s1.ZEPHYR}")
    c.expect(r, 401, "unauthenticated", "API GET without token and without Accept: text/html [QC-10]")
    r = c.req("GET", f"/dossiers/{s1.ZEPHYR}", token=ada, headers={"Accept": "application/json"})
    c.check(r.status == 200 and isinstance(r.body, dict) and r.body.get("domain") == s1.ZEPHYR,
            f"API GET with Accept: application/json {r!r} [Q8-09]")


@probe("U01", "Q16-01 Q16-03..Q16-08 Q16-10 QX-04 QD-16 QD-17", "upgrade: import an export of the stage-1 service (9166a28)")
def u01(c):
    if c.svc1 is None:
        c.check(False, "no --service1 (stage-1 service) given")
        return
    c.mock_reset(0)
    r = c.req1("POST", "/_test/reset", s1.FIXTURE)
    if not c.check(r.status == 204, f"stage-1 reset {r!r}"):
        return
    t1 = c.req1("POST", "/auth/login", {"email": "ada@example.com", "password": s1.PW}).body["token"]
    cpw = "carol-" + s1.uid()
    carol = c.req1("POST", "/auth/signup", {"email": "carol@example.com", "password": cpw, "display_name": "Carol"}).body
    keys = {}
    for dom in (s1.ZEPHYR, "halvorsen-robotics.test", "nowhere-known.test"):
        keys[dom] = "u1-" + s1.uid()
        c.req1("POST", "/dossiers", {"domain": dom}, token=t1, key=keys[dom])
        _wait1(c, t1, dom)
    c.mock_fault("nimble", ["search", "extract", "research"], "error")
    c.req1("POST", "/dossiers", {"domain": "ashgrove-solar.test"}, token=t1, key="u1-fail")
    _wait1(c, t1, "ashgrove-solar.test", 60)
    c.mock_reset(0)
    klost = "u1-lost-" + s1.uid()
    lost = c.req1("POST", "/dossiers", {"domain": s1.NORDLICHT}, token=t1, key=klost)   # "lost" by the client
    _wait1(c, t1, s1.NORDLICHT)
    olds = {}
    for dom in (s1.ZEPHYR, "halvorsen-robotics.test", "nowhere-known.test", "ashgrove-solar.test", s1.NORDLICHT):
        olds[dom] = c.req1("GET", f"/dossiers/{dom}", token=t1).body
    e = c.req1("GET", "/_test/export")
    if not c.check(e.status == 200, f"stage-1 export {e!r}"):
        return
    c.reset()
    c.mock_reset(0)
    c.imported |= set(olds)
    r = c.req("POST", "/_test/import", e.body)
    if not c.expect(r, 204, what="stage-2 import of a stage-1 export [Q16-01]"):
        return
    c.expect(c.req("GET", "/dossiers", token=t1), 200, what="stage-1 token after the upgrade [QX-04, Q16-02]")
    r = c.req("POST", "/auth/login", {"email": "carol@example.com", "password": cpw})
    c.check(r.status == 200 and r.body.get("user_id") == carol.get("user_id"), f"carol login after upgrade {r!r} [QX-04]")
    l = c.req("GET", "/dossiers?limit=200", token=t1)
    c.check(l.status == 200 and sorted(x["domain"] for x in l.body["dossiers"]) == sorted(olds),
            f"imported dossiers listed {l!r} [Q16-03]")
    for dom, old in olds.items():
        new = c.get(c.login("ada@example.com"), dom).body or {}
        for k in ("dossier_id", "state", "researched_at", "spent_units"):
            c.check(new.get(k) == old.get(k), f"{dom}: {k} {new.get(k)!r} != stage-1 {old.get(k)!r} [Q16-03]")
        for f in FIELDS:
            of, nf = old["fields"][f], (new.get("fields") or {}).get(f) or {}
            cands = nf.get("candidates")
            if of["value"] is None:
                c.check(cands == [] and nf.get("status") == "unknown", f"{dom} {f}: null field gained candidates [QD-16]")
                continue
            want = sorted((x["url"], x["excerpt"], x["provider"]) for x in of["citations"]
                          if A.supported_value(x["excerpt"], f, dom) == of["value"])
            got = sorted((x.get("url"), x.get("excerpt"), x.get("provider")) for x in cands or [])
            c.check(got == want, f"{dom} {f}: candidates {got} != one per exported citation {want} [Q16-04, QD-16]")
            for x in cands or []:
                c.check(x.get("kind") is None and x.get("published_at") is None
                        and same_instant(x.get("retrieved_at"), old["researched_at"]) and norm_val(x.get("value")) == of["value"],
                        f"{dom} {f}: imported candidate {x} (kind/published null, retrieved_at = researched_at) [Q16-06, QD-16]")
            c.check(nf.get("value") == of["value"] and nf.get("status") == "known",
                    f"{dom} {f}: value/status after upgrade {nf.get('value')!r}/{nf.get('status')!r} [Q16-07]")
    rp = c.req("POST", "/dossiers", {"domain": s1.NORDLICHT}, token=t1, key=klost)
    c.check(rp.status == 200 and rp.body == lost.body, f"retry of a request lost before export {rp!r} vs {lost.body!r} [Q16-08]")
    c.expect(c.req("POST", "/dossiers", {"domain": "other.test"}, token=t1, key=keys[s1.ZEPHYR]), 409,
             "idempotency_key_reuse", "claimed stage-1 key with another body [QX-04]")
    time.sleep(0.3)
    c.check(c.mock_log() == [], "import or replay made a provider call [R10-20]")
    ada = c.login("ada@example.com")
    d = s1.build_and_check(c, ada, s1.ZEPHYR, 0, exact=s1.ZEPHYR_E0, what="U01 rebuild", fresh=False)
    if d:
        nulls = [(f, x.get("url")) for f in FIELDS for x in d["fields"][f].get("candidates") or [] if x.get("kind") is None]
        c.check(not nulls, f"after the next completed build imported candidates remain: {nulls} [Q16-10]")
    c.imported.clear()


def _wait1(c, tok, dom, timeout=30):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        r = c.req1("GET", f"/dossiers/{urllib.parse.quote(dom)}", token=tok)
        if r.status == 200 and r.body.get("state") != "building":
            return r.body
        time.sleep(0.3)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", default=os.environ.get("SERVICE_URL", "http://svc:8080"))
    ap.add_argument("--service1", default=os.environ.get("SERVICE1_URL", ""))
    ap.add_argument("--mock", default=os.environ.get("MOCK_URL", "http://web:8080"))
    ap.add_argument("--admin", default=os.environ.get("MOCK_ADMIN_TOKEN", "local-admin"))
    ap.add_argument("--corpus", default=os.environ.get("CORPUS_DIR", "/corpus"))
    ap.add_argument("--only", default=os.environ.get("PROBE_ONLY", ""))
    args = ap.parse_args()
    import test_appendix_a
    if test_appendix_a.main() != 0:
        return 2
    c = Ctx2(args)
    t = time.monotonic()
    while time.monotonic() - t < 60:
        if c._http(c.mock, "GET", "/_mock/health", timeout=2.0).status == 200:
            break
        time.sleep(0.5)
    t = time.monotonic()
    while time.monotonic() - t < 60:
        if c._http(c.svc, "GET", "/health", timeout=2.0).status == 200:
            break
        time.sleep(0.5)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    plan = [("S1-" + pid, rows, title, fn) for pid, rows, title, fn in s1.PROBES] + PROBES2
    results = []
    for pid, rows, title, fn in plan:
        if only and pid not in only:
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
        if len(c.fail) > 40:
            print(f"     ... {len(c.fail) - 40} more", flush=True)
    c.current = "SERVED"
    bad = s1.served_check(c)
    results.append(("SERVED", not bad))
    print(f"{'PASS' if not bad else 'FAIL'} SERVED every citation/candidate excerpt was served for its url, from prose, "
          f"by the named provider ({len(c.citations)} excerpts) [R1-05 Q2-04 Q2-05 Q5-05 Q5-07]")
    for m in bad[:40]:
        print("     - " + m)
    results.append(("G", not c.global_viol))
    print(f"{'PASS' if not c.global_viol else 'FAIL'} G global response checks [R5-01 R5-15 R3-24 R2-24]")
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
