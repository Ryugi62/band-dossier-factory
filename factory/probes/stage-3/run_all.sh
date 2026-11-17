#!/usr/bin/env bash
# Run every verifier probe for dossier stage 3 against a checkout of the result repository.
#   factory/probes/stage-3/run_all.sh /path/to/result-repo-checkout
# Builds <checkout>/stage-3 (service under test), <checkout>/stage-1 and <checkout>/stage-2 (closed services, for
# the upgrade probes), the mock web and the probe runner; runs them on an --internal docker network; then:
#   run3.py main (stage-1 + stage-2 API probes with stage-3 invariants, C01..C05, U3, U4)
#   run3.py pre-restart -> docker kill + docker start (no volume) -> run3.py post-restart
#   run3.py pre-kill (build running) -> docker kill + docker start -> run3.py post-kill
#   browser3.py (stage-2 screen probes + B13)
# Env: SF_ROOT, PROBE_ONLY (main and browser parts), PART=api|restart|browser|all, KEEP=1, LOGDIR.
set -uo pipefail
REPO="$(cd "${1:?usage: run_all.sh <result-repo-checkout>}" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROBES="$(cd "$HERE/.." && pwd)"
SF_ROOT="${SF_ROOT:-/Users/ryugi62/band-work/sf-2026}"
WEB_DIR="$SF_ROOT/challenges/dossier/web"
PART="${PART:-all}"
TAG="s3p$$"
NET="$TAG-net"
BASE="${PROBE_TMP:-$HOME/.cache/s3-probes}"   # must be under $HOME: colima shares only $HOME
mkdir -p "$BASE"
CORPUS="$(mktemp -d "$BASE/corpus.XXXXXX")"
LOGDIR="${LOGDIR:-$(mktemp -d "$BASE/logs.XXXXXX")}"
mkdir -p "$LOGDIR/shots"; chmod -R a+rwX "$LOGDIR"

for pair in "stage-1 9166a2805e9c6481c7225b4eafc53f2758d464a8" "stage-2 3e32ac880a826539c69ab9c662f90c9588d19126"; do
  set -- $pair
  if ! git -C "$REPO" diff --quiet "$2" -- "$1"; then echo "FAIL D24: $1/ differs from $2"; exit 1; fi
done
echo "D24: stage-1/ and stage-2/ identical to their closed commits"

cleanup() {
  for s in svc svc1 svc2; do docker logs "$TAG-$s" > "$LOGDIR/$s.log" 2>&1 || true; done
  echo "logs: $LOGDIR"
  if [ "${KEEP:-0}" != "1" ]; then
    docker rm -f "$TAG-svc" "$TAG-svc1" "$TAG-svc2" "$TAG-web" > /dev/null 2>&1 || true
    docker network rm "$NET" > /dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cp "$WEB_DIR"/corpus/sample/*.test.json "$CORPUS"/
cp "$WEB_DIR"/corpus/sample/traits.json "$CORPUS"/ 2>/dev/null || true
cp "$PROBES"/stage-1/corpus/*.json "$PROBES"/stage-2/corpus/*.json "$PROBES"/stage-3/corpus/*.json "$CORPUS"/
chmod -R a+rX "$CORPUS"

set -e
docker build -q -t dossier-web "$WEB_DIR" > /dev/null
docker build -q -t s2-probe-runner "$PROBES/stage-2/browser" > /dev/null
docker build -q -t "$TAG-s1-img" "$REPO/stage-1" > /dev/null
docker build -q -t "$TAG-s2-img" "$REPO/stage-2" > /dev/null
docker build -t "$TAG-svc-img" "$REPO/stage-3"
set +e

ENVS=(-e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble
      -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily
      -e KERNEL_API_KEY=local -e KERNEL_BASE_URL=http://web:8080/kernel
      -e BROWSERBASE_API_KEY=local -e BROWSERBASE_BASE_URL=http://web:8080/browserbase)
docker network create --internal "$NET" > /dev/null
docker run -d --name "$TAG-web" --network "$NET" --network-alias web \
  -e MOCK_ADMIN_TOKEN=local-admin -v "$CORPUS:/data/corpus:ro" dossier-web > /dev/null
docker run -d --name "$TAG-svc1" --network "$NET" --network-alias svc1 --cpus 1 --memory 1g \
  -e PORT=8080 "${ENVS[@]}" "$TAG-s1-img" > /dev/null
docker run -d --name "$TAG-svc2" --network "$NET" --network-alias svc2 --cpus 1 --memory 1g \
  -e PORT=8080 "${ENVS[@]}" "$TAG-s2-img" > /dev/null
docker run -d --name "$TAG-svc" --network "$NET" --network-alias svc --cpus 2 --memory 3g \
  -e PORT=8080 "${ENVS[@]}" "$TAG-svc-img" > /dev/null

RUN=(docker run --rm --network "$NET" --shm-size 512m -e PYTHONDONTWRITEBYTECODE=1 -e PROBE_ONLY="${PROBE_ONLY:-}"
     -v "$PROBES:/probes:ro" -v "$CORPUS:/corpus:ro" -v "$LOGDIR:/logs" s2-probe-runner)
ARGS=(--service http://svc:8080 --service1 http://svc1:8080 --service2 http://svc2:8080 --mock http://web:8080
      --admin local-admin --corpus /corpus --state /logs)
rc=0
restart_svc() { docker kill "$TAG-svc" > /dev/null; docker start "$TAG-svc" > /dev/null; echo "--- docker kill + docker start ($1)"; }
if [ "$PART" = "all" ] || [ "$PART" = "api" ]; then
  echo "=== API probes (run3.py main)"
  "${RUN[@]}" python3 -u /probes/stage-3/run3.py --phase main "${ARGS[@]}" || rc=1
fi
if [ "$PART" = "all" ] || [ "$PART" = "restart" ]; then
  echo "=== restart probes"
  "${RUN[@]}" python3 -u /probes/stage-3/run3.py --phase pre-restart "${ARGS[@]}" || rc=1
  restart_svc "idle"
  "${RUN[@]}" python3 -u /probes/stage-3/run3.py --phase post-restart "${ARGS[@]}" || rc=1
  "${RUN[@]}" python3 -u /probes/stage-3/run3.py --phase pre-kill "${ARGS[@]}" || rc=1
  restart_svc "during a build"
  "${RUN[@]}" python3 -u /probes/stage-3/run3.py --phase post-kill "${ARGS[@]}" || rc=1
fi
if [ "$PART" = "all" ] || [ "$PART" = "browser" ]; then
  echo "=== browser probes (browser3.py)"
  "${RUN[@]}" python3 -u /probes/stage-3/browser3.py "${ARGS[@]}" --shots /logs/shots || rc=1
fi
exit $rc
