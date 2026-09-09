#!/usr/bin/env bash
# RAGFlow knowledge-dev bootstrap: prepare a smoke-ready RAGFlow tenant for
# the iDeer knowledge-dev compose profile (docker-compose-knowledge-dev.yaml).
#
# Idempotent: every step tolerates being already done, so the script can be
# re-run against a live stack to converge it to the desired state.
#
# Prerequisites:
#   - the knowledge-dev stack is up (`up -d ragflow`, optionally ragflow-tei
#     with --profile tei as the embedding endpoint)
#   - python3 available on the host (JSON parsing) and inside the ragflow
#     container (RSA password encryption, same as the RAGFlow web UI)
#
# Usage:
#   docker/ragflow/bootstrap.sh [--docs-dir DIR]
#
# Environment overrides (defaults shown):
#   RAGFLOW_URL=http://127.0.0.1:9380
#   RAGFLOW_SMOKE_EMAIL=smoke-b05@test.local
#   RAGFLOW_SMOKE_PASSWORD='SmokeTest#2026'
#   RAGFLOW_EMBEDDING_BASE_URL=http://ideer-ragflow-tei:80/v1
#   RAGFLOW_EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
#   RAGFLOW_DATASET_NAME=ideer-knowledge-smoke
#
# Output: prints the values the iDeer config.yaml knowledge_search tool needs
# (dataset ID for the allowlist, API key for $RAGFLOW_API_KEY in .env).
set -euo pipefail

