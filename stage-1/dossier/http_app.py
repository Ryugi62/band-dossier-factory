"""HTTP transport (§3, §5, §6, §8, §10): routing, JSON bodies, error envelopes."""
from __future__ import annotations

import json
import logging
import re

from aiohttp import web

from . import errors
from .service import Service, canonical

log = logging.getLogger("dossier.http")
_DIGITS = re.compile(r"[0-9]+")


def _json(status: int, body) -> web.Response:
    return web.Response(status=status, text=json.dumps(body, ensure_ascii=False),
                        content_type="application/json", charset="utf-8")


def _reject_constant(name):
    raise ValueError(f"not JSON: {name}")


async def _body(request: web.Request):
    raw = await request.read()
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError):
        raise errors.malformed() from None


async def _object(request: web.Request) -> dict:
    body = await _body(request)
    if not isinstance(body, dict):
        raise errors.malformed("body must be a JSON object")
    return body


def _int_param(request: web.Request, name: str, default: int, low: int, high: int | None) -> int:
    if name not in request.query:
        return default
    raw = request.query[name]
    if not _DIGITS.fullmatch(raw):
        raise errors.invalid(f"{name} must be written as plain decimal digits")
    value = int(raw)
    if value < low or (high is not None and value > high):
        raise errors.invalid(f"{name} is out of range")
    return value


def _idempotency_key(request: web.Request) -> str:
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise errors.ApiError(400, "missing_idempotency_key", "Idempotency-Key header is required")
    if len(key) > 255:
        raise errors.invalid("Idempotency-Key must be 1 to 255 characters")
    return key


def build_app(service: Service) -> web.Application:
    routes = web.RouteTableDef()

    def auth(request: web.Request) -> str:
        return service.authenticate(request.headers.get("Authorization"))

    @routes.get("/health")
    async def health(_):
        return _json(200, {"status": "ok"})

    @routes.post("/_test/reset")
    async def reset(request):
        await service.reset(await _body(request))
        return web.Response(status=204)

    @routes.post("/_test/clock")
    async def clock(request):
        service.set_clock(await _body(request))
        return web.Response(status=204)

    @routes.get("/_test/export")
    async def export(_):
        return _json(200, service.export())

    @routes.post("/_test/import")
    async def import_(request):
        service.import_state(await _body(request))
        return web.Response(status=204)

    @routes.post("/auth/signup")
    async def signup(request):
        return _json(201, await service.signup(await _body(request)))

    @routes.post("/auth/login")
    async def login(request):
        return _json(200, await service.login(await _body(request)))

    @routes.post("/dossiers")
    async def create(request):
        user_id = auth(request)
        key = _idempotency_key(request)
        body = await _object(request)
        fingerprint = canonical({"domain": body["domain"]} if "domain" in body else {})
        status, out = service.idempotent(user_id, "POST", request.path, key, fingerprint,
                                         lambda: service.create(body))
        return _json(status, out)

    @routes.get("/dossiers")
    async def list_(request):
        auth(request)
        limit = _int_param(request, "limit", 50, 1, 200)
        offset = _int_param(request, "offset", 0, 0, None)
        return _json(200, service.list(request.query.get("q"), limit, offset))

    @routes.get("/dossiers/{domain}")
    async def read(request):
        auth(request)
        return _json(200, service.read(request.match_info["domain"]))

    @routes.post("/dossiers/{domain}/refresh")
    async def refresh(request):
        user_id = auth(request)
        key = _idempotency_key(request)
        domain = request.match_info["domain"]
        status, out = service.idempotent(user_id, "POST", request.path, key, "",
                                         lambda: service.refresh(domain))
        return _json(status, out)

    @web.middleware
    async def envelope(request, handler):
        try:
            return await handler(request)
        except errors.ApiError as exc:
            return _json(exc.status, exc.body())
        except web.HTTPException as exc:
            if exc.status < 400:
                raise
            code = "not_found" if exc.status in (404, 405) else "malformed_request"
            status = 404 if exc.status == 405 else exc.status
            return _json(status, {"error": {"code": code, "message": exc.reason}})
        except Exception:  # noqa: BLE001 - never answer with a bare 5xx
            log.exception("unhandled error on %s %s", request.method, request.path)
            return _json(500, {"error": {"code": "internal", "message": "internal error"}})

    app = web.Application(middlewares=[envelope], client_max_size=16 * 1024 * 1024)
    app.add_routes(routes)
    return app
