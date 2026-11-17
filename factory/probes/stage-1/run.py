#!/usr/bin/env python3
"""Verifier black-box probes for dossier stage 1.

Talks to the service only over HTTP, and to the mock web only through its admin API
(/_mock/reset, /_mock/faults, /_mock/epoch, /_mock/log). Every probe names the ledger rows
(factory/ledger/stage-1.md) it covers. Standard library only.

  python3 run.py --service http://svc:8080 --mock http://web:8080 --admin local-admin \
                 --corpus /corpus [--only P06,P11]
"""
import argparse
import datetime as dt
import glob
import http.client
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import appendix_a as A  # noqa: E402

T0 = "2026-03-01T09:00:00+00:00"
PW = "correct horse"
FIXTURE = {"now": T0, "users": [
    {"id": "u_ada", "email": "ada@example.com", "password": PW, "display_name": "Ada"},
    {"id": "u_bob", "email": "bob@example.com", "password": PW, "display_name": "Bob"}]}
SIX = sorted(A.FIELDS)
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
ZEPHYR = "zephyr-quantum.test"
NORDLICHT = "nordlicht-optics.test"
ZEPHYR_E0 = {"legal_name": "Zephyr Quantum Systems GmbH", "hq_city": "Zürich", "ceo": "Lena Vogt",
             "founded_year": 2011, "headcount_range": "51-200", "funding_total": 12500000}
ZEPHYR_E1 = dict(ZEPHYR_E0, ceo="Oskar Lind")
NORDLICHT_E = {"legal_name": None, "hq_city": "Malmö", "ceo": "Ines Brandt", "founded_year": 2005,
               "headcount_range": None, "funding_total": None}


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def ts_plus(base, **kw):
    return (parse_ts(base) + dt.timedelta(**kw)).isoformat()


def uid():
    return uuid.uuid4().hex[:12]


class Resp:
    def __init__(self, status, body, text, headers, elapsed, error=None):
        self.status, self.body, self.text, self.headers, self.elapsed, self.error = \
            status, body, text, headers, elapsed, error

    def __repr__(self):
        return f"<{self.status} {self.text[:300]!r}>"


class Ctx:
    def __init__(self, args):
        self.args = args
        self.svc = urllib.parse.urlparse(args.service)
        self.mock = urllib.parse.urlparse(args.mock)
        self.lock = threading.Lock()
        self.fail = []          # failures of the current probe
        self.notes = []         # non-blocking notes (whole run)
        self.global_viol = []   # G violations (whole run)
        self.citations = {}     # (url, excerpt, provider) -> (domain, field, value, probe)
        self.served = {}        # url -> [(provider, method, depth, text)]
        self.current = "-"
        self.corpus = load_corpus(args.corpus)
        self.mock_epoch = 0

    # ------------------------------------------------------------ low-level HTTP
    def _http(self, target, method, path, body=None, headers=None, raw=None, timeout=5.0):
        h = {"Connection": "close"}
        data = None
        if raw is not None:
            data = raw.encode() if isinstance(raw, str) else raw
            h["Content-Type"] = "application/json"
        elif body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        t = time.monotonic()
        try:
            c = http.client.HTTPConnection(target.hostname, target.port or 80, timeout=timeout)
            c.request(method, path, body=data, headers=h)
            r = c.getresponse()
            text = r.read().decode("utf-8", "replace")
            el = time.monotonic() - t
            hd = {k.lower(): v for k, v in r.getheaders()}
            c.close()
        except Exception as e:  # timeout or connection failure
            return Resp(None, None, "", {}, time.monotonic() - t, error=repr(e))
        try:
            js = json.loads(text) if text else None
        except ValueError:
            js = None
        return Resp(r.status, js, text, hd, el)

    def req(self, method, path, body=None, token=None, key=None, raw=None, headers=None, timeout=None):
        h = dict(headers or {})
        if token is not None:
            h["Authorization"] = f"Bearer {token}"
        if key is not None:
            h["Idempotency-Key"] = key
        if timeout is None:
            timeout = 10.0 if path.startswith("/_test/reset") or path.startswith("/_test/import") \
                or path.startswith("/_test/export") else 5.0
        r = self._http(self.svc, method, path, body, h, raw, timeout)
        self._global(method, path, r, timeout)
        return r

    def _global(self, method, path, r, timeout):
        where = f"[{self.current}] {method} {path}"
        if r.status is None:
            self.gv(f"{where}: no response within {timeout}s ({r.error}) [R2-24]")
            return
        if r.status >= 500:
            self.gv(f"{where}: 5xx {r!r} [R5-15]")
        if r.status >= 400:
            b = r.body
            if not (isinstance(b, dict) and isinstance(b.get("error"), dict)
                    and isinstance(b["error"].get("code"), str) and isinstance(b["error"].get("message"), str)):
                self.gv(f"{where}: error body not {{error:{{code,message}}}}: {r!r} [R5-01]")
        if r.status != 204 and r.text:
            ct = r.headers.get("content-type", "")
            if not ct.lower().startswith("application/json"):
                self.gv(f"{where}: content-type {ct!r} [R3-24]")
            elif "charset=utf-8" not in ct.lower().replace(" ", ""):
                self.note_once("content-type lacks '; charset=utf-8' (R3-24): " + ct)

    def gv(self, msg):
        with self.lock:
            self.global_viol.append(msg)

    def note_once(self, msg):
        with self.lock:
            if msg not in self.notes:
                self.notes.append(msg)

    def check(self, cond, msg):
        if not cond:
            with self.lock:
                self.fail.append(msg)
        return cond

    def expect(self, r, status, code=None, what=""):
        ok = r.status == status
        if ok and code is not None:
            ok = isinstance(r.body, dict) and isinstance(r.body.get("error"), dict) and r.body["error"].get("code") == code
        self.check(ok, f"{what}: expected {status}{' ' + code if code else ''}, got {r!r}")
        return ok

    # ------------------------------------------------------------ mock admin
    def madmin(self, method, path, body=None):
        r = self._http(self.mock, method, path, body, {"X-Mock-Admin": self.args.admin}, None, 10.0)
        if r.status not in (200, 204):
            raise RuntimeError(f"mock admin {method} {path} -> {r!r}")
        return r

    def mock_log(self):
        calls = self.madmin("GET", "/_mock/log").body.get("calls", [])
        return calls

    def capture_log(self):
        for c in self.mock_log():
            for s in c.get("served") or []:
                url, text = s.get("url"), s.get("text")
                if url is None or text is None:
                    continue
                with self.lock:
                    self.served.setdefault(url, []).append((c.get("provider"), c.get("method"), c.get("depth"), text))

    def mock_reset(self, epoch=0, quiet=True):
        if quiet:  # let stray calls of builds cut by a reset land before the log is cleared
            n, t, last = -1, time.monotonic(), time.monotonic()
            while time.monotonic() - t < 15:
                m = len(self.mock_log())
                if m != n:
                    n, last = m, time.monotonic()
                elif time.monotonic() - last >= 1.5:
                    break
                time.sleep(0.3)
        self.capture_log()
        self.madmin("POST", "/_mock/reset", {"epoch": epoch})
        self.mock_epoch = epoch

    def mock_fault(self, provider, methods, mode, seconds=None):
        b = {"provider": provider, "methods": methods, "mode": mode}
        if seconds is not None:
            b["seconds"] = seconds
        self.madmin("POST", "/_mock/faults", b)

    # ------------------------------------------------------------ service helpers
    def reset(self, fixture=None):
        r = self.req("POST", "/_test/reset", fixture or FIXTURE)
        self.expect(r, 204, what="reset")
        return r

    def login(self, email, pw=PW):
        r = self.req("POST", "/auth/login", {"email": email, "password": pw})
        self.expect(r, 200, what=f"login {email}")
        return (r.body or {}).get("token")

    def signup(self, email=None, pw="pw-" + "x" * 8, name="Probe"):
        email = email or f"p{uid()}@example.com"
        r = self.req("POST", "/auth/signup", {"email": email, "password": pw, "display_name": name})
        self.expect(r, 201, what=f"signup {email}")
        return (r.body or {}).get("token"), email, (r.body or {}).get("user_id")

    def get(self, token, domain):
        r = self.req("GET", "/dossiers/" + urllib.parse.quote(domain, safe=""), token=token)
        if r.status == 200:
            self.inv(r.body)
        return r

    def post(self, token, domain, key=None, extra=None):
        body = {"domain": domain}
        body.update(extra or {})
        return self.req("POST", "/dossiers", body, token=token, key=key or uid())

    def refresh(self, token, domain, key=None, body=None):
        return self.req("POST", "/dossiers/" + urllib.parse.quote(domain, safe="") + "/refresh",
                        body, token=token, key=key or uid())

    def wait(self, token, domain, timeout=12.0, start=None):
        """Poll until state != building. Returns (body, seconds since start, polls)."""
        start = start or time.monotonic()
        last = None
        spent_seen = []
        while time.monotonic() - start < timeout:
            r = self.get(token, domain)
            if r.status == 200:
                last = r.body
                spent_seen.append(last.get("spent_units"))
                if last.get("state") != "building":
                    break
            time.sleep(0.2)
        el = time.monotonic() - start
        nums = [s for s in spent_seen if isinstance(s, int)]
        self.check(nums == sorted(nums), f"{domain}: spent_units decreased during build {nums} [RD-04]")
        return last, el

    # ------------------------------------------------------------ invariants (INV)
    def inv(self, d):
        p = []
        if not isinstance(d, dict):
            self.check(False, f"INV: dossier not an object: {d!r}")
            return
        dom = d.get("domain")
        for k in ("dossier_id", "domain", "state", "researched_at", "spent_units", "fields"):
            if k not in d:
                p.append(f"missing key {k} [R8-21]")
        if not (isinstance(d.get("dossier_id"), str) and 0 < len(d["dossier_id"]) <= 64):
            p.append(f"dossier_id not a string of 1..64 chars [R3-28]")
        if d.get("state") not in ("building", "ready", "failed"):
            p.append(f"state {d.get('state')!r} [R8-22]")
        ra = d.get("researched_at")
        if ra is not None and not (isinstance(ra, str) and TS_RE.match(ra)):
            p.append(f"researched_at {ra!r} not RFC 3339 with offset [R3-25]")
        su = d.get("spent_units")
        if not (isinstance(su, int) and not isinstance(su, bool) and su >= 0):
            p.append(f"spent_units {su!r} [R8-27]")
        f = d.get("fields")
        if not isinstance(f, dict) or sorted(f.keys()) != SIX:
            p.append(f"fields keys {sorted(f.keys()) if isinstance(f, dict) else f!r} != six [R4-14, R8-23]")
            f = {}
        for name, fv in f.items():
            if not isinstance(fv, dict):
                p.append(f"{name} not an object")
                continue
            v, st, cits = fv.get("value"), fv.get("status"), fv.get("citations")
            if v is None:
                if st != "unknown" or cits != []:
                    p.append(f"{name}: null value needs status unknown and [] citations, got {st!r} {cits!r} [R4-23, R4-25]")
                continue
            if st != "known":
                p.append(f"{name}: value {v!r} with status {st!r} [R4-23]")
            if name in ("founded_year", "funding_total"):
                if not (isinstance(v, int) and not isinstance(v, bool)):
                    p.append(f"{name}: {v!r} not a JSON integer [R4-18, R4-20]")
            elif not isinstance(v, str) or v != v.strip() or not v:
                p.append(f"{name}: {v!r} not a trimmed string [R4-21]")
            if name == "headcount_range" and v not in A.HEADCOUNT_VALUES:
                p.append(f"headcount_range {v!r} not an allowed range [R4-19]")
            if not isinstance(cits, list) or not cits:
                p.append(f"{name}: known without citations [R4-24, R1-05]")
                continue
            for c in cits:
                if not isinstance(c, dict):
                    p.append(f"{name}: citation not an object")
                    continue
                url, ex, prov = c.get("url"), c.get("excerpt"), c.get("provider")
                if prov not in ("nimble", "tavily"):
                    p.append(f"{name}: provider {prov!r} [R4-27]")
                if not isinstance(url, str) or not url:
                    p.append(f"{name}: url {url!r} [R4-26]")
                if not isinstance(ex, str) or not (1 <= len(ex) <= 500):
                    p.append(f"{name}: excerpt length {len(ex) if isinstance(ex, str) else ex!r} not 1..500 [R4-34]")
                    continue
                if isinstance(dom, str):
                    got = A.supported_value(ex, name, dom)
                    if got != v:
                        p.append(f"{name}={v!r}: excerpt {ex!r} supports {got!r} by Appendix A [R1-05, R1-06, R4-36, R4-40]")
                with self.lock:
                    self.citations.setdefault((url, ex, prov), (dom, name, v, self.current))
        for msg in p:
            self.check(False, f"INV {dom}: {msg}")

    # ------------------------------------------------------------ evidence oracle (EV)
    def ev(self, d, epoch, research_ok=True):
        dom = d.get("domain")
        must = expected_must(self.corpus, dom, epoch, research_ok)
        if must is None:
            return
        for f in A.FIELDS:
            fv = (d.get("fields") or {}).get(f) or {}
            if must[f] and fv.get("value") is None:
                self.check(False, f"EV {dom} epoch {epoch}: {f} unknown but the evidence supports {sorted(map(str, must[f]))} "
                                  f"e.g. {must[f][next(iter(must[f]))][0]!r} [R8-08, R4-28, R4-41]")
            if not must[f] and fv.get("value") is not None:
                self.note_once(f"{dom} epoch {epoch}: {f}={fv.get('value')!r} known although no searchable page of the "
                               f"company nor a supported research claim supports a value (citations "
                               f"{[c.get('url') for c in fv.get('citations') or []]}) [R8-08]")

    # ------------------------------------------------------------ call-log window (LOG)
    def window(self, domain, spent_before=0, spent_after=None, builds=1, what=""):
        calls = self.mock_log()
        cost = sum(c.get("cost") or 0 for c in calls)
        self.check(cost <= 80 * builds, f"{what} {domain}: {builds} build(s) cost {cost} > {80 * builds} [R1-07, R9-16]")
        if spent_after is not None:
            self.check(spent_after - spent_before == cost,
                       f"{what} {domain}: spent_units grew by {spent_after - spent_before}, call log cost {cost} [R8-27, R9-01..R9-09]")
        doms = [c for c in calls if c.get("method") == "search" and c.get("status") == 200 and c.get("query") == domain]
        self.check(len(doms) == builds,
                   f"{what} {domain}: {len(doms)} successful searches with query == domain for {builds} build(s) [R4-29, R4-30]")
        for c in calls:
            if c.get("method") == "research":
                self.check(domain in (c.get("query") or ""), f"{what}: research query {c.get('query')!r} lacks {domain} [R9-17]")
                self.check(c.get("fields") == SIX, f"{what}: research fields {c.get('fields')!r} != six [R9-18]")
            if c.get("method") == "extract" and c.get("provider") == "nimble":
                self.check(c.get("cost") in (0, len(c.get("urls") or [])),
                           f"{what}: nimble extract cost {c.get('cost')} for {len(c.get('urls') or [])} urls (render?) [R9-15]")
            if c.get("provider") == "tavily":
                self.note_once("a tavily call was made (decision D1 says Nimble only) [RD-01]")
            if c.get("provider") not in ("nimble", "tavily"):
                self.note_once(f"call to provider {c.get('provider')!r}")
        return calls, cost


