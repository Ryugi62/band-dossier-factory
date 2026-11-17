"""Browser routes (stage 2, Screens): the UI document, its static assets, and Accept negotiation.

Browser routes answer the same single-page document; its scripts read the API with the bearer
token kept in browser storage (decision D18). Every asset ships inside the image (decision D21).
"""
from __future__ import annotations

from pathlib import Path

from aiohttp import web

UI_DIR = Path(__file__).parent / "ui"
BROWSER_ONLY = ("/", "/signup", "/login", "/contested", "/dossiers/{domain}/evidence")
_NO_CACHE = {"Cache-Control": "no-cache"}


def wants_html(request: web.Request) -> bool:
    return accepts_html(request.headers.get("Accept", ""))


def accepts_html(accept: str) -> bool:
    """True when an Accept header lists text/html with a non-zero quality."""
    for part in accept.split(","):
        media, *params = [p.strip() for p in part.split(";")]
        if media.lower() != "text/html":
            continue
        for p in params:
            name, _, value = p.partition("=")
            if name.strip().lower() == "q":
                try:
                    return float(value) > 0
                except ValueError:
                    return False
        return True
    return False


async def document(_request: web.Request) -> web.Response:
    return web.Response(text=(UI_DIR / "index.html").read_text(encoding="utf-8"), content_type="text/html",
                        charset="utf-8", headers=_NO_CACHE)


def add_routes(app: web.Application) -> None:
    for path in BROWSER_ONLY:
        app.router.add_get(path, document)
    app.router.add_static("/static/", UI_DIR, show_index=False, append_version=False)
