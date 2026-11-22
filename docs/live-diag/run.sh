#!/bin/bash
# usage: run.sh <image> <domain> <outprefix>   (NIMBLE_API_KEY from env)
IMG=$1; DOM=$2; OUT=$3
docker rm -f dossier-diag-run >/dev/null 2>&1
docker run -d --name dossier-diag-run -p 8010:8010 -e PORT=8010 -e NIMBLE_API_KEY -e NIMBLE_BASE_URL=https://sdk.nimbleway.com $IMG >/dev/null
n=0; until curl -sf http://localhost:8010/health >/dev/null; do sleep 1; n=$((n+1)); [ $n -ge 60 ] && { echo HEALTH_TIMEOUT; exit 1; }; done
B=http://localhost:8010
T=$(curl -s -X POST $B/auth/signup -H 'Content-Type: application/json' -d '{"email":"live@example.com","password":"live-dossier","display_name":"Live"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
S=$(date +%s)
curl -s -X POST $B/dossiers -H "Authorization: Bearer $T" -H "Idempotency-Key: $(python3 -c 'import uuid;print(uuid.uuid4())')" -H 'Content-Type: application/json' -d "{\"domain\": \"$DOM\"}" >/dev/null
n=0; while curl -s $B/dossiers/$DOM -H "Authorization: Bearer $T" | grep -q '"state": *"building"'; do sleep 5; n=$((n+1)); [ $n -ge 90 ] && { echo BUILD_TIMEOUT; break; }; done
echo "elapsed $(( $(date +%s)-S ))s"
curl -s $B/dossiers/$DOM -H "Authorization: Bearer $T" > $OUT.json
docker logs dossier-diag-run > $OUT.log 2>&1
docker rm -f dossier-diag-run >/dev/null
python3 -c "
import json;d=json.load(open('$OUT.json'));print(d['state'],d.get('spent_units'));[print(f,v['status'],v['value']) for f,v in d['fields'].items()]"