# ---------------------------------------------------------------- corpus / evidence oracle

def load_corpus(path):
    out = {}
    for f in sorted(glob.glob(os.path.join(path, "*.json"))):
        name = os.path.basename(f)
        if name in ("traits.json", "key.json"):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(d, dict) and "domain" in d:
            out[d["domain"]] = d
    return out


def expected_must(corpus, domain, epoch, research_ok=True):
    """Values the evidence certainly supports: whole sentences of the company's own searchable pages
    in this epoch, plus research claims whose excerpt supports the claimed value."""
    d = corpus.get(domain)
    if d is None:
        return None
    must = {f: {} for f in A.FIELDS}
    for p in d.get("pages", []):
        if epoch in p.get("epochs", []) and p.get("searchable", True):
            for f, vals in A.page_supports(p.get("text", ""), domain).items():
                for v, ss in vals.items():
                    must[f].setdefault(v, []).extend(ss)
    if research_ok:
        for r in (d.get("research", {}).get("nimble", {}) or {}).get(str(epoch), []):
            v = A.supported_value(r.get("excerpt", ""), r.get("field"), domain)
            if v is not None and v == A.normalise_claim_value(r.get("field"), r.get("value")):
                must[r["field"]].setdefault(v, []).append(r["excerpt"])
    return must


def excerpt_in(excerpt, text):
    parts = excerpt.split(" ")
    pat = r"\s+".join(re.escape(x) for x in parts)
    return re.search(pat, text) is not None


def prose_of(provider, method, depth, text):
    if method == "research":
        return text
    if method == "search" and (depth == "lite" or (provider == "tavily" and depth == "fast")):
        return text
    return A.split_prose(text)[1]


# ---------------------------------------------------------------- probes

PROBES = []


def probe(pid, rows, title):
    def deco(fn):
        PROBES.append((pid, rows, title, fn))
        return fn
    return deco


def par(n, fn):
    with ThreadPoolExecutor(max_workers=n) as ex:
        return list(ex.map(fn, range(n)))


@probe("P00", "R2-22 R3-03 R3-04 R3-05 R3-06 R3-19", "startup, health, pre-reset clock")
def p00(c):
    start = time.monotonic()
    ok = False
    while time.monotonic() - start < 60:
        r = c._http(c.svc, "GET", "/health", timeout=2.0)
        if r.status == 200:
            ok = True
            break
        time.sleep(0.5)
    if not c.check(ok, "no 200 from /health within 60 s of probe start [R3-04, R2-22]"):
        return
    r = c.req("GET", "/health")
    c.check(r.status == 200 and r.body == {"status": "ok"}, f"/health body {r!r} [R3-03]")
    c.mock_reset(0)
    for _ in range(3):
        c.req("GET", "/health")
    c.check(c.mock_log() == [], "/health made a provider call [R3-06]")
    tok, _, _ = c.signup()
    r = c.post(tok, "windrush-bakery.test")
    c.expect(r, 202, what="pre-reset POST /dossiers")
    d, _ = c.wait(tok, "windrush-bakery.test")
    if d and d.get("researched_at"):
        skew = abs((parse_ts(d["researched_at"]) - dt.datetime.now(dt.timezone.utc)).total_seconds())
        c.check(skew < 300, f"before the first reset researched_at {d['researched_at']} is {skew:.0f}s from system time [R3-19]")
    else:
        c.check(False, f"pre-reset build did not complete ready: {d!r}")


