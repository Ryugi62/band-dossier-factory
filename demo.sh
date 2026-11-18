#!/bin/sh
# demo.sh: one command from a fresh clone to a running stage-4 service on the organizer's mock web.
#
# Spec: with Docker and git installed and no API key, `sh demo.sh` clones the organizer's repository
# next to this one if it is missing, builds the mock web and the stage-4 image, starts both on a private
# network, waits until `GET /health` answers {"status": "ok"} (exit 0) or 180 s pass (exit 1), and prints
# the URL and the cleanup command. `sh demo.sh stop` removes the two containers and the network.
# It runs the same commands as RUN.md section A; it does not touch stage-N/. PORT (default 8080) and
# STAGE (default stage-4) can be set in the environment.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
org="${ORG:-$here/../sf-buildathon-2026}"
port="${PORT:-8080}"
stage="${STAGE:-stage-4}"
net=dossier-demo

if [ "${1:-}" = stop ]; then
  docker rm -f dossier-demo-web dossier-demo-svc >/dev/null 2>&1 || true
  docker network rm "$net" >/dev/null 2>&1 || true
  echo "stopped"
  exit 0
fi

[ -d "$org" ] || git clone -q https://github.com/band-ai/sf-buildathon-2026 "$org"
docker build -q -t dossier-web "$org/challenges/dossier/web" >/dev/null
docker build -q -t "dossier-$stage" "$here/$stage" >/dev/null
docker network inspect "$net" >/dev/null 2>&1 || docker network create "$net" >/dev/null
docker rm -f dossier-demo-web dossier-demo-svc >/dev/null 2>&1 || true
docker run --rm -d --name dossier-demo-web --network "$net" -e MOCK_ADMIN_TOKEN=local-admin \
  -v "$org/challenges/dossier/web/corpus/sample:/data/corpus:ro" dossier-web >/dev/null
docker run --rm -d --name dossier-demo-svc --network "$net" -p "$port:8080" -e PORT=8080 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://dossier-demo-web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://dossier-demo-web:8080/tavily "dossier-$stage" >/dev/null

sleep 3  # let a crashing mock web show up before the first check
i=3
while [ $i -lt 180 ]; do
  if [ "$(docker inspect -f '{{.State.Running}}' dossier-demo-web 2>/dev/null)" != true ]; then
    echo "mock web exited: its corpus folder is probably not shared with the Docker VM (use a checkout under your home folder); run the two docker run lines by hand without -d to see why" >&2
    exit 1
  fi
  if curl -fs "localhost:$port/health" 2>/dev/null | grep -q '"ok"'; then
    echo "ready: http://localhost:$port  (health ok after ${i}s; next steps in RUN.md; stop with: sh demo.sh stop)"
    exit 0
  fi
  i=$((i + 2)); sleep 2
done
echo "not ready after 180 s; see: docker logs dossier-demo-svc" >&2
exit 1
