#!/usr/bin/env python3
"""Verifier browser probes for dossier stage 4: the stage-2 and stage-3 screen probes (browser.py, browser3.py,
imported, never edited) re-run with the stage-4 invariants, plus B14 (investors markup, D45).
"""
import argparse
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run4  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "stage-3"))
import browser3  # noqa: E402  (registers B13, imports browser.py)

browser = browser3.browser
run4.run2.Ctx2 = run4.Ctx4          # browser.B builds its API context from run2.Ctx2


@browser.probe("B14", "V2-01 V2-02 TD-45", "investors in separate markup; six field testids; /contested ignores investors")
async def b14(b, browser_):
    await b.api(b.setup, (run4.ORBIT,), False)
    ada = await b.api(b.c.login, "ada@example.com")
    api = (await b.api(b.c.get, ada, run4.ORBIT)).body
    inv = (api.get("fields") or {}).get("investors") or {}
    page = await b.page(browser_)
    await b.login(page)
    await page.goto(f"/dossiers/{run4.ORBIT}")
    await b.present(page, "dossier-domain")
    await page.wait_for_timeout(800)
    tids = await page.locator("[data-testid]").evaluate_all("es => es.map(e => e.getAttribute('data-testid'))")
    b.check(not [t for t in tids if "investors" in t and t.startswith(("field-", "citation-"))],
            f"investors uses stage-2 field testids [V2-01, TD-45]")
    body = await page.inner_text("body")
    for n in inv.get("value") or []:
        b.check(n in body, f"investor {n!r} not shown on the dossier screen [TD-45]")
    await b.shot(page, "s4-dossier-orbit")
    await page.goto(f"/dossiers/{run4.ORBIT}/evidence")
    await b.present(page, "evidence-legal_name")
    await page.wait_for_timeout(800)
    tids = await page.locator("[data-testid]").evaluate_all("es => es.map(e => e.getAttribute('data-testid'))")
    b.check("evidence-investors" not in tids, "evidence-investors testid used [V2-01, TD-45]")
    body = await page.inner_text("body")
    for c in inv.get("candidates") or []:
        b.check(c.get("value") in body, f"investors candidate {c.get('value')!r} not on the evidence screen [TD-45]")
    await b.shot(page, "s4-evidence-orbit")
    await page.goto("/contested")
    b.check(await b.count(page, f"contested-item-{run4.ORBIT}-investors") == 0, "investors listed on /contested [V2-02]")
    await page.context.close()


def main():
    ap = argparse.ArgumentParser()
    for k, d in (("service", "http://svc:8080"), ("service1", ""), ("service2", ""), ("service3", ""),
                 ("mock", "http://web:8080"), ("admin", "local-admin"), ("corpus", "/corpus"), ("shots", "/logs/shots"),
                 ("state", "/logs")):
        ap.add_argument("--" + k, default=d)
    ap.add_argument("--only", default=os.environ.get("PROBE_ONLY", ""))
    return asyncio.run(browser.amain(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