@probe("P01", "R3-07..R3-14 R4-47 R4-48 R4-49 R6-08 R5-03", "reset and seed")
def p01(c):
    c.mock_reset(0)
    tok_pre, email_pre, _ = c.signup()
    r = c.reset()
    c.check(r.elapsed < 10, f"reset took {r.elapsed:.1f}s [R2-24]")
    for u in FIXTURE["users"]:
        r = c.req("POST", "/auth/login", {"email": u["email"], "password": PW})
        c.expect(r, 200, what=f"seeded login {u['email']} [R4-48]")
        if r.status == 200:
            c.check(r.body.get("user_id") == u["id"], f"seeded user_id {r.body.get('user_id')!r} != {u['id']} [R6-08]")
            c.check(r.body.get("display_name") == u["display_name"], f"display_name {r.body.get('display_name')!r} [R6-02]")
    r = c.req("POST", "/auth/login", {"email": email_pre, "password": "pw-" + "x" * 8})
    c.expect(r, 401, "unauthenticated", "pre-reset user login after reset [R3-09]")
    r = c.req("GET", "/dossiers", token=tok_pre)
    c.expect(r, 401, "unauthenticated", "pre-reset token after reset [R3-09]")
    ada = c.login("ada@example.com")
    r = c.req("GET", "/dossiers", token=ada)
    c.check(r.status == 200 and r.body.get("dossiers") == [] and r.body.get("has_more") is False,
            f"list after reset {r!r} [R3-10]")
    r = c.get(ada, "windrush-bakery.test")
    c.expect(r, 404, "not_found", "dossier from before reset [R3-10]")
    key = "reset-key-" + uid()
    r1 = c.post(ada, "nowhere-known.test", key)
    c.expect(r1, 202, what="first POST")
    c.wait(ada, "nowhere-known.test")
    c.reset()
    ada = c.login("ada@example.com")
    r2 = c.post(ada, "nowhere-known.test", key)
    c.expect(r2, 202, what="same key after reset must be a first use, not a replay [R3-11]")
    c.wait(ada, "nowhere-known.test")
    for i in range(3):
        c.check(c.req("POST", "/_test/reset", FIXTURE).status == 204, "repeated reset [R3-12]")
    ada = c.login("ada@example.com")
    c.post(ada, "nowhere-known.test")
    c.wait(ada, "nowhere-known.test")
    bad = {"now": T0, "users": [
        {"id": "u_x", "email": "x@example.com", "password": PW, "display_name": "X"},
        {"id": "u_y", "email": "x@example.com", "password": PW, "display_name": "Y"}]}
    c.expect(c.req("POST", "/_test/reset", bad), 422, "validation_failed", "fixture with duplicate email [R4-49]")
    c.expect(c.req("POST", "/_test/reset", {"users": FIXTURE["users"]}), 422, "validation_failed",
             "fixture without now [R4-47]")
    c.expect(c.req("POST", "/_test/reset", raw="{not json"), 400, "malformed_request", "reset malformed JSON [R5-03]")
    c.expect(c.req("POST", "/_test/reset", {"now": 12345, "users": []}), 400, "malformed_request",
             "reset now of wrong type [R5-03]")
    # nothing changed by the failed resets
    r = c.req("POST", "/auth/login", {"email": "ada@example.com", "password": PW})
    c.expect(r, 200, what="ada still logs in after rejected resets [R4-49]")
    c.check(c.req("POST", "/auth/login", {"email": "x@example.com", "password": PW}).status == 401,
            "user of the rejected fixture exists [R4-49]")
    r = c.get(ada, "nowhere-known.test")
    c.expect(r, 200, what="dossier survives rejected resets [R4-49]")