RF=${RAGFLOW_URL:-http://127.0.0.1:9380}
EMAIL=${RAGFLOW_SMOKE_EMAIL:-smoke-b05@test.local}
PASSWORD=${RAGFLOW_SMOKE_PASSWORD:-'SmokeTest#2026'}
EMB_BASE_URL=${RAGFLOW_EMBEDDING_BASE_URL:-http://ideer-ragflow-tei:80/v1}
EMB_MODEL=${RAGFLOW_EMBEDDING_MODEL_NAME:-BAAI/bge-small-en-v1.5}
PROVIDER_NAME="OpenAI-API-Compatible"
INSTANCE_NAME="tei-intranet"
DATASET_NAME=${RAGFLOW_DATASET_NAME:-ideer-knowledge-smoke}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR=${RAGFLOW_DOCS_DIR:-"$SCRIPT_DIR/../../dev-log/knowledge-smoke-docs"}
COOKIES=$(mktemp)
trap 'rm -f "$COOKIES"' EXIT

json_field() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1" 2>/dev/null; }

rf_container() {
    # The RAGFlow *server* container (hosts /ragflow + api.utils.crypt), not
    # its tei/mysql/minio/redis/es01 dependency containers.
    docker ps --format '{{.Names}}' | grep 'ragflow' | grep -vE 'tei|mysql|minio|redis|es01' | head -1
}

encrypt_password() {
    local container
    container=$(rf_container)
    docker exec "$container" python3 -c "
import sys; sys.path.insert(0, '/ragflow')
from api.utils.crypt import crypt
print(crypt('$1'))" | tail -1
}

echo "== 1. register tenant $EMAIL (tolerates existing) =="
ENCRYPTED=$(encrypt_password "$PASSWORD")
curl -sS -X POST "$RF/api/v1/users" -H 'Content-Type: application/json' \
    -d "{\"nickname\":\"${EMAIL%%@*}\",\"email\":\"$EMAIL\",\"password\":\"$ENCRYPTED\"}" \
    | json_field "d.get('code')" > /tmp/bs_register_code || true
REGISTER_CODE=$(cat /tmp/bs_register_code 2>/dev/null || echo "?")
if [ "$REGISTER_CODE" = "0" ] || [ "$REGISTER_CODE" = "?" ]; then
    echo "   register: code=$REGISTER_CODE (already-registered or empty reply tolerated)"
elif [ "$REGISTER_CODE" = "103" ]; then
    echo "   register: user already exists (code=103), continuing"
else
    echo "   register: code=$REGISTER_CODE (unexpected; continuing to login)"
fi
rm -f /tmp/bs_register_code

echo "== 2. login =="
LOGIN_CODE=$(curl -sS -c "$COOKIES" -X POST "$RF/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$ENCRYPTED\"}" | json_field "d.get('code')")
[ "$LOGIN_CODE" = "0" ] || { echo "login failed (code=$LOGIN_CODE)"; exit 1; }
echo "   login ok"

echo "== 3. register provider $PROVIDER_NAME (tolerates existing) =="
curl -sS -b "$COOKIES" -X PUT "$RF/api/v1/providers" -H 'Content-Type: application/json' \
    -d "{\"provider_name\":\"$PROVIDER_NAME\"}" | head -c 120; echo

echo "== 4. ensure embedding instance $INSTANCE_NAME -> $EMB_BASE_URL =="
# Creating the same instance twice would defeat the single-active-instance
# fallback that two-part model references rely on — always check first.
INSTANCE_EXISTS=$(curl -sS -b "$COOKIES" "$RF/api/v1/providers/$PROVIDER_NAME/instances" \
    | json_field "any(i.get('instance_name') == '$INSTANCE_NAME' for i in (d.get('data') or []))")
if [ "$INSTANCE_EXISTS" = "True" ]; then
    echo "   instance exists, skipping"
else
    curl -sS -b "$COOKIES" -X POST "$RF/api/v1/providers/$PROVIDER_NAME/instances" \
        -H 'Content-Type: application/json' \
        -d "{
          \"instance_name\": \"$INSTANCE_NAME\",
          \"api_key\": \"sk-tei-local\",
          \"base_url\": \"$EMB_BASE_URL\",
          \"region\": \"\",
          \"model_info\": [{\"model_type\": [\"embedding\"], \"model_name\": \"$EMB_MODEL\", \"max_tokens\": 8192}]
        }" | head -c 200; echo
fi

echo "== 5. set tenant default embedding =="
curl -sS -b "$COOKIES" -X PATCH "$RF/api/v1/models/default" -H 'Content-Type: application/json' \
    -d "{\"model_type\": \"embedding\", \"model_provider\": \"$PROVIDER_NAME\", \"model_instance\": \"$INSTANCE_NAME\", \"model_name\": \"$EMB_MODEL\"}" \
    | head -c 120; echo

echo "== 6. find or create dataset $DATASET_NAME =="
DATASET_ID=""
for ID in $(curl -sS -b "$COOKIES" "$RF/api/v1/datasets?page_size=100" \
      | json_field "' '.join(x['id'] for x in (d.get('data') or []))"); do
    [ -z "$ID" ] && continue
    NAME=$(curl -sS -b "$COOKIES" "$RF/api/v1/datasets/$ID" | json_field "(d.get('data') or {}).get('name','')")
    if [ "$NAME" = "$DATASET_NAME" ]; then DATASET_ID=$ID; break; fi
done
if [ -z "$DATASET_ID" ]; then
    # Three-part composite name pins the instance deterministically; a
    # two-part name would depend on the single-instance fallback.
    DATASET_ID=$(curl -sS -b "$COOKIES" -X POST "$RF/api/v1/datasets" -H 'Content-Type: application/json' \
        -d "{\"name\":\"$DATASET_NAME\",\"description\":\"iDeer knowledge-dev smoke dataset\",\"embedding_model\":\"$EMB_MODEL@$INSTANCE_NAME@$PROVIDER_NAME\"}" \
        | json_field "(d.get('data') or {}).get('id','')")
    echo "   created dataset $DATASET_ID"
else
    echo "   reusing dataset $DATASET_ID"
fi
[ -n "$DATASET_ID" ] || { echo "dataset resolution failed"; exit 1; }

echo "== 7. upload smoke documents (name-deduplicated) =="
if [ -d "$DOCS_DIR" ] && [ -n "$(ls "$DOCS_DIR" 2>/dev/null)" ]; then
    EXISTING_DOCS=$(curl -sS -b "$COOKIES" "$RF/api/v1/datasets/$DATASET_ID/documents" \
        | json_field "','.join(x.get('name','') for x in ((d.get('data') or {}).get('docs') or []))")
    UPLOAD_ARGS=()
    UPLOADED=0
    for F in "$DOCS_DIR"/*; do
        [ -f "$F" ] || continue
        BASENAME=$(basename "$F")
        if grep -q ",$BASENAME," <<< ",$EXISTING_DOCS,"; then
            echo "   already present: $BASENAME"
            continue
        fi
        UPLOAD_ARGS+=(-F "file=@$F")
        UPLOADED=$((UPLOADED + 1))
    done
    if [ ${#UPLOAD_ARGS[@]} -gt 0 ]; then
        curl -sS -b "$COOKIES" -X POST "$RF/api/v1/datasets/$DATASET_ID/documents" "${UPLOAD_ARGS[@]}" > /dev/null
        echo "   uploaded $UPLOADED new document(s) from $DOCS_DIR"
    fi
else
    echo "   no docs dir at $DOCS_DIR — skipping (dataset kept as-is)"
fi

echo "== 8. parse pending documents and wait =="
DOC_IDS=$(curl -sS -b "$COOKIES" "$RF/api/v1/datasets/$DATASET_ID/documents" \
    | json_field "json.dumps([x['id'] for x in ((d.get('data') or {}).get('docs') or []) if x.get('run') not in ('DONE',)])")
if [ "$DOC_IDS" != "[]" ] && [ -n "$DOC_IDS" ]; then
    curl -sS -b "$COOKIES" -X POST "$RF/api/v1/datasets/$DATASET_ID/documents/parse" \
        -H 'Content-Type: application/json' -d "{\"document_ids\": $DOC_IDS}" > /dev/null
    echo "   parse triggered for $DOC_IDS"
fi
for _ in $(seq 1 60); do
    PENDING=$(curl -sS -b "$COOKIES" "$RF/api/v1/datasets/$DATASET_ID/documents" \
        | json_field "sum(1 for x in ((d.get('data') or {}).get('docs') or []) if x.get('run') not in ('DONE','FAIL'))")
    [ "$PENDING" = "0" ] && break
    sleep 5
done
curl -sS -b "$COOKIES" "$RF/api/v1/datasets/$DATASET_ID/documents" \
    | json_field "[(x.get('name'), x.get('run'), x.get('chunk_count')) for x in ((d.get('data') or {}).get('docs') or [])]"

echo "== 9. mint API token =="
API_KEY=$(curl -sS -b "$COOKIES" -X POST "$RF/api/v1/system/tokens" -H 'Content-Type: application/json' \
    -d '{"name":"ideer-knowledge-dev"}' | json_field "(d.get('data') or {}).get('token','')")
[ -n "$API_KEY" ] || { echo "token minting failed"; exit 1; }

echo
echo "================================================================"
echo "Bootstrap complete. Wire these into the iDeer host:"
echo "  .env:            RAGFLOW_API_KEY=$API_KEY"
echo "  config.yaml:     knowledge_search.datasets: [$DATASET_ID]"
echo "  config.yaml:     knowledge_search.base_url: http://localhost:9380"
echo "                   (Docker dev gateway: http://ragflow:9380)"
echo "================================================================"
