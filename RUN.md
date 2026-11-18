# RUN.md: stand the service up from this repository

The stage folders are the factory's output and stay byte-identical, so their own `RUN.md` files
are unchanged. This file is the single entry for a reader; it passes `NIMBLE_BASE_URL` only when it
is set and non-empty, because an empty value counts as set and makes every provider call fail
with `Connection error`.

Needs Docker and a sibling checkout of the organizer's repository
(`https://github.com/band-ai/sf-buildathon-2026`) for the mock web. Replace `stage-4` by
`stage-1`, `stage-2` or `stage-3` to run an earlier stage.

## A. Mock web (no key, about three minutes)

```sh
docker build -t dossier-web ../sf-buildathon-2026/challenges/dossier/web
docker network create dossier
docker run --rm -d --name web --network dossier -e MOCK_ADMIN_TOKEN=local-admin \
  -v "$PWD/../sf-buildathon-2026/challenges/dossier/web/corpus/sample:/data/corpus:ro" dossier-web
docker build -t dossier-s4 stage-4
docker run --rm -d --name dossier-s4 --network dossier -p 8080:8080 -e PORT=8080 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily dossier-s4
curl -s localhost:8080/health        # {"status": "ok"}
```

If port 8080 is taken, change the left number of `-p`. Try it:

```sh
TOKEN=$(curl -s -X POST localhost:8080/auth/signup -H 'content-type: application/json' \
  -d '{"email":"a@example.com","password":"correct horse","display_name":"Ada"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -X POST localhost:8080/dossiers -H "Authorization: Bearer $TOKEN" -H 'Idempotency-Key: k1' \
  -H 'content-type: application/json' -d '{"domain":"brightwater-labs.test"}'
sleep 8; curl -s localhost:8080/dossiers/brightwater-labs.test -H "Authorization: Bearer $TOKEN"
```

Clean up: `docker rm -f web dossier-s4 && docker network rm dossier`.

## B. Live web (your own Nimble key; spends real units; see the limits in the README)

```sh
: "${NIMBLE_API_KEY:?set NIMBLE_API_KEY to your Nimble key, or use section A}"
ENVS=(-e PORT=8080 -e NIMBLE_API_KEY="$NIMBLE_API_KEY")
[ -n "$NIMBLE_BASE_URL" ] && ENVS+=(-e NIMBLE_BASE_URL="$NIMBLE_BASE_URL")   # never pass it empty
docker build -t dossier-s4 stage-4 && docker run --rm -p 8080:8080 "${ENVS[@]}" dossier-s4
```

Leave `NIMBLE_BASE_URL` unset to use Nimble's own endpoint.
