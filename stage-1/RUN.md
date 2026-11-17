# Dossier — stage 1

A company-research HTTP service (Python 3.12, aiohttp). Providers are reached only through
WebRouter's `nimble` provider (`web_router`, installed in the image); Tavily is never called.
State is in memory.

## Build and start

From this folder:

```sh
docker build -t dossier-s1 . && docker run --rm -p 8080:8080 -e PORT=8080 \
  -e NIMBLE_API_KEY="$NIMBLE_API_KEY" -e NIMBLE_BASE_URL="$NIMBLE_BASE_URL" \
  -e TAVILY_API_KEY="$TAVILY_API_KEY" -e TAVILY_BASE_URL="$TAVILY_BASE_URL" dossier-s1
```

Leave `NIMBLE_BASE_URL` out (do not pass it empty) to use the live Nimble endpoint.
`GET /health` answers `{"status": "ok"}` within a few seconds of start.

Against the mock web (`sf-2026/challenges/dossier/web`), on a shared docker network where the
mock runs as `web`:

```sh
docker run --rm --network dossier -p 8000:8000 -e PORT=8000 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily dossier-s1
```

## Unit tests (offline, standard library only)

```sh
python3 -m unittest discover -s tests -t .
```

(Python 3.11 or later, run from this folder; or inside the image:
`docker run --rm dossier-s1 python -m unittest discover -s tests -t .`)

## Layout

| Module | Role |
|---|---|
| `dossier/support.py` | Appendix A: sentences, value formats, the support rule (pure) |
| `dossier/pages.py` | Page header/prose split, supporting sentences of prose (pure) |
| `dossier/domains.py` | Domain normalisation and validation (pure) |
| `dossier/pipeline.py` | One build: which provider calls to make, field decision and citations |
| `dossier/provider.py` | WebRouter access, per-build 80-unit cap, cost accounting, retries |
| `dossier/service.py` | Dossiers, builds, idempotency, accounts, reset/clock/import operations |
| `dossier/store.py`, `dossier/exchange.py` | In-memory state; export/import format and validation |
| `dossier/accounts.py`, `dossier/clock.py`, `dossier/errors.py` | Accounts (scrypt), service clock, error envelope |
| `dossier/http_app.py` | HTTP routes and JSON transport |

## Cost per build

Every build starts one Nimble research run (25 units), makes one lite search for the domain
(1), lite searches for fields still unsupported when that search came back full (1 each), and
1-unit extracts only for pages it still needs (snippets cut short, research-cited pages).
Each call reserves its cost first; a build never spends more than 80 units.