@probe("P02", "R3-15..R3-23 R8-03 R4-47", "clock")
def p02(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    t30 = ts_plus(T0, minutes=30)
    c.expect(c.req("POST", "/_test/clock", {"now": t30}), 204, what="clock forward [R3-17]")
    c.expect(c.req("POST", "/_test/clock", {"now": t30}), 204, what="clock to the same time is not earlier [R3-22]")
    c.expect(c.req("POST", "/_test/clock", {"now": T0}), 422, "validation_failed", "clock earlier [R3-22]")
    c.expect(c.req("POST", "/_test/clock", {"now": "2026-03-01T12:00:00"}), 422, "validation_failed",
             "clock without offset [R3-21]")
    c.expect(c.req("POST", "/_test/clock", {"now": "tomorrow"}), 422, "validation_failed", "clock not RFC 3339 [R3-21]")
    c.expect(c.req("POST", "/_test/clock", {}), 422, "validation_failed", "clock without now")
    c.expect(c.req("POST", "/_test/clock", {"now": 5}), 400, "malformed_request", "clock now of wrong type [R5-03]")
    c.expect(c.req("POST", "/_test/clock", raw="{bad"), 400, "malformed_request", "clock malformed body")
    r = c.post(ada, ZEPHYR)
    c.expect(r, 202, what="POST zephyr")
    time.sleep(1.5)
    d, _ = c.wait(ada, ZEPHYR)
    if c.check(d and d.get("researched_at"), f"zephyr build not ready {d!r}"):
        c.check(parse_ts(d["researched_at"]) == parse_ts(t30),
                f"researched_at {d['researched_at']} != clock {t30}: clock moved without a clock call, or the rejected "
                f"clock change took effect [R3-15, R3-16, R3-20, R3-22]")
        d2 = c.get(ada, ZEPHYR).body
        c.check(d2.get("researched_at") == d.get("researched_at"), "researched_at changed between reads [R3-20]")
    # build time = time the request was received, even if the clock moves during the build
    t1 = "2026-03-01T11:00:00+01:00"  # = T0 + 1h, written with another offset
    c.expect(c.req("POST", "/_test/clock", {"now": t1}), 204, what="clock with +01:00 offset")
    c.mock_fault("nimble", ["research"], "delay", 3)
    c.expect(c.post(ada, NORDLICHT), 202, what="POST nordlicht")
    c.expect(c.req("POST", "/_test/clock", {"now": ts_plus(T0, hours=2)}), 204, what="clock during build")
    d, _ = c.wait(ada, NORDLICHT, timeout=20)
    if c.check(d and d.get("researched_at"), f"nordlicht build not ready {d!r}"):
        c.check(parse_ts(d["researched_at"]) == parse_ts(t1),
                f"researched_at {d['researched_at']} != time the POST was received {t1} [R8-03]")
    c.mock_reset(0)


@probe("P03", "R3-26 R3-27 R3-28", "conventions")
def p03(c):
    c.reset()
    r = c.req("POST", "/auth/signup", {"email": f"u{uid()}@example.com", "password": "longenough",
                                         "display_name": "U", "favourite_colour": "teal"})
    c.expect(r, 201, what="signup with unknown field [R3-26]")
    if r.status == 201:
        c.check(isinstance(r.body.get("user_id"), str) and len(r.body["user_id"]) <= 64, "user_id > 64 chars [R3-28]")
        tok = r.body.get("token")
        r = c.req("GET", "/dossiers?colour=teal&limit=5", token=tok)
        c.expect(r, 200, what="unknown query parameter [R3-27]")


@probe("P04", "R4-01 R5-05 R6-01..R6-12 R5-03 R5-09 R5-11 R11-01", "authentication")
def p04(c):
    c.reset()
    c.mock_reset(0)
    email = f"a{uid()}@example.com"
    r = c.req("POST", "/auth/signup", {"email": email, "password": "12345678", "display_name": "N" * 100})
    c.expect(r, 201, what="signup: 8-char password, 100-char display_name [R6-01, R6-04, R6-06]")
    if r.status == 201:
        c.check(set(r.body) >= {"user_id", "display_name", "token"} and r.body["display_name"] == "N" * 100,
                f"signup body {r.body!r} [R6-01]")
    c.expect(c.req("POST", "/auth/signup", {"email": email, "password": "12345678", "display_name": "X"}),
             409, "email_taken", "duplicate signup [R6-03]")
    c.expect(c.req("POST", "/auth/signup", {"email": "ada@example.com", "password": "12345678", "display_name": "X"}),
             409, "email_taken", "signup with a seeded email [R6-03]")
    for pw, dn, em, why in [("1234567", "X", None, "7-char password [R6-04]"),
                            ("12345678", "", None, "empty display_name [R6-06]"),
                            ("12345678", "N" * 101, None, "101-char display_name [R6-06]"),
                            ("12345678", "X", "plainaddress", "email without @ [R6-05]"),
                            ("12345678", "X", "@example.com", "email without local part [R6-05]"),
                            ("12345678", "X", "someone@", "email without domain [R6-05]")]:
        c.expect(c.req("POST", "/auth/signup", {"email": em or f"v{uid()}@example.com", "password": pw,
                                                 "display_name": dn}), 422, "validation_failed", why)
    c.expect(c.req("POST", "/auth/signup", {"email": f"w{uid()}@example.com", "display_name": "X"}),
             422, "validation_failed", "signup without password [R5-08]")
    c.expect(c.req("POST", "/auth/signup", {"email": 5, "password": "12345678", "display_name": "X"}),
             400, "malformed_request", "email of wrong type [R5-11]")
    c.expect(c.req("POST", "/auth/signup", {"email": f"z{uid()}@example.com", "password": 12345678, "display_name": "X"}),
             400, "malformed_request", "password of wrong type [R5-11]")
    c.expect(c.req("POST", "/auth/signup", raw="{\"email\": "), 400, "malformed_request", "signup malformed JSON [R5-03]")
    c.expect(c.req("POST", "/auth/login", {"email": "ada@example.com", "password": "wrong password"}),
             401, "unauthenticated", "wrong password [R6-07]")
    c.expect(c.req("POST", "/auth/login", {"email": "nobody@example.com", "password": PW}),
             401, "unauthenticated", "unknown email [R6-07]")
    r = c.req("POST", "/auth/login", {"email": email, "password": "12345678"})
    c.expect(r, 200, what="login after signup [R6-02]")
    if r.status == 200:
        c.check(set(r.body) >= {"user_id", "display_name", "token"}, f"login body {r.body!r} [R6-02]")
    # tokens
    t1 = c.login("ada@example.com")
    t2 = c.login("ada@example.com")
    for t in (t1, t2):
        c.expect(c.req("GET", "/dossiers", token=t), 200, what="each of several tokens is valid [R6-12]")
    for hdr, why in [({}, "no Authorization"), ({"Authorization": "Bearer"}, "empty bearer"),
                     ({"Authorization": "Basic YWRhOnB3"}, "Basic scheme"),
                     ({"Authorization": "Bearer not-a-real-token"}, "unknown token")]:
        c.expect(c.req("GET", "/dossiers", headers=hdr), 401, "unauthenticated", f"GET /dossiers with {why} [R5-05]")
    c.expect(c.req("GET", "/dossiers/acme.test"), 401, "unauthenticated", "GET dossier without token [R6-09]")
    c.expect(c.req("POST", "/dossiers", {"domain": "acme.test"}), 401, "unauthenticated",
             "POST /dossiers without token and without Idempotency-Key [R6-10]")
    c.expect(c.req("POST", "/dossiers/acme.test/refresh", headers={"Authorization": "Bearer nope"}), 401,
             "unauthenticated", "refresh with unknown token and without Idempotency-Key [R6-10]")
    # everyone sees the same dossiers
    bob = c.login("bob@example.com")
    r = c.post(t1, "nowhere-known.test")
    c.expect(r, 202, what="ada POST")
    rb = c.get(bob, "nowhere-known.test")
    c.check(rb.status == 200 and r.body and rb.body.get("dossier_id") == r.body.get("dossier_id"),
            f"bob does not see ada's dossier: {rb!r} [R4-01]")
    lb = c.req("GET", "/dossiers", token=bob)
    c.check(lb.status == 200 and [x.get("domain") for x in lb.body.get("dossiers", [])] == ["nowhere-known.test"],
            f"bob's list {lb!r} [R4-01]")
    c.wait(t1, "nowhere-known.test")
    # tokens do not expire
    c.expect(c.req("POST", "/_test/clock", {"now": ts_plus(T0, days=400)}), 204, what="clock +400 days")
    c.expect(c.req("GET", "/dossiers", token=t1), 200, what="token after 400 days [R6-11]")
    # concurrent signups for one email
    em = f"burst{uid()}@example.com"
    rs = par(10, lambda i: c.req("POST", "/auth/signup", {"email": em, "password": "12345678", "display_name": f"B{i}"}))
    st = sorted(x.status for x in rs)
    c.check(st.count(201) == 1 and st.count(409) == 9, f"10 concurrent signups for one email: statuses {st} [R6-03, R11-01]")


@probe("P05", "R4-02..R4-13 R8-19 R8-20 R8-28 R8-34 R5-09 R5-11", "domain normalisation and validation")
def p05(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    r = c.post(ada, "  WWW.Zephyr-Quantum.TEST. ")
    c.expect(r, 202, what="POST with whitespace, upper case, www. and trailing dot")
    if r.status == 202:
        c.check(r.body.get("domain") == ZEPHYR and r.body.get("state") == "building",
                f"202 body {r.body!r} [R4-03..R4-06, R4-13, R8-15]")
        did = r.body.get("dossier_id")
        for variant in ("zephyr-quantum.test", "Zephyr-Quantum.TEST.", "www.zephyr-quantum.test", " zephyr-quantum.test "):
            g = c.get(ada, variant)
            c.check(g.status == 200 and g.body.get("dossier_id") == did and g.body.get("domain") == ZEPHYR,
                    f"GET {variant!r} -> {g!r} [R4-12, R8-28]")
        r2 = c.post(ada, "zephyr-quantum.test")
        c.check(r2.status == 200 and r2.body.get("dossier_id") == did, f"second POST same company {r2!r} [R4-12, R8-17]")
    r = c.post(ada, "www.www.verifier-www.test")
    c.check(r.status == 202 and (r.body or {}).get("domain") == "www.verifier-www.test",
            f"only one leading www. is removed: {r!r} [R4-06]")
    lab63, lab64 = "a" * 63, "a" * 64
    d253 = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 61])
    d254 = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 62])
    for dom in (f"{lab63}.test", d253, "x-1.test", "1x.test", "acme.test."):
        g = c.get(ada, dom)
        c.expect(g, 404, "not_found", f"GET valid but absent domain {dom[:40]!r} [R4-07..R4-10, R8-28]")
    bad = ["localhost", f"{lab64}.test", d254, "-acme.test", "acme-.test", "a..test", "acme_x.test", "acme.test..",
           ".acme.test", "www.test", "ac me.test", "acme.te$t"]
    for dom in bad:
        g = c.get(ada, dom)
        c.expect(g, 422, "validation_failed", f"GET invalid domain {dom[:40]!r} [R4-07..R4-11]")
        p = c.post(ada, dom)
        c.expect(p, 422, "validation_failed", f"POST invalid domain {dom[:40]!r} [R8-20]")
    for dom in ("https://acme.test", "acme.test/about", "", "   ", "http://www.acme.test/"):
        p = c.post(ada, dom)
        c.expect(p, 422, "validation_failed", f"POST domain {dom!r} [R4-11, R8-20]")
    c.expect(c.refresh(ada, "localhost"), 422, "validation_failed", "refresh invalid path domain [R8-34]")
    c.expect(c.req("POST", "/dossiers", {}, token=ada, key=uid()), 422, "validation_failed", "POST without domain [R8-19]")
    c.expect(c.req("POST", "/dossiers", {"domain": 42}, token=ada, key=uid()), 400, "malformed_request",
             "domain of wrong type [R5-11]")
    c.expect(c.req("POST", "/dossiers", raw="{\"domain\":", token=ada, key=uid()), 400, "malformed_request",
             "malformed body [R5-03]")
    c.wait(ada, ZEPHYR)
    c.wait(ada, "www.verifier-www.test")


def build_and_check(c, token, domain, epoch, exact=None, what="", research_ok=True, timeout=12.0, fresh=True):
    """mock_reset, POST (fresh) or refresh, wait, then INV/EV/LOG. Returns the final dossier."""
    c.mock_reset(epoch)
    before = 0
    if not fresh:
        g = c.get(token, domain)
        before = (g.body or {}).get("spent_units", 0) if g.status == 200 else 0
    t = time.monotonic()
    r = c.post(token, domain) if fresh else c.refresh(token, domain)
    if not c.expect(r, 202, what=f"{what} {'POST' if fresh else 'refresh'} {domain}"):
        return None
    c.check(set(r.body or {}) >= {"dossier_id", "domain", "state"} and r.body.get("state") == "building"
            and r.body.get("domain") == domain, f"{what} 202 body {r.body!r} [R8-15, R8-30]")
    if fresh:
        g = c.get(token, domain)
        if g.status == 200 and g.body.get("state") == "building":
            c.check(all(g.body["fields"][f]["status"] == "unknown" for f in A.FIELDS) and g.body.get("researched_at") is None,
                    f"{what} {domain}: while the first build runs every field must be unknown and researched_at null "
                    f"[R8-24, R8-26]")
        elif g.status != 200:
            c.check(False, f"{what} {domain}: GET right after 202 -> {g!r}")
    d, el = c.wait(token, domain, timeout=max(timeout, 30), start=t)
    if not c.check(d is not None and d.get("state") == "ready", f"{what} {domain}: final state {d!r} [R8-05]"):
        return d
    c.check(el <= timeout, f"{what} {domain}: build took {el:.1f}s > {timeout:.0f}s with mock answers under 1 s [R8-09]")
    c.window(domain, before, d.get("spent_units"), 1, what)
    c.ev(d, epoch, research_ok)
    if exact:
        got = {f: d["fields"][f]["value"] for f in A.FIELDS}
        c.check(got == exact, f"{what} {domain}: fields {got} != {exact}")
    return d


