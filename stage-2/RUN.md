# Dossier — stage 2

A company-research service with browser screens (Python 3.12, aiohttp, vanilla ES modules).
Providers are reached only through WebRouter's `nimble` provider (`web_router`, installed in the
image); Tavily, Kernel and Browserbase are never called. State is in memory. Every UI script,
style and font is inside the image (system font stack), so nothing loads from the network.

## Build and start

From this folder:

```sh
docker build -t dossier-s2 . && docker run --rm -p 8080:8080 -e PORT=8080 \
  -e NIMBLE_API_KEY="$NIMBLE_API_KEY" -e NIMBLE_BASE_URL="$NIMBLE_BASE_URL" \
  -e TAVILY_API_KEY="$TAVILY_API_KEY" -e TAVILY_BASE_URL="$TAVILY_BASE_URL" dossier-s2
```

Leave `NIMBLE_BASE_URL` out (do not pass it empty) to use the live Nimble endpoint. The
`KERNEL_*` and `BROWSERBASE_*` variables are accepted and ignored. `GET /health` answers
`{"status": "ok"}` within a few seconds of start. Open `http://localhost:8080/` in a browser,
sign up (or log in as a seeded user) and research a domain.

Against the mock web (`sf-2026/challenges/dossier/web`), on a shared docker network where the
mock runs as `web`:

```sh
docker run --rm --network dossier -p 8000:8000 -e PORT=8000 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily dossier-s2
```

## Unit tests (offline, standard library only)

```sh
python3 -m unittest discover -s tests -t .
```

(Python 3.11 or later, run from this folder; the HTTP negotiation test is skipped when aiohttp
is not installed. Inside the image: `docker run --rm dossier-s2 python -m unittest discover -s tests -t .`)

## Layout

| Module | Role |
|---|---|
| `dossier/support.py` | Appendix A: sentences, value formats, the support rule (pure) |
| `dossier/pages.py` | Header/prose split, page kind and publication time, supporting sentences (pure) |
| `dossier/selection.py` | Selection rule, status, citations and ranked candidates of a field (pure) |
| `dossier/domains.py` | Domain normalisation and validation (pure) |
| `dossier/pipeline.py` | One build: which provider calls to make; candidates from rendered page text |
| `dossier/provider.py` | WebRouter access, per-build 80-unit cap, cost accounting, 429 retries, deadline |
| `dossier/service.py` | Dossiers, builds, idempotency, accounts, reset/clock/import operations |
| `dossier/store.py`, `dossier/exchange.py` | In-memory state; export/import (stage-2 and stage-1 exports) |
| `dossier/accounts.py`, `dossier/clock.py`, `dossier/errors.py` | Accounts (scrypt), service clock, error envelope |
| `dossier/http_app.py`, `dossier/ui_routes.py` | HTTP API routes; browser routes, Accept negotiation, static assets |
| `dossier/ui/` | The browser UI: `app.js` (screens and layout), `api.js`, `format.js`, `views/*.js`, `app.css` |

## Cost per build

Every build starts one Nimble research run (25 units) and one lite search for the domain (1);
when that search comes back full, six lite searches by company name and field phrases (1 each)
reach the remaining pages. Every page whose known text supports a value is read once with a
rendered Nimble extract (3), which is where candidates come from; a page whose snippet is cut
short gets a 1-unit plain extract first and is rendered only if it supports a value. Pages cited
by research claims are read the same way. Each call reserves its cost first; a build never spends
more than 80 units.
