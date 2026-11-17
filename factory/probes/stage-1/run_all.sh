#!/usr/bin/env bash
# Run every verifier probe for dossier stage 1 against a checkout of the result repository.
#   factory/probes/stage-1/run_all.sh /path/to/result-repo-checkout
# Builds <checkout>/stage-1 and the mock web, runs both on an --internal docker network (no outbound
# access), then runs run.py from a python:3.12-slim container on the same network.
# Env: SF_ROOT (kickoff checkout), PROBE_ONLY=P06,P11, KEEP=1 (leave containers running).
set -euo pipefail
REPO="$(cd "${1:?usage: run_all.sh <result-repo-checkout>}" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
SF_ROOT="${SF_ROOT:-./sf-2026}"
WEB_DIR="$SF_ROOT/challenges/dossier/web"
TAG="s1p$$"
NET="$TAG-net"
mkdir -p "${PROBE_TMP:-$HOME/.cache/s1-probes}"   # must be under $HOME: colima shares only $HOME
CORPUS="$(mktemp -d "${PROBE_TMP:-$HOME/.cache/s1-probes}/corpus.XXXXXX")"
LOGDIR="${LOGDIR:-$CORPUS}"

cleanup() {
  docker logs "$TAG-svc" > "$LOGDIR/service.log" 2>&1 || true
  echo "service log: $LOGDIR/service.log"
  if [ "${KEEP:-0}" != "1" ]; then
    docker rm -f "$TAG-svc" "$TAG-web" > /dev/null 2>&1 || true
    docker network rm "$NET" > /dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cp "$WEB_DIR"/corpus/sample/*.test.json "$CORPUS"/
cp "$WEB_DIR"/corpus/sample/traits.json "$CORPUS"/ 2>/dev/null || true
cp "$HERE"/corpus/*.json "$CORPUS"/
chmod -R a+rX "$CORPUS"

docker image inspect python:3.12-slim > /dev/null 2>&1 || docker pull python:3.12-slim
docker build -q -t dossier-web "$WEB_DIR" > /dev/null
docker build -t "$TAG-svc-img" "$REPO/stage-1"

docker network create --internal "$NET" > /dev/null
docker run -d --name "$TAG-web" --network "$NET" --network-alias web \
  -e MOCK_ADMIN_TOKEN=local-admin -v "$CORPUS:/data/corpus:ro" dossier-web > /dev/null
docker run -d --name "$TAG-svc" --network "$NET" --network-alias svc --cpus 2 --memory 3g \
  -e PORT=8080 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily \
  "$TAG-svc-img" > /dev/null

docker run --rm --network "$NET" -e PYTHONDONTWRITEBYTECODE=1 -e PROBE_ONLY="${PROBE_ONLY:-}" \
  -v "$HERE:/probes:ro" -v "$CORPUS:/corpus:ro" python:3.12-slim \
  python3 -u /probes/run.py --service http://svc:8080 --mock http://web:8080 --admin local-admin --corpus /corpus