@probe("P06", "R1-01 R1-02 R4-21 R4-22 R4-35 R4-37 R4-45 R8-13 R8-15..R8-17 R8-24 R8-26 R9-* RA-04 RA-10 RA-27 RA-31 RA-35 RA-41",
       "first build of the verifier company zephyr-quantum.test (traps: Facts header, Inc. sentence, negations, EUR)")
def p06(c):
    c.reset()
    ada = c.login("ada@example.com")
    d = build_and_check(c, ada, ZEPHYR, 0, exact=ZEPHYR_E0, what="P06")
    if not d:
        return
    c.check(parse_ts(d["researched_at"]) == parse_ts(T0), f"researched_at {d['researched_at']} != fixture now [R3-16, R8-26]")
    c.mock_reset(0)
    r = c.post(ada, ZEPHYR)
    c.check(r.status == 200 and isinstance(r.body, dict) and {k: r.body.get(k) for k in ("dossier_id", "domain", "state")}
            == {"dossier_id": d["dossier_id"], "domain": ZEPHYR, "state": "ready"},
            f"POST for an existing dossier: {r!r} [R8-17]")
    c.get(ada, ZEPHYR)
    c.req("GET", "/dossiers", token=ada)
    c.req("GET", "/dossiers?q=zeph", token=ada)
    c.login("bob@example.com")
    time.sleep(0.5)
    c.check(c.mock_log() == [], "reads / existing-dossier POST made provider calls [R8-13, R8-17]")


@probe("P07", "R4-28 R4-38 R4-39 R4-40 R4-41 R8-08 R1-05 R9-16 RD-02 RD-08 RA-*",
       "evidence sweep: every corpus company, fields vs. the Appendix A oracle, cost windows")
def p07(c):
    c.reset()
    ada = c.login("ada@example.com")
    for dom in sorted(c.corpus):
        if dom == ZEPHYR:
            continue
        exact = NORDLICHT_E if dom == NORDLICHT else None
        build_and_check(c, ada, dom, 0, exact=exact, what="P07")


@probe("P08", "R8-05 R8-08 R4-39", "company with no evidence ends ready with every field unknown")
def p08(c):
    c.reset()
    ada = c.login("ada@example.com")
    d = build_and_check(c, ada, "nowhere-known.test", 0, what="P08")
    if d:
        c.check(all(d["fields"][f]["status"] == "unknown" for f in A.FIELDS),
                f"unknown company has known fields {d['fields']!r} [R8-08]")


@probe("P09", "R8-43 R8-06 R8-07 R8-26 R9-12 R2-06 R2-07 R5-15", "provider failures: failed builds, partial failures, Tavily absent")
def p09(c):
    c.reset()
    ada = c.login("ada@example.com")
    dom = "ashgrove-solar.test"
    c.mock_reset(0)
    c.mock_fault("nimble", ["search", "extract", "research"], "error")
    c.mock_fault("tavily", ["search", "extract"], "error")
    c.expect(c.post(ada, dom), 202, what="POST with every provider failing")
    d, _ = c.wait(ada, dom, timeout=60)
    if c.check(d and d.get("state") == "failed", f"all provider calls refused: state {d and d.get('state')!r} [R8-06]"):
        c.check(all(d["fields"][f]["status"] == "unknown" for f in A.FIELDS), "failed first build has known fields [R8-24]")
        c.check(d.get("researched_at") is None, f"failed first build researched_at {d.get('researched_at')!r} [R8-26]")
        c.check(d.get("spent_units") == 0, f"refused calls cost nothing but spent_units={d.get('spent_units')} [R9-12]")
    d1 = build_and_check(c, ada, dom, 0, what="P09 recovery", fresh=False)
    if not d1:
        return
    c.expect(c.req("POST", "/_test/clock", {"now": ts_plus(T0, hours=1)}), 204, what="clock")
    c.mock_reset(0)
    c.mock_fault("nimble", ["search", "extract", "research"], "error")
    c.mock_fault("tavily", ["search", "extract"], "error")
    c.expect(c.refresh(ada, dom), 202, what="refresh with every provider failing")
    d2, _ = c.wait(ada, dom, timeout=60)
    if c.check(d2 and d2.get("state") == "failed", f"refresh with all calls refused: {d2 and d2.get('state')!r} [R8-06]"):
        c.check(d2["fields"] == d1["fields"], "failed build changed the fields [R8-07]")
        c.check(d2.get("researched_at") == d1.get("researched_at"), "failed build changed researched_at [R8-07, R8-26]")
        c.check(d2.get("spent_units") == d1.get("spent_units"), "refused calls added to spent_units [R9-12]")
    c.mock_reset(0)
    c.mock_fault("nimble", ["research"], "error")
    c.mock_fault("tavily", ["search", "extract"], "error")
    t = time.monotonic()
    c.expect(c.refresh(ada, dom), 202, what="refresh with only research failing")
    d3, _ = c.wait(ada, dom, timeout=30, start=t)
    if c.check(d3 and d3.get("state") == "ready", f"research refused, searches fine: {d3 and d3.get('state')!r} [R8-06, R2-07]"):
        c.ev(d3, 0, research_ok=False)
        c.check(parse_ts(d3["researched_at"]) == parse_ts(ts_plus(T0, hours=1)), "researched_at of the ready refresh")
    c.mock_reset(0)


@probe("P10", "R8-46 R8-02 R8-04 R8-22 R8-25 R8-26 R8-30..R8-33 R8-03 RD-04 RD-05 R11-02", "refresh: concurrent refreshes, reads during a build, epochs")
def p10(c):
    c.reset()
    ada = c.login("ada@example.com")
    dom = "halvorsen-robotics.test"
    d0 = build_and_check(c, ada, dom, 0, what="P10 first")
    if not d0:
        return
    t1 = ts_plus(T0, hours=1)
    c.req("POST", "/_test/clock", {"now": t1})
    c.mock_reset(0)
    c.mock_fault("nimble", ["research"], "delay", 3)
    r = c.refresh(ada, dom)
    exp = {"dossier_id": d0["dossier_id"], "domain": dom, "state": "building"}
    c.check(r.status == 202 and r.body == exp, f"refresh response {r!r} [R8-30]")
    g = c.get(ada, dom)
    if c.check(g.status == 200 and g.body.get("state") == "building", f"read during refresh {g!r} [R8-22]"):
        c.check(g.body["fields"] == d0["fields"], "fields changed while a later build runs [R8-25]")
        c.check(g.body.get("researched_at") == d0.get("researched_at"), "researched_at changed while building [R8-26]")
    li = c.req("GET", "/dossiers?q=halvorsen", token=ada)
    if c.check(li.status == 200 and len(li.body.get("dossiers", [])) == 1, f"list during refresh {li!r}"):
        it = li.body["dossiers"][0]
        c.check(it.get("state") == "building" and it.get("legal_name") == d0["fields"]["legal_name"]["value"]
                and it.get("researched_at") == d0.get("researched_at"),
                f"list item during a refresh {it} must show building + last ready legal_name/researched_at [R8-46]")
    rs = par(10, lambda i: c.refresh(ada, dom))
    c.check(all(x.status == 202 and x.body == exp for x in rs),
            f"10 concurrent refreshes during a build: {[x.status for x in rs]} {rs[0]!r} [R8-31]")
    d1, _ = c.wait(ada, dom, timeout=30)
    if c.check(d1 and d1.get("state") == "ready", f"refresh result {d1!r}"):
        c.window(dom, d0["spent_units"], d1["spent_units"], 1, "P10 refresh (one build despite 11 refreshes)")
        c.check(d1["spent_units"] > d0["spent_units"], "refresh made no provider call [R8-32]")
        c.check(parse_ts(d1["researched_at"]) == parse_ts(t1), f"researched_at {d1['researched_at']} != {t1} [R8-03]")
        calls = [x for x in c.mock_log() if x.get("method") == "research"]
        c.check(len(calls) <= 1, f"{len(calls)} research runs for one build [R8-04, R8-31]")
    # epoch 1: refresh researches again and sees the new web
    d2 = build_and_check(c, ada, dom, 1, what="P10 epoch1", fresh=False)
    z = build_and_check(c, ada, ZEPHYR, 0, exact=ZEPHYR_E0, what="P10 zephyr e0")
    if z:
        build_and_check(c, ada, ZEPHYR, 1, exact=ZEPHYR_E1, what="P10 zephyr e1", fresh=False)
    c.expect(c.refresh(ada, "absent-company.test"), 404, "not_found", "refresh of unknown dossier [R8-33]")
    c.mock_reset(0)


