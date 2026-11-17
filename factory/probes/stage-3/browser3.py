#!/usr/bin/env python3
"""Verifier browser probes for dossier stage 3: the stage-2 screen probes (factory/probes/stage-2/browser.py,
imported, never edited) re-run with the stage-3 invariants, plus B13 (executives markup, D30).

  python3 browser3.py --service http://svc:8080 --service1 http://svc1:8080 --mock http://web:8080 \
                      --admin local-admin --corpus /corpus --shots /logs/shots
"""
import argparse
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run3  # noqa: E402  (patches nothing global; provides Ctx3)

run3.run2.Ctx2 = run3.Ctx3          # browser.B builds its API context from run2.Ctx2
import browser  # noqa: E402

LUMEN = run3.LUMEN


@browser.probe("B13", "T2-17 T2-18 TD-30", "executives in separate markup; six field testids; /contested ignores executives")
async def b13(b, browser_):
    await b.api(b.setup, (LUMEN,), False)
    ada = await b.api(b.c.login, "ada@example.com")
    api = (await b.api(b.c.get, ada, LUMEN)).body
    ex = (api.get("fields") or {}).get("executives") or {}
    names = [m.get("name") for m in (ex.get("value") or [])]
    page = await b.page(browser_)
    await b.login(page)
    await page.goto(f"/dossiers/{LUMEN}")
    await b.present(page, "dossier-domain")
    await page.wait_for_timeout(800)
    tids = await page.locator("[data-testid]").evaluate_all("es => es.map(e => e.getAttribute('data-testid'))")
    b.check(not [t for t in tids if "executives" in t and (t.startswith("field-") or t.startswith("citation-"))],
            f"executives uses stage-2 field testids: {[t for t in tids if 'executives' in t]} [T2-17, TD-30]")
    fields = [t for t in tids if t.startswith("field-") and t.count("-") == 1 or (t.startswith("field-") and "_" in t and
              not t.startswith(("field-value-", "field-contested-", "field-citations-")))]
    b.check(len(set(fields)) == 6, f"dossier screen field testids {sorted(set(fields))} (exactly six) [T2-17, TD-30]")
    body = await page.inner_text("body")
    for n in names:
        b.check(n in body, f"executive {n!r} not shown on the dossier screen [TD-30]")
    await b.shot(page, "s3-dossier-lumen")
    await page.goto(f"/dossiers/{LUMEN}/evidence")
    await b.present(page, "evidence-legal_name")
    await page.wait_for_timeout(800)
    tids = await page.locator("[data-testid]").evaluate_all("es => es.map(e => e.getAttribute('data-testid'))")
    ev = sorted({t for t in tids if t.startswith("evidence-") and not t.startswith("evidence-empty-")})
    b.check(len(ev) == 6 and "evidence-executives" not in tids, f"evidence containers {ev} (exactly six) [T2-17, TD-30]")
    body = await page.inner_text("body")
    for cand in ex.get("candidates") or []:
        b.check(cand["value"] in body, f"executives candidate {cand['value']!r} not on the evidence screen [TD-30]")
    await b.shot(page, "s3-evidence-lumen")
    await page.goto("/contested")
    b.check(await b.present(page, "empty-contested"), "only executives is contested: /contested must show empty-contested [T2-18]")
    b.check(await b.count(page, f"contested-item-{LUMEN}-executives") == 0, "executives listed on /contested [T2-18]")
    await page.context.close()


def main():
    ap = argparse.ArgumentParser()
    for k, d in (("service", "http://svc:8080"), ("service1", ""), ("service2", ""), ("mock", "http://web:8080"),
                 ("admin", "local-admin"), ("corpus", "/corpus"), ("shots", "/logs/shots"), ("state", "/logs")):
        ap.add_argument("--" + k, default=d)
    ap.add_argument("--only", default=os.environ.get("PROBE_ONLY", ""))
    return asyncio.run(browser.amain(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
