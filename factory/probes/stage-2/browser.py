#!/usr/bin/env python3
"""Verifier black-box probes for dossier stage 2: the screens, in a real headless Chromium.

Drives the UI only through the data-testid attributes of stage-2.md and checks what it shows
against the API (read with a bearer token, as any client would). Provider calls are observed
through the mock admin log. Each probe names its ledger rows (factory/ledger/stage-2.md).

  python3 browser.py --service http://svc:8080 --service1 http://svc1:8080 --mock http://web:8080 \
                     --admin local-admin --corpus /corpus --shots /logs/shots [--only B06]
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
import traceback
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run2  # noqa: E402  (stage-2 API helpers, INV2; imports the stage-1 probes)

from playwright.async_api import async_playwright  # noqa: E402

s1, A = run2.s1, run2.A
FIELDS = run2.FIELDS
ZEPHYR, KESTREL, NORD = s1.ZEPHYR, run2.KESTREL, s1.NORDLICHT
FAILED = "ashgrove-solar.test"
T = 15000  # ms


class B:
    def __init__(self, args):
        self.args = args
        self.c = run2.Ctx2(args)
        self.base = args.service.rstrip("/")
        self.shots = args.shots
        os.makedirs(self.shots, exist_ok=True)
        self.host = urllib.parse.urlparse(self.base).netloc

    def check(self, cond, msg):
        return self.c.check(cond, msg)

    async def api(self, fn, *a, **kw):
        return await asyncio.to_thread(fn, *a, **kw)

    # ------------------------------------------------------------ browser helpers
    async def page(self, browser, width=1280, height=900):
        ctx = await browser.new_context(viewport={"width": width, "height": height}, base_url=self.base)
        ctx.set_default_timeout(10000)
        page = await ctx.new_page()
        page.reqlog = []
        page.foreign = []

        def on_req(r):
            page.reqlog.append((time.monotonic(), r.method, r.url, r.resource_type, r.headers, r.post_data))
            host = urllib.parse.urlparse(r.url).netloc
            if host and host != self.host and not r.url.startswith(("data:", "blob:", "about:")):
                page.foreign.append(r.url)
        page.on("request", on_req)
        return page

    async def present(self, page, tid, timeout=T):
        try:
            await page.get_by_test_id(tid).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    async def absent(self, page, tid, timeout=3000):
        try:
            await page.get_by_test_id(tid).first.wait_for(state="hidden", timeout=timeout)
            return True
        except Exception:
            return False

    async def count(self, page, tid):
        return await page.get_by_test_id(tid).count()

    async def text(self, page, tid):
        return (await page.get_by_test_id(tid).first.inner_text()).strip()

    async def attr(self, page, tid, name):
        return await page.get_by_test_id(tid).first.get_attribute(name)

    async def login(self, page, email="ada@example.com", pw=s1.PW, name="Ada"):
        await page.goto("/login")
        if not await self.present(page, "login-email"):
            self.check(False, "login-email not shown on /login [Q10-02]")
            return None
        await page.get_by_test_id("login-email").fill(email)
        await page.get_by_test_id("login-password").fill(pw)
        async with page.expect_response(lambda r: r.url.endswith("/auth/login"), timeout=T) as ri:
            await page.get_by_test_id("login-submit").click()
        resp = await ri.value
        ok = await self.present(page, "current-user")
        self.check(ok and name in await self.text(page, "current-user"), "current-user missing or lacks the display name "
                                                                        "after login [Q10-04]")
        try:
            return (await resp.json()).get("token")
        except Exception:
            return None

    async def ids(self, page, container, prefix):
        loc = page.locator(f'[data-testid="{container}"] [data-testid^="{prefix}"]')
        out = []
        for i in range(await loc.count()):
            out.append(await loc.nth(i).get_attribute("data-testid"))
        return out

    async def shot(self, page, name):
        try:
            await page.screenshot(path=os.path.join(self.shots, name + ".png"), full_page=True)
        except Exception:
            pass

    def reads(self, page, dom, since=0.0):
        return [t for t, m, u, rt, h, b in page.reqlog
                if t >= since and m == "GET" and rt in ("fetch", "xhr")
                and urllib.parse.urlparse(u).path.rstrip("/").lower() == f"/dossiers/{dom}"]

    # ------------------------------------------------------------ API setup
    def setup(self, domains=(ZEPHYR, KESTREL, NORD), failed=True):
        c = self.c
        c.reset()
        c.mock_reset(0)
        ada = c.login("ada@example.com")
        for d in domains:
            c.post(ada, d)
            c.wait(ada, d, timeout=30)
        if failed:
            c.mock_fault("nimble", ["search", "extract", "research"], "error")
            c.post(ada, FAILED)
            c.wait(ada, FAILED, timeout=60)
            c.mock_reset(0)
        return ada


PROBES = []


def probe(pid, rows, title):
    def deco(fn):
        PROBES.append((pid, rows, title, fn))
        return fn
    return deco


@probe("B02", "Q8-08 Q10-02 Q10-03 Q10-04 Q10-05 QD-18", "login, auth-error, logout; signed-out visitor goes to /login")
async def b02(b, browser):
    await b.api(b.setup, (), False)
    page = await b.page(browser)
    await page.goto("/")
    await page.wait_for_timeout(1500)
    b.check(urllib.parse.urlparse(page.url).path == "/login", f"signed-out visitor to / ended at {page.url} [QD-18]")
    await page.goto("/login")
    b.check(await b.count(page, "auth-error") == 0, "auth-error present before any error [Q10-03]")
    await page.get_by_test_id("login-email").fill("ada@example.com")
    await page.get_by_test_id("login-password").fill("wrong password")
    await page.get_by_test_id("login-submit").click()
    b.check(await b.present(page, "auth-error"), "no auth-error after a wrong password [Q10-03]")
    await b.shot(page, "login-error")
    await b.login(page)
    b.check(await b.count(page, "auth-error") == 0, "auth-error still present after a successful login [Q10-03]")
    if await b.present(page, "logout-button"):
        await page.get_by_test_id("logout-button").click()
        b.check(await b.absent(page, "current-user"), "current-user still shown after logout [Q10-05]")
        await page.goto("/")
        await page.wait_for_timeout(1500)
        b.check(urllib.parse.urlparse(page.url).path == "/login", f"after logout / ends at {page.url} [QD-18]")
    else:
        b.check(False, "no logout-button when signed in [Q10-05]")
    await page.context.close()


@probe("B03", "Q8-07 Q10-01 Q10-03 Q10-04", "signup")
async def b03(b, browser):
    await b.api(b.setup, (), False)
    page = await b.page(browser)
    await page.goto("/signup")
    if not await b.present(page, "signup-email"):
        b.check(False, "signup inputs missing [Q10-01]")
        return
    b.check(await b.count(page, "auth-error") == 0, "auth-error present before any error [Q10-03]")
    await page.get_by_test_id("signup-email").fill("ada@example.com")
    await page.get_by_test_id("signup-password").fill("long enough pw")
    await page.get_by_test_id("signup-display-name").fill("Dup")
    await page.get_by_test_id("signup-submit").click()
    b.check(await b.present(page, "auth-error"), "no auth-error for an email already registered [Q10-03]")
    await page.get_by_test_id("signup-email").fill("newbie@example.com")
    await page.get_by_test_id("signup-display-name").fill("Newbie Person")
    await page.get_by_test_id("signup-submit").click()
    ok = await b.present(page, "current-user")
    b.check(ok and "Newbie Person" in await b.text(page, "current-user"), "signed-up user not shown in current-user [Q10-04]")
    await page.context.close()


@probe("B04", "Q8-03 Q11-05..Q11-08 Q9-14", "dossier list: order, items, search, empty state")
async def b04(b, browser):
    ada = await b.api(b.setup)
    page = await b.page(browser)
    await b.login(page)
    await page.goto("/")
    b.check(await b.present(page, "dossier-list"), "dossier-list missing [Q11-06]")
    api = (await b.api(b.c.req, "GET", "/dossiers?limit=200", token=ada)).body["dossiers"]
    want = [d["domain"] for d in api]
    await page.wait_for_timeout(500)
    got = [t.removeprefix("dossier-item-") for t in await b.ids(page, "dossier-list", "dossier-item-")]
    b.check(got == want, f"dossier-list children {got} != API order {want} [Q11-06]")
    for d in api:
        tid = f"dossier-item-{d['domain']}"
        if await b.count(page, tid) == 0:
            continue
        b.check(await b.attr(page, tid, "data-state") == d["state"], f"{tid} data-state != {d['state']} [Q11-07]")
        txt = await b.text(page, tid)
        b.check(d["domain"] in txt, f"{tid} text lacks the domain [Q11-07]")
        if d["legal_name"]:
            b.check(d["legal_name"] in txt, f"{tid} text lacks the legal name {d['legal_name']!r} [Q11-07]")
        hrefs = await page.get_by_test_id(tid).first.evaluate(
            "e => [e.getAttribute('href'), ...Array.from(e.querySelectorAll('a')).map(a => a.getAttribute('href'))]")
        b.check(any(h and urllib.parse.urlparse(h).path.rstrip("/") == f"/dossiers/{d['domain']}" for h in hrefs),
                f"{tid} does not link to /dossiers/{d['domain']} ({hrefs}) [Q11-07]")
    await b.shot(page, "list-desktop")
    for q in ("KESTREL", "systems gmbh", "zzzz-nothing"):
        await page.get_by_test_id("dossier-search").fill(q)
        await page.wait_for_timeout(1200)
        want = [d["domain"] for d in (await b.api(b.c.req, "GET", "/dossiers?limit=200&q=" + urllib.parse.quote(q),
                                                  token=ada)).body["dossiers"]]
        got = [t.removeprefix("dossier-item-") for t in await b.ids(page, "dossier-list", "dossier-item-")]
        if want:
            b.check(got == want, f"search {q!r}: list {got} != API q {want} [Q11-05]")
        else:
            b.check(await b.present(page, "empty-dossiers", 5000) and not got,
                    f"search {q!r} with no match: empty-dossiers not shown (items {got}) [Q11-08]")
    await b.shot(page, "list-empty-search")
    await b.api(b.setup, (), False)
    page2 = await b.page(browser)
    await b.login(page2)
    await page2.goto("/")
    b.check(await b.present(page2, "empty-dossiers"), "no empty-dossiers when there are no dossiers [Q11-08, Q9-14]")
    await page.context.close()
    await page2.context.close()


@probe("B05", "Q11-01..Q11-03 Q11-09 Q11-10 Q15-02", "research flow: normalised navigation, refusal, existing dossier")
async def b05(b, browser):
    ada = await b.api(b.setup, (ZEPHYR,), False)
    page = await b.page(browser)
    await b.login(page)
    await page.goto("/")
    await b.present(page, "research-domain")

    async def slow_post(route):
        if route.request.method == "POST":
            resp = await route.fetch()
            await asyncio.sleep(2)
            await route.fulfill(response=resp)
        else:
            await route.continue_()
    await page.route("**/dossiers", slow_post)
    await page.get_by_test_id("research-domain").fill("  WWW.Mosaic-Freight.TEST. ")
    await page.get_by_test_id("research-submit").click()
    try:
        await page.wait_for_url("**/dossiers/mosaic-freight.test", timeout=T)
        b.check(True, "")
    except Exception:
        b.check(False, f"research did not open /dossiers/mosaic-freight.test (at {page.url}) [Q11-09]")
    b.check(await b.present(page, "dossier-domain") and await b.text(page, "dossier-domain") == "mosaic-freight.test",
            "dossier screen after research does not show the normalised domain [Q11-09, Q12-01]")
    b.check(await b.count(page, "dossier-not-found") == 0, "dossier-not-found after a delayed successful POST [Q15-02]")
    await page.unroute("**/dossiers")
    await b.api(b.c.wait, ada, "mosaic-freight.test", 30)
    await page.goto("/")
    await b.present(page, "research-domain")
    await page.get_by_test_id("research-domain").fill("not a domain")
    await page.get_by_test_id("research-submit").click()
    b.check(await b.present(page, "research-error"), "invalid domain: no research-error [Q11-03]")
    b.check(urllib.parse.urlparse(page.url).path == "/", f"invalid domain navigated to {page.url} [Q11-03]")
    await b.shot(page, "research-error")
    # another client creates a dossier after this browser read the list
    await page.goto("/")
    await b.present(page, "dossier-list")
    other = await b.api(b.c.post, ada, "windrush-bakery.test")
    await b.api(b.c.wait, ada, "windrush-bakery.test", 30)
    await b.api(b.c.mock_reset, 0)
    await page.get_by_test_id("research-domain").fill("windrush-bakery.test")
    await page.get_by_test_id("research-submit").click()
    try:
        await page.wait_for_url("**/dossiers/windrush-bakery.test", timeout=T)
    except Exception:
        b.check(False, f"existing dossier: not opened ({page.url}) [Q11-10]")
    await page.wait_for_timeout(1000)
    log = await b.api(b.c.mock_log)
    b.check(not [x for x in log if x.get("method") == "research"], "research of an existing dossier started a build [Q11-10]")
    g = await b.api(b.c.get, ada, "windrush-bakery.test")
    b.check(g.body.get("dossier_id") == (other.body or {}).get("dossier_id"), "existing dossier replaced [Q11-10]")
    await page.context.close()


@probe("B06", "Q8-04 Q8-11 Q9-08 Q9-09 Q12-01..Q12-10 Q12-15..Q12-18", "dossier screen vs API; not found; polling while building")
async def b06(b, browser):
    ada = await b.api(b.setup)
    page = await b.page(browser)
    await b.login(page)
    for dom in (ZEPHYR, KESTREL, NORD, FAILED):
        api = (await b.api(b.c.get, ada, dom)).body
        await page.goto(f"/dossiers/{dom}")
        if not await b.present(page, "dossier-domain"):
            b.check(False, f"{dom}: dossier screen not rendered")
            continue
        await page.wait_for_timeout(500)
        b.check(await b.text(page, "dossier-domain") == dom, f"{dom}: dossier-domain text [Q12-01]")
        b.check(await b.text(page, "dossier-state") == api["state"], f"{dom}: dossier-state [Q12-02]")
        b.check(await b.attr(page, "dossier-spent", "data-units") == str(api["spent_units"]), f"{dom}: dossier-spent data-units [Q12-03]")
        n_ra = await b.count(page, "dossier-researched-at")
        if api["researched_at"] is None:
            b.check(n_ra == 0, f"{dom}: dossier-researched-at present although researched_at is null [Q12-04]")
        else:
            ra = await b.text(page, "dossier-researched-at") if n_ra else ""
            b.check(n_ra == 1 and ra and ra != api["researched_at"],
                    f"{dom}: dossier-researched-at missing or the raw RFC 3339 string {ra!r} [Q12-04, Q9-08]")
        order = await page.locator('[data-testid^="field-"]').evaluate_all(
            "es => es.map(e => e.getAttribute('data-testid')).filter(t => /^field-[a-z_]+$/.test(t) && "
            "!/^field-(value|contested|citations)-/.test(t))")
        b.check(order == [f"field-{f}" for f in FIELDS], f"{dom}: field order {order} [Q12-05]")
        for f in FIELDS:
            fv = api["fields"][f]
            b.check(await b.attr(page, f"field-{f}", "data-status") == fv["status"], f"{dom}: field-{f} data-status [Q12-05]")
            nv = await b.count(page, f"field-value-{f}")
            if fv["value"] is None:
                b.check(nv == 0, f"{dom}: field-value-{f} present for a null value [Q12-06]")
            else:
                b.check(nv == 1 and await b.attr(page, f"field-value-{f}", "data-value") == str(fv["value"]),
                        f"{dom}: field-value-{f} data-value != {fv['value']!r} [Q12-06, Q12-16]")
                if f == "funding_total" and nv:
                    b.check((await b.text(page, f"field-value-{f}")) != str(fv["value"]),
                            f"{dom}: money shown as the raw integer {fv['value']} [Q9-08]")
            b.check((await b.count(page, f"field-contested-{f}") > 0) == (fv["status"] == "contested"),
                    f"{dom}: field-contested-{f} presence vs status {fv['status']} [Q12-07]")
            cits = await b.ids(page, f"field-citations-{f}", f"citation-{f}-")
            b.check(cits == [f"citation-{f}-{i}" for i in range(1, len(fv["citations"]) + 1)],
                    f"{dom}: citations of {f} {cits} vs {len(fv['citations'])} in the API [Q12-08, Q12-09]")
            for i, ct in enumerate(fv["citations"], 1):
                tid = f"citation-{f}-{i}"
                if await b.count(page, tid) == 0:
                    continue
                txt = await b.text(page, tid)
                b.check(A.collapse_ws(ct["excerpt"]) in A.collapse_ws(txt), f"{dom}: {tid} text lacks the excerpt [Q12-09]")
                b.check(await b.attr(page, tid, "data-provider") == ct["provider"], f"{dom}: {tid} data-provider [Q12-09]")
                hrefs = await page.get_by_test_id(tid).first.evaluate(
                    "e => Array.from(e.querySelectorAll('a')).map(a => a.getAttribute('href')).concat([e.getAttribute('href')])")
                b.check(ct["url"] in hrefs, f"{dom}: {tid} has no link to {ct['url']} [Q12-09, Q9-09]")
        ev = await b.attr(page, "dossier-evidence-link", "href") if await b.count(page, "dossier-evidence-link") else None
        b.check(ev and urllib.parse.urlparse(ev).path.rstrip("/") == f"/dossiers/{dom}/evidence",
                f"{dom}: dossier-evidence-link href {ev!r} [Q12-10]")
        for t in ("dossier-refresh", "dossier-reload"):
            b.check(await b.count(page, t) == 1, f"{dom}: {t} missing [Q12-11, Q12-14]")
        await b.shot(page, f"dossier-{dom}")
    await page.goto("/dossiers/WWW.Zephyr-Quantum.TEST")
    b.check(await b.present(page, "dossier-domain") and await b.text(page, "dossier-domain") == ZEPHYR,
            "browser route domain not normalised [Q8-11]")
    for bad in ("/dossiers/absent-company.test", "/dossiers/not_a_domain"):
        await page.goto(bad)
        b.check(await b.present(page, "dossier-not-found") and await b.count(page, "field-legal_name") == 0,
                f"{bad}: no dossier-not-found (or fields shown) [Q12-15, QD-18]")
    await b.shot(page, "dossier-not-found")
    # polling while building
    await b.api(b.c.mock_reset, 0)
    await b.api(b.c.mock_fault, "nimble", ["research"], "delay", 6)
    r = await b.api(b.c.post, ada, "corvid-security.test")
    t0 = time.monotonic()
    await page.goto("/dossiers/corvid-security.test")
    await b.present(page, "dossier-state")
    try:
        await page.wait_for_function(
            "() => { const e = document.querySelector('[data-testid=\"dossier-state\"]'); return e && e.textContent.trim() !== 'building'; }",
            timeout=40000)
    except Exception:
        b.check(False, "dossier screen never left building without a manual reload [Q12-17, Q12-18]")
    reads = b.reads(page, "corvid-security.test", t0)
    gaps = [round(y - x, 2) for x, y in zip(reads, reads[1:])]
    b.check(len(reads) >= 3 and all(g <= 2.5 for g in gaps), f"reads while building at gaps {gaps} (need <= 2 s) [Q12-17]")
    api = (await b.api(b.c.get, ada, "corvid-security.test")).body
    known = [f for f in FIELDS if api["fields"][f]["value"] is not None]
    for f in known:
        b.check(await b.count(page, f"field-value-{f}") == 1, f"new field {f} not shown after the build [Q12-18]")
    await b.api(b.c.mock_reset, 0)
    await page.context.close()


@probe("B07", "Q12-11..Q12-13 Q15-01 Q15-07..Q15-11 QD-20", "refresh: success, competing build, refusal, lost response retried")
async def b07(b, browser):
    ada = await b.api(b.setup, (ZEPHYR, KESTREL), False)
    page = await b.page(browser)
    await b.login(page)
    await page.goto(f"/dossiers/{KESTREL}")
    await b.present(page, "dossier-refresh")
    before = (await b.api(b.c.get, ada, KESTREL)).body
    await b.api(b.c.mock_reset, 0)
    await b.api(b.c.mock_fault, "nimble", ["research"], "delay", 3)
    await page.get_by_test_id("dossier-refresh").click()
    try:
        await page.wait_for_function("() => document.querySelector('[data-testid=\"dossier-state\"]')?.textContent.trim() === 'building'",
                                     timeout=5000)
    except Exception:
        b.check(False, "after refresh the screen does not show building [Q15-01]")
    try:
        await page.wait_for_function("() => document.querySelector('[data-testid=\"dossier-state\"]')?.textContent.trim() === 'ready'",
                                     timeout=40000)
    except Exception:
        b.check(False, "refresh build not followed to ready [Q15-01]")
    after = (await b.api(b.c.get, ada, KESTREL)).body
    b.check(after["spent_units"] > before["spent_units"], "refresh did not reach the API")
    b.check(await b.attr(page, "dossier-spent", "data-units") == str(after["spent_units"]),
            "spent not updated after the refresh without reload [Q15-01]")
    # competing client refreshes after this browser read the dossier
    await page.goto(f"/dossiers/{ZEPHYR}")
    await b.present(page, "dossier-refresh")
    await b.api(b.c.mock_reset, 0)
    await b.api(b.c.mock_fault, "nimble", ["research"], "delay", 4)
    await b.api(b.c.refresh, ada, ZEPHYR)
    async with page.expect_response(lambda r: r.url.endswith(f"/dossiers/{ZEPHYR}/refresh"), timeout=T) as ri:
        await page.get_by_test_id("dossier-refresh").click()
    b.check((await ri.value).status == 202, "refresh during another client's build not 202 [Q15-07]")
    try:
        await page.wait_for_function("() => document.querySelector('[data-testid=\"dossier-state\"]')?.textContent.trim() === 'ready'",
                                     timeout=40000)
    except Exception:
        b.check(False, "screen did not follow the running build to its end [Q15-07]")
    log = await b.api(b.c.mock_log)
    b.check(len([x for x in log if x.get("method") == "research"]) == 1, "the competing refresh started a second build")
    await b.api(b.c.mock_reset, 0)
    # refusal (4xx) and 5xx
    for status, want, why in ((404, "refresh-error", "4xx is a refusal"), (503, "refresh-uncertain", "5xx is uncertain")):
        async def fake(route, status=status):
            if route.request.method == "POST":
                await route.fulfill(status=status, content_type="application/json",
                                    body=json.dumps({"error": {"code": "not_found" if status == 404 else "unavailable",
                                                               "message": "probe"}}))
            else:
                await route.continue_()
        await page.goto(f"/dossiers/{ZEPHYR}")
        await b.present(page, "dossier-refresh")
        await page.route(f"**/dossiers/{ZEPHYR}/refresh", fake)
        await page.get_by_test_id("dossier-refresh").click()
        other = "refresh-uncertain" if want == "refresh-error" else "refresh-error"
        b.check(await b.present(page, want, 8000), f"refresh answered {status}: no {want} ({why}) [Q12-12, Q12-13, QD-20]")
        b.check(await b.count(page, other) == 0, f"refresh answered {status}: {other} shown [QD-20, Q15-11]")
        await b.shot(page, f"refresh-{status}")
        await page.unroute(f"**/dossiers/{ZEPHYR}/refresh")
    # lost response after the request committed, then a retry
    await page.goto(f"/dossiers/{ZEPHYR}")
    await b.present(page, "dossier-refresh")
    await b.api(b.c.mock_reset, 0)
    sent = []

    async def lose(route):
        if route.request.method == "POST":
            sent.append((route.request.headers.get("idempotency-key"), route.request.post_data))
            await route.fetch()
            await route.abort("connectionreset")
        else:
            await route.continue_()
    await page.route(f"**/dossiers/{ZEPHYR}/refresh", lose)
    await page.get_by_test_id("dossier-refresh").click()
    ok = await b.present(page, "refresh-uncertain", 8000)
    b.check(ok and (await b.text(page, "refresh-uncertain")), "lost refresh response: no nonempty refresh-uncertain [Q15-08]")
    b.check(await b.count(page, "refresh-error") == 0, "lost refresh response shown as refresh-error [Q15-08, Q15-11]")
    await b.shot(page, "refresh-uncertain")
    await page.unroute(f"**/dossiers/{ZEPHYR}/refresh")
    async with page.expect_request(lambda r: r.method == "POST" and r.url.endswith(f"/dossiers/{ZEPHYR}/refresh"),
                                   timeout=T) as qi:
        await page.get_by_test_id("dossier-refresh").click()
    q = await qi.value
    b.check(sent and q.headers.get("idempotency-key") == sent[0][0] and (q.post_data or "") == (sent[0][1] or ""),
            f"retry used key/body {q.headers.get('idempotency-key')!r}/{q.post_data!r}, original {sent[:1]} [Q15-09]")
    await page.wait_for_timeout(2500)
    b.check(await b.count(page, "refresh-uncertain") == 0 and await b.count(page, "refresh-error") == 0,
            "successful retry left refresh-uncertain/refresh-error [Q15-10]")
    await b.api(b.c.wait, ada, ZEPHYR, 30)
    log = await b.api(b.c.mock_log)
    b.check(len([x for x in log if x.get("method") == "research"]) <= 1, "lost refresh + retry started more than one build [Q15-10]")
    await page.context.close()


@probe("B08", "Q11-04 Q15-08..Q15-11 QD-20", "research: lost response shows research-uncertain; retry with same key and body")
async def b08(b, browser):
    ada = await b.api(b.setup, (), False)
    page = await b.page(browser)
    await b.login(page)
    await page.goto("/")
    await b.present(page, "research-domain")
    sent = []

    async def lose(route):
        if route.request.method == "POST":
            sent.append((route.request.headers.get("idempotency-key"), route.request.post_data))
            await route.fetch()
            await route.abort("connectionreset")
        else:
            await route.continue_()
    await page.route("**/dossiers", lose)
    await page.get_by_test_id("research-domain").fill("pemberton-analytics.test")
    await page.get_by_test_id("research-submit").click()
    ok = await b.present(page, "research-uncertain", 8000)
    b.check(ok and await b.text(page, "research-uncertain"), "lost research response: no nonempty research-uncertain [Q11-04, Q15-08]")
    b.check(await b.count(page, "research-error") == 0, "lost research response shown as research-error [Q15-08]")
    await b.shot(page, "research-uncertain")
    await page.unroute("**/dossiers")
    if not await page.get_by_test_id("research-domain").input_value():
        await page.get_by_test_id("research-domain").fill("pemberton-analytics.test")
    async with page.expect_request(lambda r: r.method == "POST" and urllib.parse.urlparse(r.url).path == "/dossiers",
                                   timeout=T) as qi:
        await page.get_by_test_id("research-submit").click()
    q = await qi.value
    b.check(sent and q.headers.get("idempotency-key") == sent[0][0]
            and json.loads(q.post_data or "{}") == json.loads(sent[0][1] or "{}"),
            f"retry key/body {q.headers.get('idempotency-key')!r}/{q.post_data!r} vs {sent[:1]} [Q15-09]")
    try:
        await page.wait_for_url("**/dossiers/pemberton-analytics.test", timeout=T)
    except Exception:
        b.check(False, f"successful retry did not show the dossier ({page.url}) [Q15-10]")
    b.check(await b.count(page, "research-uncertain") == 0 and await b.count(page, "research-error") == 0,
            "uncertainty/error elements remain after a successful retry [Q15-10]")
    await b.api(b.c.wait, ada, "pemberton-analytics.test", 30)
    log = await b.api(b.c.mock_log)
    b.check(len([x for x in log if x.get("method") == "research"]) == 1, "lost research + retry did not start exactly one build [Q15-10]")
    # 5xx -> uncertain, 422 -> error
    await page.goto("/")
    await b.present(page, "research-domain")

    async def five(route):
        if route.request.method == "POST":
            await route.fulfill(status=502, content_type="application/json",
                                body=json.dumps({"error": {"code": "bad_gateway", "message": "probe"}}))
        else:
            await route.continue_()
    await page.route("**/dossiers", five)
    await page.get_by_test_id("research-domain").fill("quillmate.test")
    await page.get_by_test_id("research-submit").click()
    b.check(await b.present(page, "research-uncertain", 8000) and await b.count(page, "research-error") == 0,
            "research answered 502: not shown as uncertain [QD-20]")
    await page.unroute("**/dossiers")
    await page.context.close()


@probe("B09", "Q12-14 Q15-05 Q15-06", "latest read wins: reload and polling with out-of-order answers")
async def b09(b, browser):
    ada = await b.api(b.setup, (ZEPHYR,), False)
    real = (await b.api(b.c.get, ada, ZEPHYR)).body
    page = await b.page(browser)
    await b.login(page)
    await page.goto(f"/dossiers/{ZEPHYR}")
    await b.present(page, "dossier-reload")
    await page.wait_for_timeout(500)
    await b.api(b.c.mock_reset, 0)
    state = {"n": 0}

    async def delay_first(route):
        r = route.request
        if r.method == "GET" and r.resource_type in ("fetch", "xhr"):
            state["n"] += 1
            if state["n"] == 1:
                resp = await route.fetch()
                body = await resp.json()
                body["spent_units"] = 987654
                await asyncio.sleep(3)
                await route.fulfill(response=resp, body=json.dumps(body))
                return
        await route.continue_()
    await page.route(f"**/dossiers/{ZEPHYR}", delay_first)
    await page.get_by_test_id("dossier-reload").click()
    await page.wait_for_timeout(300)
    await page.get_by_test_id("dossier-reload").click()
    await page.wait_for_timeout(4500)
    b.check(state["n"] >= 2, f"dossier-reload issued {state['n']} reads")
    b.check(await b.attr(page, "dossier-spent", "data-units") == str(real["spent_units"]),
            f"a delayed earlier read overwrote a later one (dossier-spent {await b.attr(page, 'dossier-spent', 'data-units')}) [Q15-05]")
    await page.unroute(f"**/dossiers/{ZEPHYR}")
    b.check(not [x for x in await b.api(b.c.mock_log)], "dossier-reload made a provider call [Q12-14]")
    # polling: an early 'building' answer arrives after a later 'ready'
    await b.api(b.c.mock_fault, "nimble", ["research"], "delay", 3)
    hold = {"n": 0}

    async def hold_first(route):
        r = route.request
        if r.method == "GET" and r.resource_type in ("fetch", "xhr"):
            hold["n"] += 1
            if hold["n"] == 1:
                resp = await route.fetch()
                body = await resp.body()
                for _ in range(40):
                    await asyncio.sleep(0.5)
                    st = (await b.api(b.c.get, ada, ZEPHYR)).body.get("state")
                    if st != "building" and hold["n"] >= 3:
                        break
                await asyncio.sleep(1.5)
                await route.fulfill(response=resp, body=body)
                hold["released"] = time.monotonic()
                return
        await route.continue_()
    await page.goto(f"/dossiers/{ZEPHYR}")
    await b.present(page, "dossier-refresh")
    await page.route(f"**/dossiers/{ZEPHYR}", hold_first)
    await page.get_by_test_id("dossier-refresh").click()
    for _ in range(60):
        if "released" in hold:
            break
        await page.wait_for_timeout(500)
    await page.wait_for_timeout(800)
    st = await b.text(page, "dossier-state")
    b.check(st == "ready", f"after a stale 'building' read arrived late the screen shows {st!r} [Q15-06]")
    await page.unroute(f"**/dossiers/{ZEPHYR}")
    await b.api(b.c.mock_reset, 0)
    await page.context.close()


@probe("B10", "Q8-05 Q8-10 Q13-01..Q13-03 Q12-16", "evidence screen vs API candidates")
async def b10(b, browser):
    ada = await b.api(b.setup, (KESTREL, NORD), False)
    page = await b.page(browser)
    await b.login(page)
    for dom in (KESTREL, NORD):
        api = (await b.api(b.c.get, ada, dom)).body
        await page.goto(f"/dossiers/{dom}/evidence")
        if not await b.present(page, "evidence-legal_name"):
            b.check(False, f"{dom}: evidence screen not rendered [Q13-01]")
            continue
        await page.wait_for_timeout(500)
        for f in FIELDS:
            cands = api["fields"][f]["candidates"]
            b.check(await b.count(page, f"evidence-{f}") == 1, f"{dom}: evidence-{f} missing [Q13-01]")
            got = await b.ids(page, f"evidence-{f}", f"candidate-{f}-")
            b.check(got == [f"candidate-{f}-{i}" for i in range(1, len(cands) + 1)], f"{dom}: candidates of {f} {got} [Q13-01]")
            b.check((await b.count(page, f"evidence-empty-{f}") > 0) == (not cands), f"{dom}: evidence-empty-{f} [Q13-03]")
            for i, x in enumerate(cands, 1):
                tid = f"candidate-{f}-{i}"
                if await b.count(page, tid) == 0:
                    continue
                at = {k: await b.attr(page, tid, k) for k in ("data-value", "data-provider", "data-kind", "data-url",
                                                              "data-published-at", "data-selected")}
                want = {"data-value": str(x["value"]), "data-provider": x["provider"], "data-kind": x["kind"] or "",
                        "data-url": x["url"], "data-selected": "true" if x["selected"] else "false"}
                for k, v in want.items():
                    b.check((at[k] or "") == v, f"{dom}: {tid} {k}={at[k]!r}, API {v!r} [Q13-02]")
                pa = at["data-published-at"] or ""
                b.check((pa == "" and x["published_at"] is None) or (pa and run2.same_instant(pa, x["published_at"])),
                        f"{dom}: {tid} data-published-at {pa!r} vs {x['published_at']!r} [Q13-02]")
                txt = await b.text(page, tid)
                b.check(A.collapse_ws(x["excerpt"]) in A.collapse_ws(txt), f"{dom}: {tid} text lacks the excerpt [Q13-02]")
                if x["published_at"]:
                    b.check(x["published_at"] not in txt, f"{dom}: {tid} shows the raw published_at [Q9-04]")
        await b.shot(page, f"evidence-{dom}")
    await page.goto("/dossiers/WWW.Kestrel-Dynamics.TEST/evidence")
    b.check(await b.present(page, "evidence-ceo") and await b.count(page, "candidate-ceo-1") == 1,
            "evidence route with a non-normalised domain [Q8-11]")
    await page.context.close()


@probe("B11", "Q8-06 Q14-01..Q14-03 Q9-14", "contested screen vs API; empty state")
async def b11(b, browser):
    ada = await b.api(b.setup, (KESTREL, NORD, "halvorsen-robotics.test", "pemberton-analytics.test"), False)
    want = []
    for d in (await b.api(b.c.req, "GET", "/dossiers?limit=200", token=ada)).body["dossiers"]:
        api = (await b.api(b.c.get, ada, d["domain"])).body
        for f in FIELDS:
            if api["fields"][f]["status"] == "contested":
                want.append((d["domain"], f, api["fields"][f]))
    page = await b.page(browser)
    await b.login(page)
    await page.goto("/contested")
    b.check(await b.present(page, "contested-list"), "contested-list missing [Q14-01]")
    await page.wait_for_timeout(500)
    got = await b.ids(page, "contested-list", "contested-item-")
    b.check(got == [f"contested-item-{d}-{f}" for d, f, _ in want],
            f"contested items {got} != API contested fields {[(d, f) for d, f, _ in want]} [Q14-01, Q14-02]")
    for d, f, fv in want:
        tid = f"contested-item-{d}-{f}"
        if await b.count(page, tid) == 0:
            continue
        b.check(await b.attr(page, tid, "data-value") == str(fv["value"]), f"{tid} data-value [Q14-02]")
        txt = await b.text(page, tid)
        b.check(d in txt, f"{tid} text lacks the domain [Q14-02]")
        low = txt.lower()
        if f not in low and f.replace("_", " ") not in low:
            b.c.note_once(f"{tid}: field key {f!r} not literally in the text (a human label may be used) [Q14-02]")
        for v in {json.dumps(run2.norm_val(x["value"])) for x in fv["candidates"]}:
            v = json.loads(v)
            if isinstance(v, str):
                b.check(v in txt, f"{tid} text lacks candidate value {v!r} [Q14-02]")
            elif str(v) not in re.sub(r"[,\s]", "", txt):
                b.c.note_once(f"{tid}: integer candidate value {v} not found as digits (formatted differently?) [Q14-02]")
        hrefs = await page.get_by_test_id(tid).first.evaluate(
            "e => [e.getAttribute('href'), ...Array.from(e.querySelectorAll('a')).map(a => a.getAttribute('href'))]")
        b.check(any(h and urllib.parse.urlparse(h).path.rstrip("/") == f"/dossiers/{d}/evidence" for h in hrefs),
                f"{tid} does not link to /dossiers/{d}/evidence [Q14-02]")
    await b.shot(page, "contested")
    await b.api(b.setup, (NORD,), False)
    page2 = await b.page(browser)
    await b.login(page2)
    await page2.goto("/contested")
    b.check(await b.present(page2, "empty-contested"), "no empty-contested when nothing is contested [Q14-03]")
    await page.context.close()
    await page2.context.close()


@probe("B12", "Q9-07 Q9-10..Q9-13 Q9-15 Q10-04 QD-21", "quality: 375 px and desktop without horizontal scroll, labels, contrast, focus, current-user, assets local")
async def b12(b, browser):
    from axe_playwright_python.async_playwright import Axe
    axe = Axe()
    await b.api(b.setup, (ZEPHYR, KESTREL, NORD), False)
    routes = ["/", f"/dossiers/{KESTREL}", f"/dossiers/{KESTREL}/evidence", "/contested", f"/dossiers/{NORD}"]
    for width, height in ((375, 812), (1280, 900)):
        page = await b.page(browser, width, height)
        for r in ("/login", "/signup"):
            await page.goto(r)
            await page.wait_for_timeout(800)
            await _quality(b, axe, page, r, width, signed_in=False)
        await b.login(page)
        for r in routes:
            await page.goto(r)
            await page.wait_for_timeout(1200)
            await _quality(b, axe, page, r, width, signed_in=True)
        b.check(not page.foreign, f"requests left the service origin: {sorted(set(page.foreign))[:5]} [QD-21, R2-27]")
        await page.context.close()
    # keyboard focus is apparent
    page = await b.page(browser)
    await b.login(page)
    await page.goto("/")
    await b.present(page, "research-domain")
    sig = "e => { const s = getComputedStyle(e); return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderColor, s.backgroundColor].join('|'); }"
    found = False
    for _ in range(40):
        await page.keyboard.press("Tab")
        tid = await page.evaluate("() => document.activeElement && document.activeElement.getAttribute('data-testid')")
        if tid in ("research-domain", "research-submit"):
            found = True
            focused = await page.get_by_test_id(tid).evaluate(sig)
            await page.evaluate("() => document.activeElement.blur()")
            plain = await page.get_by_test_id(tid).evaluate(sig)
            b.check(focused != plain, f"keyboard focus on {tid} is not visible (same style focused and not) [Q9-12]")
            break
    b.check(found, "research controls not reachable with the keyboard [Q9-12]")
    # states visually distinct (known / unknown / contested field rows)
    await page.goto(f"/dossiers/{NORD}")
    await b.present(page, "field-ceo")
    sigs = {}
    for f in FIELDS:
        st = await b.attr(page, f"field-{f}", "data-status")
        s = await page.get_by_test_id(f"field-{f}").evaluate(
            "e => { const all = [e, ...e.querySelectorAll('*')].slice(0, 12); return all.map(x => { const s = getComputedStyle(x); "
            "return [s.color, s.backgroundColor, s.borderLeftColor, s.borderTopColor].join(','); }).join(';'); }")
        sigs.setdefault(st, s)
    if len(sigs) >= 2 and len(set(sigs.values())) < len(sigs):
        b.c.note_once(f"field rows with statuses {sorted(sigs)} have identical colours (states may not be visually distinct) [Q9-07]")
    await page.context.close()


async def _quality(b, axe, page, route, width, signed_in):
    sw = await page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    b.check(sw[0] <= sw[1] + 1, f"{route} at {width}px: horizontal scrolling (scrollWidth {sw[0]} > {sw[1]}) [Q9-10]")
    if signed_in:
        b.check(await b.present(page, "current-user", 5000), f"{route}: current-user not visible [Q10-04]")
        links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => new URL(a.href, location.href).pathname)")
        b.check("/" in links, f"{route}: no navigation link to / [Q9-15]")
    try:
        res = await axe.run(page, options={"runOnly": {"type": "rule", "values": ["label", "color-contrast", "button-name",
                                                                                 "link-name"]}})
        for v in res.response.get("violations", []):
            if v.get("impact") in ("serious", "critical"):
                nodes = [", ".join(n.get("target", [])) for n in v.get("nodes", [])][:3]
                b.check(False, f"{route} at {width}px: axe {v['id']} ({v['impact']}) on {nodes} [Q9-11, Q9-13]")
    except Exception as e:
        b.c.note_once(f"axe could not run on {route}: {e!r}")
    await b.shot(page, f"q-{width}-{route.strip('/').replace('/', '_') or 'home'}")


@probe("U02", "Q16-02 Q16-03 Q16-08 Q16-09", "upgrade in the browser: stage-1 token stays signed in; lost research recovered after import")
async def u02(b, browser):
    c = b.c
    if c.svc1 is None:
        b.check(False, "no --service1 (stage-1 service) given")
        return
    await b.api(c.mock_reset, 0)
    r = await b.api(c.req1, "POST", "/_test/reset", s1.FIXTURE)
    if not b.check(r.status == 204, f"stage-1 reset {r!r}"):
        return
    t1 = (await b.api(c.req1, "POST", "/auth/login", {"email": "ada@example.com", "password": s1.PW})).body["token"]
    await b.api(c.req1, "POST", "/dossiers", {"domain": ZEPHYR}, t1, "u2-z")
    await b.api(run2._wait1, c, t1, ZEPHYR)
    e0 = (await b.api(c.req1, "GET", "/_test/export")).body
    await b.api(c.reset)
    c.imported |= {ZEPHYR, "ostrava-mobility.test"}
    b.check((await b.api(c.req, "POST", "/_test/import", e0)).status == 204, "import of stage-1 export E0")
    page = await b.page(browser)
    t2 = await b.login(page)
    store = await page.evaluate("() => [Object.entries(localStorage), Object.entries(sessionStorage)]")
    replaced = False
    for kind, entries in (("localStorage", store[0]), ("sessionStorage", store[1])):
        for k, v in entries:
            if t2 and t2 in v:
                await page.evaluate("([kind, k, v]) => window[kind].setItem(k, v)", [kind, k, v.replace(t2, t1)])
                replaced = True
    if not b.check(replaced, "the UI keeps no bearer token in browser storage (D18); cannot place the stage-1 token"):
        return
    await page.goto("/")
    b.check(await b.present(page, "current-user") and "Ada" in await b.text(page, "current-user"),
            "browser holding the stage-1 token is not signed in [Q16-02]")
    b.check(await b.count(page, f"dossier-item-{ZEPHYR}") == 1, "imported dossier not listed [Q16-03]")
    svc1 = c.args.service1.rstrip("/")
    sent = []

    async def to_stage1(route):
        q = route.request
        if q.method == "POST" and urllib.parse.urlparse(q.url).path == "/dossiers":
            sent.append((q.headers.get("idempotency-key"), q.post_data))
            await route.fetch(url=svc1 + "/dossiers")       # the request commits on the stage-1 service
            await route.abort("connectionreset")             # and its response is lost
        else:
            await route.continue_()
    await page.route("**/dossiers", to_stage1)
    await page.get_by_test_id("research-domain").fill("ostrava-mobility.test")
    await page.get_by_test_id("research-submit").click()
    b.check(await b.present(page, "research-uncertain", 8000), "lost research (sent to stage 1): no research-uncertain [Q15-08]")
    await page.unroute("**/dossiers")
    await b.api(run2._wait1, c, t1, "ostrava-mobility.test")
    e1 = (await b.api(c.req1, "GET", "/_test/export")).body
    await b.api(c.mock_reset, 0)
    b.check((await b.api(c.req, "POST", "/_test/import", e1)).status == 204, "import of stage-1 export E1 (upgrade)")
    b.check(await b.present(page, "current-user"), "signed out by the upgrade [Q16-02]")
    if not await page.get_by_test_id("research-domain").input_value():
        await page.get_by_test_id("research-domain").fill("ostrava-mobility.test")
    async with page.expect_request(lambda r: r.method == "POST" and urllib.parse.urlparse(r.url).path == "/dossiers",
                                   timeout=T) as qi:
        await page.get_by_test_id("research-submit").click()
    q = await qi.value
    b.check(sent and q.headers.get("idempotency-key") == sent[0][0], "retry after the upgrade used another key [Q16-08]")
    try:
        await page.wait_for_url("**/dossiers/ostrava-mobility.test", timeout=T)
        b.check(await b.present(page, "dossier-state") and await b.text(page, "dossier-state") == "ready",
                "recovered request does not show the imported dossier [Q16-08]")
    except Exception:
        b.check(False, f"retry after the upgrade did not open the imported dossier ({page.url}) [Q16-08]")
    await page.wait_for_timeout(1000)
    b.check(not [x for x in await b.api(c.mock_log) if x.get("method") == "research"],
            "retry after the upgrade started a build instead of recovering the original response [Q16-08]")
    await b.shot(page, "upgrade-recovered")
    c.imported.clear()
    await page.context.close()


async def amain(args):
    b = B(args)
    t = time.monotonic()
    while time.monotonic() - t < 60:
        if b.c._http(b.c.mock, "GET", "/_mock/health", timeout=2.0).status == 200:
            break
        await asyncio.sleep(0.5)
    t = time.monotonic()
    while time.monotonic() - t < 60:
        if b.c._http(b.c.svc, "GET", "/health", timeout=2.0).status == 200:
            break
        await asyncio.sleep(0.5)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for pid, rows, title, fn in PROBES:
            if only and pid not in only:
                continue
            b.c.current, b.c.fail = pid, []
            t = time.monotonic()
            try:
                await asyncio.wait_for(fn(b, browser), 300)
            except Exception:
                b.c.fail.append("probe crashed: " + traceback.format_exc(limit=4).replace("\n", " | "))
            results.append((pid, not b.c.fail))
            print(f"{'PASS' if not b.c.fail else 'FAIL'} {pid} ({time.monotonic() - t:.0f}s) {title}  [{rows}]", flush=True)
            for m in b.c.fail[:40]:
                print(f"     - {m}", flush=True)
        await browser.close()
    results.append(("G-UI", not b.c.global_viol))
    print(f"{'PASS' if not b.c.global_viol else 'FAIL'} G-UI global response checks on API calls made by the probes")
    for m in b.c.global_viol[:20]:
        print("     - " + m)
    if b.c.notes:
        print("NOTES (non-blocking):")
        for i, n in enumerate(b.c.notes, 1):
            print(f"  {i}. {n}")
    print(f"screenshots: {args.shots}")
    np_ = sum(1 for _, ok in results if ok)
    print(f"TOTAL: {np_} passed, {len(results) - np_} failed")
    return 0 if np_ == len(results) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", default=os.environ.get("SERVICE_URL", "http://svc:8080"))
    ap.add_argument("--service1", default=os.environ.get("SERVICE1_URL", ""))
    ap.add_argument("--mock", default=os.environ.get("MOCK_URL", "http://web:8080"))
    ap.add_argument("--admin", default=os.environ.get("MOCK_ADMIN_TOKEN", "local-admin"))
    ap.add_argument("--corpus", default=os.environ.get("CORPUS_DIR", "/corpus"))
    ap.add_argument("--shots", default=os.environ.get("SHOTS_DIR", "/logs/shots"))
    ap.add_argument("--only", default=os.environ.get("PROBE_ONLY", ""))
    return asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
