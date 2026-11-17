#!/usr/bin/env bash
# Run every verifier probe for dossier stage 2 against a checkout of the result repository.
#   factory/probes/stage-2/run_all.sh /path/to/result-repo-checkout
# Builds <checkout>/stage-2 (service under test), <checkout>/stage-1 (closed stage-1 service, for the
# upgrade probes), the mock web and the probe runner (Playwright + axe), runs all of them on an
# --internal docker network (no outbound access), then runs run2.py (API) and browser.py (screens).
# Env: SF_ROOT, PROBE_ONLY=A02,B06, PART=api|browser|all, KEEP=1, LOGDIR.
set -uo pipefail
REPO="$(cd "${1:?usage: run_all.sh <result-repo-checkout>}" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROBES="$(cd "$HERE/.." && pwd)"
SF_ROOT="${SF_ROOT:-./sf-2026}"
WEB_DIR="$SF_ROOT/challenges/dossier/web"
PART="${PART:-all}"
TAG="s2p$$"
NET="$TAG-net"
BASE="${PROBE_TMP:-$HOME/.cache/s2-probes}"   # must be under $HOME: colima shares only $HOME
mkdir -p "$BASE"
CORPUS="$(mktemp -d "$BASE/corpus.XXXXXX")"
LOGDIR="${LOGDIR:-$(mktemp -d "$BASE/logs.XXXXXX")}"
mkdir -p "$LOGDIR/shots"

if ! git -C "$REPO" diff --quiet 9166a2805e9c6481c7225b4eafc53f2758d464a8 -- stage-1; then
  echo "FAIL D22: stage-1/ differs from 9166a28"; exit 1
fi
echo "D22: stage-1/ identical to 9166a28"

cleanup() {
  docker logs "$TAG-svc" > "$LOGDIR/service.log" 2>&1 || true
  docker logs "$TAG-svc1" > "$LOGDIR/service1.log" 2>&1 || true
  echo "logs: $LOGDIR"
  if [ "${KEEP:-0}" != "1" ]; then
    docker rm -f "$TAG-svc" "$TAG-svc1" "$TAG-web" > /dev/null 2>&1 || true
    docker network rm "$NET" > /dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cp "$WEB_DIR"/corpus/sample/*.test.json "$CORPUS"/
cp "$WEB_DIR"/corpus/sample/traits.json "$CORPUS"/ 2>/dev/null || true
cp "$PROBES"/stage-1/corpus/*.json "$PROBES"/stage-2/corpus/*.json "$CORPUS"/
chmod -R a+rX "$CORPUS"

set -e
docker build -q -t dossier-web "$WEB_DIR" > /dev/null
docker build -q -t s2-probe-runner "$HERE/browser" > /dev/null
docker build -q -t "$TAG-s1-img" "$REPO/stage-1" > /dev/null
docker build -t "$TAG-svc-img" "$REPO/stage-2"
set +e

ENVS=(-e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble
      -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily
      -e KERNEL_API_KEY=local -e KERNEL_BASE_URL=http://web:8080/kernel
      -e BROWSERBASE_API_KEY=local -e BROWSERBASE_BASE_URL=http://web:8080/browserbase)
docker network create --internal "$NET" > /dev/null
docker run -d --name "$TAG-web" --network "$NET" --network-alias web \
  -e MOCK_ADMIN_TOKEN=local-admin -v "$CORPUS:/data/corpus:ro" dossier-web > /dev/null
docker run -d --name "$TAG-svc1" --network "$NET" --network-alias svc1 --cpus 1 --memory 1g \
  -e PORT=8080 "${ENVS[@]:0:8}" "$TAG-s1-img" > /dev/null
docker run -d --name "$TAG-svc" --network "$NET" --network-alias svc --cpus 2 --memory 3g \
  -e PORT=8080 "${ENVS[@]}" "$TAG-svc-img" > /dev/null

RUN=(docker run --rm --network "$NET" --shm-size 512m -e PYTHONDONTWRITEBYTECODE=1 -e PROBE_ONLY="${PROBE_ONLY:-}"
     -v "$PROBES:/probes:ro" -v "$CORPUS:/corpus:ro" -v "$LOGDIR:/logs" s2-probe-runner)
ARGS=(--service http://svc:8080 --service1 http://svc1:8080 --mock http://web:8080 --admin local-admin --corpus /corpus)
rc=0
if [ "$PART" = "all" ] || [ "$PART" = "api" ]; then
  echo "=== API probes (run2.py)"
  "${RUN[@]}" python3 -u /probes/stage-2/run2.py "${ARGS[@]}" || rc=1
fi
if [ "$PART" = "all" ] || [ "$PART" = "browser" ]; then
  echo "=== browser probes (browser.py)"
  "${RUN[@]}" python3 -u /probes/stage-2/browser.py "${ARGS[@]}" --shots /logs/shots || rc=1
fi
exit $rc