@probe("P11", "R7-01..R7-17 R5-04 R5-07 R5-12 R8-14 R8-17 R8-18 R8-29 RD-06 R11-01", "idempotency, replays, concurrent identical writes")
def p11(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    bob = c.login("bob@example.com")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-a.test"}, token=ada), 400, "missing_idempotency_key", "no key [R7-06]")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-a.test"}, token=ada, key=""), 400, "missing_idempotency_key",
             "empty key [R7-06]")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-a.test"}, token=ada, key="k" * 256), 422, "validation_failed",
             "256-char key [R5-12]")
    c.expect(c.req("POST", "/dossiers/idem-a.test/refresh", token=ada), 400, "missing_idempotency_key",
             "refresh without key [R8-29]")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-a.test"}, token=ada, key="k" * 255), 202, what="255-char key [R5-12]")
    K1 = "K1-" + uid()
    b1 = c.req("POST", "/dossiers", {"domain": "idem-b.test"}, token=ada, key=K1)
    c.expect(b1, 202, what="first use [R7-07]")
    rp = c.req("POST", "/dossiers", {"domain": "idem-b.test"}, token=ada, key=K1)
    c.check(rp.status == 200 and rp.body == b1.body, f"immediate replay {rp!r} vs {b1!r} [R7-08, RD-06]")
    c.wait(ada, "idem-b.test")
    c.wait(ada, "idem-a.test")
    c.mock_reset(0)
    rp = c.req("POST", "/dossiers", {"domain": "idem-b.test"}, token=ada, key=K1)
    c.check(rp.status == 200 and rp.body == b1.body,
            f"replay after the build finished must return the original (building) body: {rp!r} [R7-15]")
    rp = c.req("POST", "/dossiers", token=ada, key=K1, raw='{ "extra" : [1, 2] ,\n  "domain":"idem-b.test" }')
    c.check(rp.status == 200 and rp.body == b1.body, f"replay with other order/whitespace/unknown field {rp!r} [R7-11, R7-12]")
    time.sleep(0.5)
    c.check(c.mock_log() == [], "a replay made a provider call [R7-16]")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-c.test"}, token=ada, key=K1), 409, "idempotency_key_reuse",
             "same key, other body [R7-09]")
    c.expect(c.req("POST", "/dossiers", {"domain": "Idem-B.test"}, token=ada, key=K1), 409, "idempotency_key_reuse",
             "same key, domain spelled differently in the body [R7-05]")
    c.expect(c.req("POST", "/dossiers", {"domain": "not a domain"}, token=ada, key=K1), 409, "idempotency_key_reuse",
             "claimed key with an invalid body [R7-17]")
    c.expect(c.req("POST", "/dossiers", {}, token=ada, key=K1), 409, "idempotency_key_reuse",
             "claimed key with a body lacking domain [R7-17]")
    c.expect(c.req("POST", "/dossiers", raw="{oops", token=ada, key=K1), 400, "malformed_request",
             "claimed key with unparseable body [R7-17]")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-b.test"}, key=K1), 401, "unauthenticated",
             "claimed key without token")
    K2 = "K2-" + uid()
    c.expect(c.req("POST", "/dossiers", {"domain": "bad domain"}, token=ada, key=K2), 422, "validation_failed", "4xx first")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-d.test"}, token=ada, key=K2), 202,
             what="key reused after a 4xx is a first use [R7-10]")
    c.expect(c.req("POST", "/dossiers", {"domain": "idem-e.test"}, token=bob, key=K1), 202,
             what="another user, same key string [R7-02]")
    rr = c.refresh(ada, "idem-b.test", key=K1)
    c.expect(rr, 202, what="same key on another path (refresh) [R7-04]")
    rp = c.refresh(ada, "idem-b.test", key=K1)
    c.check(rp.status == 200 and rp.body == rr.body, f"refresh replay {rp!r} [R7-08]")
    K3 = "K3-" + uid()
    c.expect(c.refresh(ada, "idem-b.test", key=K3), 202, what="refresh K3")
    rk = c.refresh(ada, "IDEM-B.test", key=K3)
    c.expect(rk, 202, what="same key on a path spelled differently is a new request, not a 200 replay [R7-05]")
    c.check((rk.body or {}).get("domain") == "idem-b.test", f"refresh path is normalised: {rk!r} [R8-45]")
    c.wait(ada, "idem-d.test")
    K4 = "K4-" + uid()
    r4 = c.refresh(ada, "idem-d.test", key=K4, body={"a": 1})
    c.expect(r4, 202, what="refresh with a body")
    rp = c.refresh(ada, "idem-d.test", key=K4, body={"b": 2})
    c.check(rp.status == 200 and rp.body == r4.body, f"refresh body is ignored for replay {rp!r} [R7-13]")
    rp = c.refresh(ada, "idem-d.test", key=K4)
    c.check(rp.status == 200 and rp.body == r4.body, f"refresh replay without body {rp!r} [R7-13]")
    for d in ("idem-b.test", "idem-d.test", "idem-e.test"):
        c.wait(ada, d, timeout=30)
    # burst: identical requests, unused key
    c.mock_reset(0)
    K5 = "K5-" + uid()
    rs = par(20, lambda i: c.req("POST", "/dossiers", {"domain": "idem-f.test"}, token=ada, key=K5))
    st = sorted(x.status for x in rs)
    c.check(st.count(202) == 1 and st.count(200) == 19, f"20 identical concurrent POSTs: {st} [R7-14]")
    bodies = {json.dumps(x.body, sort_keys=True) for x in rs}
    c.check(len(bodies) == 1, f"identical concurrent POSTs returned different bodies {bodies} [R7-14]")
    d, _ = c.wait(ada, "idem-f.test", timeout=30)
    if d:
        c.window("idem-f.test", 0, d.get("spent_units"), 1, "P11 identical burst")
    # burst: same domain, distinct keys
    c.mock_reset(0)
    rs = par(20, lambda i: c.req("POST", "/dossiers", {"domain": "idem-g.test"}, token=ada, key=f"K6-{i}-{uid()}"))
    st = sorted(x.status for x in rs)
    c.check(st.count(202) == 1 and st.count(200) == 19, f"20 concurrent POSTs one domain, distinct keys: {st} [R8-18]")
    ids = {(x.body or {}).get("dossier_id") for x in rs}
    c.check(len(ids) == 1, f"one domain got several dossier ids {ids} [R8-18]")
    d, _ = c.wait(ada, "idem-g.test", timeout=30)
    if d:
        c.window("idem-g.test", 0, d.get("spent_units"), 1, "P11 same-domain burst")
    l = c.req("GET", "/dossiers?q=idem-g", token=ada)
    c.check(l.status == 200 and len(l.body.get("dossiers", [])) == 1, f"list after burst {l!r} [R8-18]")


