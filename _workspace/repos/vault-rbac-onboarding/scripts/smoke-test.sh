#!/usr/bin/env bash
# End-to-end proof that isolation works: team A's CI token can't read team B's secrets.
set -euo pipefail

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-dev-root-token}"

api() { curl -fsS -H "X-Vault-Token: $1" "${@:2}"; }
code() { curl -s -o /dev/null -w '%{http_code}' -H "X-Vault-Token: $1" "${@:2}"; }

echo "==> seed secrets"
api "$VAULT_TOKEN" -X POST -d '{"data":{"password":"s3cr3t"}}' "$VAULT_ADDR/v1/kv-payments/data/prod/db" >/dev/null
api "$VAULT_TOKEN" -X POST -d '{"data":{"password":"other"}}' "$VAULT_ADDR/v1/kv-scoring/data/prod/db" >/dev/null

login() {
  local role=$1 rid sid
  rid=$(api "$VAULT_TOKEN" "$VAULT_ADDR/v1/auth/approle/role/$role/role-id" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"]["role_id"])')
  sid=$(api "$VAULT_TOKEN" -X POST "$VAULT_ADDR/v1/auth/approle/role/$role/secret-id" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"]["secret_id"])')
  curl -fsS -X POST -d "{\"role_id\":\"$rid\",\"secret_id\":\"$sid\"}" "$VAULT_ADDR/v1/auth/approle/login" \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["auth"]["client_token"])'
}

tok=$(login payments-prod-ci)

own=$(code "$tok" "$VAULT_ADDR/v1/kv-payments/data/prod/db")
foreign=$(code "$tok" "$VAULT_ADDR/v1/kv-scoring/data/prod/db")
otherenv=$(code "$tok" "$VAULT_ADDR/v1/kv-payments/data/stage/db")

echo "own team/env      : $own   (expect 200)"
echo "other team        : $foreign (expect 403)"
echo "other environment : $otherenv (expect 403)"
if [[ $own == 200 && $foreign == 403 && $otherenv == 403 ]]; then echo "PASS"; else echo "FAIL"; exit 1; fi