@probe("P12", "R8-35..R8-42 R5-10 R5-13 R5-14 R3-27", "listing: q, order, limit, offset, has_more")
def p12(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    c.post(ada, ZEPHYR)
    c.wait(ada, ZEPHYR)
    doms = [f"list-{i:02d}.test" for i in range(52)]
    for chunk in range(0, len(doms), 13):
        part = doms[chunk:chunk + 13]
        rs = par(len(part), lambda i: c.post(ada, part[i]))
        c.check(all(x.status == 202 for x in rs), f"bulk create statuses {[x.status for x in rs]}")
    alld = sorted(doms + [ZEPHYR])
    r = c.req("GET", "/dossiers", token=ada)
    if c.expect(r, 200, what="list default"):
        got = [x.get("domain") for x in r.body.get("dossiers", [])]
        c.check(got == alld[:50] and r.body.get("has_more") is True, f"default list: {len(got)} items, has_more "
                f"{r.body.get('has_more')} [R8-39, R8-40, R8-41, R8-42]")
        for x in r.body.get("dossiers", []):
            c.check(set(x) >= {"dossier_id", "domain", "state", "legal_name", "researched_at", "spent_units"},
                    f"list item keys {sorted(x)} [R8-35]")
            if x.get("domain", "").startswith("list-"):
                c.check(x.get("legal_name") is None, f"{x.get('domain')}: legal_name {x.get('legal_name')!r} without evidence [R8-36]")
    r = c.req("GET", "/dossiers?limit=200&offset=0", token=ada)
    if c.expect(r, 200, what="limit=200"):
        c.check([x["domain"] for x in r.body["dossiers"]] == alld and r.body["has_more"] is False, "limit=200 list [R8-39]")
    r = c.req("GET", "/dossiers?limit=50&offset=50", token=ada)
    if c.expect(r, 200, what="offset=50"):
        c.check([x["domain"] for x in r.body["dossiers"]] == alld[50:] and r.body["has_more"] is False, "offset 50 [R8-42]")
    r = c.req("GET", "/dossiers?limit=1", token=ada)
    if c.expect(r, 200, what="limit=1"):
        c.check([x["domain"] for x in r.body["dossiers"]] == alld[:1] and r.body["has_more"] is True, "limit 1 [R8-42]")
    r = c.req("GET", f"/dossiers?limit=10&offset={len(alld)}", token=ada)
    if c.expect(r, 200, what="offset at end"):
        c.check(r.body["dossiers"] == [] and r.body["has_more"] is False, "offset at end [R8-42]")
    r = c.req("GET", "/dossiers?q=LIST-0&limit=200", token=ada)
    if c.expect(r, 200, what="q upper case"):
        c.check([x["domain"] for x in r.body["dossiers"]] == [f"list-0{i}.test" for i in range(10)],
                f"q=LIST-0 -> {[x['domain'] for x in r.body['dossiers']]} [R8-37]")
    r = c.req("GET", "/dossiers?q=" + urllib.parse.quote("systems gmbh"), token=ada)
    if c.expect(r, 200, what="q on legal_name"):
        items = r.body["dossiers"]
        c.check([x["domain"] for x in items] == [ZEPHYR], f"q matching only legal_name -> {items} [R8-37]")
        if items:
            g = c.get(ada, ZEPHYR).body
            c.check(items[0].get("legal_name") == g["fields"]["legal_name"]["value"] == ZEPHYR_E0["legal_name"]
                    and items[0].get("researched_at") == g.get("researched_at")
                    and items[0].get("spent_units") == g.get("spent_units")
                    and items[0].get("dossier_id") == g.get("dossier_id"), f"list item vs GET {items[0]} [R8-36]")
    r = c.req("GET", "/dossiers?q=&limit=200", token=ada)
    if c.expect(r, 200, what="empty q"):
        c.check(len(r.body["dossiers"]) == len(alld), f"empty q lists {len(r.body['dossiers'])} [R8-38]")
    r = c.req("GET", "/dossiers?q=no-such-thing", token=ada)
    if c.expect(r, 200, what="q no match"):
        c.check(r.body["dossiers"] == [] and r.body["has_more"] is False, "q with no match")
    for qs in ("limit=0", "limit=201", "limit=-1", "limit=abc", "limit=1e9", "limit=4.0", "limit=%2B4", "limit=",
               "offset=-1", "offset=1.5", "offset=%2B0", "offset=abc", "offset=1e2"):
        c.expect(c.req("GET", "/dossiers?" + qs, token=ada), 422, "validation_failed", f"GET /dossiers?{qs} [R5-10, R5-13, R5-14]")
    c.expect(c.req("GET", "/dossiers?limit=200&offset=0&sort=desc", token=ada), 200, what="unknown query param [R3-27]")
    c.reset()  # cut the bulk builds (also exercises R3-13)


@probe("P13", "R2-23 R2-24 R5-15 R11-01 R11-02", "50 requests in flight; every read during builds satisfies the invariants")
def p13(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    c.post(ada, "mosaic-freight.test")

    def one(i):
        k = i % 5
        if k == 0:
            return c.req("GET", "/dossiers", token=ada)
        if k == 1:
            return c.get(ada, "mosaic-freight.test")
        if k == 2:
            return c.post(ada, f"load-{i:02d}.test")
        if k == 3:
            return c.req("POST", "/auth/signup", {"email": f"l{i}{uid()}@example.com", "password": "12345678",
                                                   "display_name": "L"})
        return c.req("POST", "/auth/login", {"email": "bob@example.com", "password": PW})
    rs = par(50, one)
    exp = {0: (200,), 1: (200,), 2: (202,), 3: (201,), 4: (200,)}
    for i, x in enumerate(rs):
        c.check(x.status in exp[i % 5], f"burst request {i} -> {x!r}")
        c.check(x.elapsed < 5, f"burst request {i} took {x.elapsed:.1f}s [R2-24]")
    deadline = time.monotonic() + 120
    pending = {f"load-{i:02d}.test" for i in range(50) if i % 5 == 2} | {"mosaic-freight.test"}
    while pending and time.monotonic() < deadline:
        for dname in list(pending):
            g = c.get(ada, dname)
            if g.status == 200 and g.body.get("state") != "building":
                pending.discard(dname)
        time.sleep(0.3)
    c.check(not pending, f"builds still running after 120 s: {sorted(pending)}")
    l = c.req("GET", "/dossiers?limit=200", token=ada)
    if l.status == 200:
        ds = [x["domain"] for x in l.body["dossiers"]]
        c.check(len(ds) == len(set(ds)) == 11, f"dossiers after burst: {ds}")
    calls = c.mock_log()
    total = sum(x.get("cost") or 0 for x in calls)
    spent = sum(x.get("spent_units", 0) for x in l.body.get("dossiers", [])) if l.status == 200 else -1
    c.check(total == spent, f"sum of spent_units {spent} != call log cost {total} over 11 builds [R8-27]")
    c.check(total <= 80 * 11, f"11 builds cost {total} [R1-07]")


@probe("P14", "R3-13", "reset while a build is running")
def p14(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    c.mock_fault("nimble", ["research"], "delay", 4)
    c.mock_fault("nimble", ["search"], "delay", 1.5)
    c.expect(c.post(ada, ZEPHYR), 202, what="POST")
    time.sleep(0.5)
    r = c.reset()
    c.check(r.elapsed < 10, f"reset during a build took {r.elapsed:.1f}s")
    ada = c.login("ada@example.com")
    c.expect(c.get(ada, ZEPHYR), 404, "not_found", "dossier right after reset [R3-13]")
    time.sleep(9)
    c.expect(c.get(ada, ZEPHYR), 404, "not_found", "dossier after the old build would have finished [R3-13]")
    l = c.req("GET", "/dossiers", token=ada)
    c.check(l.status == 200 and l.body.get("dossiers") == [], f"list after the old build finished {l!r} [R3-13]")
    d = build_and_check(c, ada, ZEPHYR, 0, exact=ZEPHYR_E0, what="P14 rebuild")
    if d:
        c.check(parse_ts(d["researched_at"]) == parse_ts(T0), "researched_at of rebuilt dossier")


@probe("P15", "R10-01..R10-29 R6-13 R8-13", "export / import")
def p15(c):
    c.reset()
    c.mock_reset(0)
    ada = c.login("ada@example.com")
    a2 = c.login("ada@example.com")
    carol_pw = "carol-" + uid()
    tc, carol, carol_id = c.signup(pw=carol_pw, name="Carol")
    Ke1 = "Ke1-" + uid()
    e1 = c.req("POST", "/dossiers", {"domain": ZEPHYR}, token=ada, key=Ke1)
    c.expect(e1, 202, what="POST zephyr")
    z, _ = c.wait(ada, ZEPHYR)
    c.mock_fault("nimble", ["search", "extract", "research"], "error")
    c.mock_fault("tavily", ["search", "extract"], "error")
    c.post(ada, "ashgrove-solar.test")
    f, _ = c.wait(ada, "ashgrove-solar.test", timeout=60)
    c.mock_reset(0)
    c.check(f and f.get("state") == "failed", f"setup: failed dossier {f and f.get('state')}")
    Ke3 = "Ke3-" + uid()
    c.expect(c.req("POST", "/dossiers", {"domain": "bad domain"}, token=ada, key=Ke3), 422, "validation_failed", "failed key")
    t5 = ts_plus(T0, hours=5)
    c.req("POST", "/_test/clock", {"now": t5})
    x = c.req("GET", "/_test/export")
    if not c.expect(x, 200, what="export [R10-01]"):
        return
    X = x.body
    c.check(isinstance(X, dict) and X.get("track") == "dossier" and X.get("format_version") == 1
            and isinstance(X.get("state"), dict), f"export envelope keys {list(X) if isinstance(X, dict) else X!r} [R10-02]")
    c.check(PW not in x.text and carol_pw not in x.text, "export contains a plaintext password [R6-13]")
    c.expect(c.req("GET", "/_test/export"), 200, what="second export")
    time.sleep(0.3)
    c.check(c.mock_log() == [], "export made a provider call [R8-13]")
    # writes after the export
    td, dave, _ = c.signup(name="Dave")
    c.post(ada, NORDLICHT)
    c.wait(ada, NORDLICHT)
    t6 = ts_plus(T0, hours=6)
    c.req("POST", "/_test/clock", {"now": t6})
    c.mock_reset(0)
    r = c.req("POST", "/_test/import", X)
    c.expect(r, 204, what="import [R10-04]")
    ada_l = c.req("GET", "/dossiers?limit=200", token=ada)
    c.check(ada_l.status == 200 and sorted(i["domain"] for i in ada_l.body.get("dossiers", [])) ==
            ["ashgrove-solar.test", ZEPHYR], f"list after import {ada_l!r} [R10-06, R10-10, R10-23]")
    zi = c.get(ada, ZEPHYR).body or {}
    for k in ("dossier_id", "state", "fields", "researched_at", "spent_units"):
        c.check(zi.get(k) == z.get(k), f"zephyr {k} after import {zi.get(k)!r} != {z.get(k)!r} [R10-13..R10-17, R10-19]")
    fi = c.get(ada, "ashgrove-solar.test").body or {}
    c.check(fi.get("state") == "failed" and fi.get("dossier_id") == f.get("dossier_id") and fi.get("fields") == f.get("fields"),
            f"failed dossier after import {fi.get('state')!r} [R10-14]")
    r = c.req("POST", "/auth/login", {"email": carol, "password": carol_pw})
    c.check(r.status == 200 and r.body.get("user_id") == carol_id, f"carol login after import {r!r} [R10-11, R10-19]")
    for t, who in ((tc, "carol"), (a2, "ada second token"), (ada, "ada")):
        c.expect(c.req("GET", "/dossiers", token=t), 200, what=f"{who} token after import [R10-12, R10-22]")
    c.expect(c.req("POST", "/auth/login", {"email": dave, "password": "pw-" + "x" * 8}), 401, "unauthenticated",
             "user created after the export [R10-23]")
    c.expect(c.req("GET", "/dossiers", token=td), 401, "unauthenticated", "token created after the export [R10-23]")
    time.sleep(0.3)
    c.check(c.mock_log() == [], "import or reads after it made a provider call [R10-20]")
    rp = c.req("POST", "/dossiers", {"domain": ZEPHYR}, token=ada, key=Ke1)
    c.check(rp.status == 200 and rp.body == e1.body, f"replay after import {rp!r} vs {e1.body!r} [R10-18, R10-22]")
    c.expect(c.req("POST", "/dossiers", {"domain": NORDLICHT}, token=ada, key=Ke1), 409, "idempotency_key_reuse",
             "claimed key after import with another body [R10-18]")
    r = c.req("POST", "/dossiers", {"domain": "windrush-bakery.test"}, token=ada, key=Ke3)
    c.expect(r, 202, what="failed key reusable after import [R10-21]")
    w, _ = c.wait(ada, "windrush-bakery.test")
    if w and w.get("researched_at"):
        c.check(parse_ts(w["researched_at"]) == parse_ts(t6), f"clock after export/import: researched_at "
                f"{w['researched_at']} != {t6} [R10-25]")
    r = c.req("POST", "/_test/import", X)
    c.expect(r, 204, what="second import")
    l2 = c.req("GET", "/dossiers?limit=200", token=ada)
    c.check(l2.status == 200 and sorted(i["domain"] for i in l2.body["dossiers"]) == ["ashgrove-solar.test", ZEPHYR],
            f"repeat import {l2!r} [R10-06]")
    # invalid imports change nothing
    for body, raw, why, codes in [(None, "{not json", "invalid JSON", (400,)),
                                  ({}, None, "empty object", (422,)),
                                  (dict(X, track="other"), None, "wrong track", (422,)),
                                  (dict(X, format_version=2), None, "wrong version", (422,)),
                                  ({"track": "dossier", "format_version": 1}, None, "missing state", (422,)),
                                  (dict(X, state="nope"), None, "invalid state", (422, 400))]:
        r = c.req("POST", "/_test/import", body, raw=raw)
        c.check(r.status in codes, f"import {why}: {r!r} [R10-07, R10-08]")
    l3 = c.req("GET", "/dossiers?limit=200", token=ada)
    c.check(l3.status == 200 and sorted(i["domain"] for i in l3.body["dossiers"]) == ["ashgrove-solar.test", ZEPHYR],
            f"state changed by a rejected import {l3!r} [R10-08]")
    c.expect(c.req("POST", "/auth/login", {"email": carol, "password": carol_pw}), 200, what="carol after rejected imports")
    # export during a build
    c.mock_reset(0)
    c.mock_fault("nimble", ["research"], "delay", 4)
    c.expect(c.refresh(ada, ZEPHYR), 202, what="refresh zephyr")
    c.expect(c.post(ada, NORDLICHT), 202, what="POST nordlicht")
    time.sleep(0.5)
    y = c.req("GET", "/_test/export")
    c.expect(y, 200, what="export during builds")
    c.wait(ada, ZEPHYR, timeout=30)
    c.wait(ada, NORDLICHT, timeout=30)
    c.mock_reset(0)
    c.expect(c.req("POST", "/_test/import", y.body), 204, what="import of the mid-build export")
    zi = c.get(ada, ZEPHYR).body or {}
    c.check(zi.get("state") == "ready" and zi.get("fields") == z.get("fields") and zi.get("researched_at") == z.get("researched_at")
            and zi.get("spent_units") == z.get("spent_units"),
            f"mid-build export must hold zephyr as before the refresh: {zi.get('state')} {zi.get('spent_units')} [R10-27, R10-28]")
    ni = c.get(ada, NORDLICHT).body or {}
    c.check(ni.get("state") == "failed" and all(ni["fields"][k]["status"] == "unknown" for k in A.FIELDS)
            and ni.get("researched_at") is None,
            f"dossier with no completed build after import must be failed/unknown: {ni.get('state')!r} [R10-28]")
    if ni.get("spent_units") != 0:
        c.note_once(f"mid-build export kept spent_units={ni.get('spent_units')} for a dossier whose first build was "
                    f"running (R10-27 reads 'as it was before that build')")
    d = build_and_check(c, ada, NORDLICHT, 0, exact=NORDLICHT_E, what="P15 refresh after import", fresh=False)
    c.reset()
    c.expect(c.req("POST", "/auth/login", {"email": carol, "password": carol_pw}), 401, "unauthenticated",
             "imported user after reset [R10-24]")
    ada = c.login("ada@example.com")
    l4 = c.req("GET", "/dossiers", token=ada)
    c.check(l4.status == 200 and l4.body.get("dossiers") == [], f"imported dossiers after reset {l4!r} [R10-24]")


@probe("P17", "R8-09 R9-13 RD-04", "build bound with every Nimble call taking 0.8 s")
def p17(c):
    c.reset()
    ada = c.login("ada@example.com")
    c.mock_reset(0)
    c.mock_fault("nimble", ["search", "extract", "research"], "delay", 0.8)
    t = time.monotonic()
    r = c.post(ada, "corvid-security.test")
    c.expect(r, 202, what="POST corvid")
    d, el = c.wait(ada, "corvid-security.test", timeout=40, start=t)
    if c.check(d and d.get("state") == "ready", f"slow-provider build {d and d.get('state')!r}"):
        c.check(el <= 10.5, f"build with 0.8 s provider answers took {el:.1f}s > 10 s [R8-09]")
        c.window("corvid-security.test", 0, d.get("spent_units"), 1, "P17")
        c.ev(d, 0)
    c.mock_reset(0)


@probe("P18", "R4-29 R4-31", "a refused domain search does not count: exactly one successful domain search (throttled provider)")
def p18(c):
    c.reset()
    ada = c.login("ada@example.com")
    c.mock_reset(0)
    c.mock_fault("nimble", ["search"], "throttle")
    c.expect(c.post(ada, "mosaic-freight.test"), 202, what="POST")
    d, _ = c.wait(ada, "mosaic-freight.test", timeout=60)
    calls = c.mock_log()
    ok = [x for x in calls if x.get("method") == "search" and x.get("status") == 200 and x.get("query") == "mosaic-freight.test"]
    c.check(len(ok) == 1, f"{len(ok)} successful searches with query == domain while the provider throttles [R4-29, R4-31]")
    c.check(d and d.get("state") == "ready", f"state {d and d.get('state')!r}")
    c.mock_reset(0)


# ---------------------------------------------------------------- final citation provenance check

def served_check(c):
    c.capture_log()
    bad = []
    for (url, ex, prov), (dom, field, val, pid) in sorted(c.citations.items()):
        ents = c.served.get(url, [])
        hit = any(p == prov and excerpt_in(ex, prose_of(p, m, dp, t)) for p, m, dp, t in ents)
        if not hit:
            any_prov = any(excerpt_in(ex, prose_of(p, m, dp, t)) for p, m, dp, t in ents)
            in_header = any(excerpt_in(ex, t) for p, m, dp, t in ents)
            why = ("served by the other provider" if any_prov else
                   "found only in a page header" if in_header else
                   "never served for this url" if ents else "no text was ever served for this url")
            bad.append(f"[{pid}] {dom} {field}={val!r}: excerpt {ex!r} @ {url} ({prov}): {why}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", default=os.environ.get("SERVICE_URL", "http://svc:8080"))
    ap.add_argument("--mock", default=os.environ.get("MOCK_URL", "http://web:8080"))
    ap.add_argument("--admin", default=os.environ.get("MOCK_ADMIN_TOKEN", "local-admin"))
    ap.add_argument("--corpus", default=os.environ.get("CORPUS_DIR", "/corpus"))
    ap.add_argument("--only", default=os.environ.get("PROBE_ONLY", ""))
    args = ap.parse_args()
    import test_appendix_a
    if test_appendix_a.main() != 0:
        print("oracle self-test failed; aborting")
        return 2
    c = Ctx(args)
    t = time.monotonic()
    while time.monotonic() - t < 60:
        if c._http(c.mock, "GET", "/_mock/health", timeout=2.0).status == 200:
            break
        time.sleep(0.5)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    results = []
    for pid, rows, title, fn in PROBES:
        if only and pid not in only:
            continue
        c.current, c.fail = pid, []
        t = time.monotonic()
        try:
            fn(c)
        except Exception:
            c.fail.append("probe crashed: " + traceback.format_exc(limit=3).replace("\n", " | "))
        el = time.monotonic() - t
        results.append((pid, not c.fail))
        print(f"{'PASS' if not c.fail else 'FAIL'} {pid} ({el:.0f}s) {title}  [{rows}]", flush=True)
        for m in c.fail[:40]:
            print(f"     - {m}", flush=True)
        if len(c.fail) > 40:
            print(f"     ... {len(c.fail) - 40} more", flush=True)
    c.current = "SERVED"
    try:
        bad = served_check(c)
    except Exception:
        bad = ["served check crashed: " + traceback.format_exc(limit=3)]
    results.append(("SERVED", not bad))
    print(f"{'PASS' if not bad else 'FAIL'} SERVED every cited excerpt was served for its url, from prose, by the named provider "
          f"({len(c.citations)} citations) [R1-05 R1-06 R4-26 R4-27 R4-33 R4-35 RD-08]")
    for m in bad[:40]:
        print("     - " + m)
    results.append(("G", not c.global_viol))
    print(f"{'PASS' if not c.global_viol else 'FAIL'} G global response checks: no 5xx, error envelope, JSON content type, "
          f"answers within the timeout [R5-01 R5-15 R3-24 R2-24]")
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
