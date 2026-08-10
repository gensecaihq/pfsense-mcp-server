#!/usr/bin/env bash
# End-to-end MCP protocol smoke test using the official MCP Inspector CLI
# (https://github.com/modelcontextprotocol/inspector).
#
# Unlike the pytest suite (which exercises tools in-process), this drives the
# server over the real MCP wire protocol on both transports:
#
#   stdio:  initialize handshake, tools/list count + annotations,
#           guardrail confirm-gate on a destructive tool, read-only mode
#   http:   /health probe, 401 without bearer token, 403 on bad Origin,
#           tools/list through an authenticated Inspector session
#
# Requirements: node/npx, python with requirements.txt installed, curl, jq.
# No pfSense instance is needed — the server is pointed at an unreachable
# TEST-NET address and must still start (bounded preflight) and respond.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
EXPECTED_TOOLS=333
EXPECTED_READONLY=131
HTTP_PORT="${SMOKE_HTTP_PORT:-3999}"
TOKEN="inspector-smoke-test-token-0123456789"

export PFSENSE_URL="https://192.0.2.1"   # TEST-NET-1: guaranteed unreachable
export PFSENSE_API_KEY="smoke-test-dummy-key"
export API_TIMEOUT=2

# The Inspector CLI parses flag-like args after the target command as its own
# options (it would eat `-m src.main`), and it does NOT forward the parent
# process environment to the spawned server (only -e vars plus a minimal
# base). So wrap the server invocation in an argument-less script that also
# carries its own environment; per-phase overrides (MCP_READ_ONLY) still go
# through -e.
WRAPPER="$(mktemp -d)/run-server.sh"
cat > "$WRAPPER" <<EOF
#!/bin/sh
export PFSENSE_URL="$PFSENSE_URL"
export PFSENSE_API_KEY="$PFSENSE_API_KEY"
export API_TIMEOUT="$API_TIMEOUT"
cd "$REPO_ROOT"
exec "$PYTHON" -m src.main
EOF
chmod +x "$WRAPPER"

INSPECTOR=(npx -y @modelcontextprotocol/inspector --cli)

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "  ok: $*"; }

echo "== stdio: tools/list =="
LIST_JSON="$("${INSPECTOR[@]}" "$WRAPPER" --method tools/list --format json 2>/dev/null)"
COUNT="$(jq '.result.tools | length' <<<"$LIST_JSON")"
[ "$COUNT" -eq "$EXPECTED_TOOLS" ] || fail "expected $EXPECTED_TOOLS tools, got $COUNT"
pass "$COUNT tools listed"

NO_ANN="$(jq '[.result.tools[] | select(has("annotations") | not)] | length' <<<"$LIST_JSON")"
[ "$NO_ANN" -eq 0 ] || fail "$NO_ANN tools missing ToolAnnotations"
pass "every tool carries ToolAnnotations"

NO_DESC="$(jq '[.result.tools[] | select((.description // "") == "")] | length' <<<"$LIST_JSON")"
[ "$NO_DESC" -eq 0 ] || fail "$NO_DESC tools missing a description"
pass "every tool has a description"

echo "== stdio: guardrail confirm gate over the wire =="
GATE_JSON="$("${INSPECTOR[@]}" "$WRAPPER" --method tools/call \
  --tool-name delete_firewall_rule --tool-arg rule_id=1 --format json 2>/dev/null)"
APPROVAL="$(jq -r '.result.content[0].text | fromjson | .approval_required' <<<"$GATE_JSON")"
[ "$APPROVAL" = "true" ] || fail "destructive tool did not demand confirm=True (got: $APPROVAL)"
pass "delete without confirm=True is blocked with approval_required"

echo "== stdio: unreachable pfSense surfaces a descriptive error =="
ERR_JSON="$("${INSPECTOR[@]}" "$WRAPPER" --method tools/call \
  --tool-name system_status --format json 2>/dev/null)"
ERR_MSG="$(jq -r '.result.content[0].text | fromjson | .error' <<<"$ERR_JSON")"
case "$ERR_MSG" in
  *"Cannot reach pfSense"*) pass "error message is descriptive: ${ERR_MSG:0:60}..." ;;
  *) fail "expected a descriptive connectivity error, got: '$ERR_MSG'" ;;
esac

echo "== stdio: MCP_READ_ONLY exposes only read tools =="
RO_JSON="$("${INSPECTOR[@]}" "$WRAPPER" --method tools/list --format json -e MCP_READ_ONLY=true 2>/dev/null)"
RO_COUNT="$(jq '.result.tools | length' <<<"$RO_JSON")"
[ "$RO_COUNT" -eq "$EXPECTED_READONLY" ] || fail "read-only mode: expected $EXPECTED_READONLY tools, got $RO_COUNT"
LEAK="$(jq '[.result.tools[] | select(.annotations.readOnlyHint != true)] | length' <<<"$RO_JSON")"
[ "$LEAK" -eq 0 ] || fail "read-only mode leaked $LEAK non-read tools"
pass "read-only mode: $RO_COUNT tools, no mutating tool leaked"

echo "== http: auth and origin enforcement =="
MCP_API_KEY="$TOKEN" "$PYTHON" -m src.main -t streamable-http --port "$HTTP_PORT" \
  > /tmp/inspector-smoke-http.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$HTTP_PORT/health" >/dev/null 2>&1 && break
  sleep 1
done

HEALTH="$(curl -sf "http://127.0.0.1:$HTTP_PORT/health")"
[ "$(jq -r .status <<<"$HEALTH")" = "ok" ] || fail "/health did not return ok"
pass "/health responds without auth"

CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$HTTP_PORT/mcp" \
  -H 'Content-Type: application/json' -d '{}')"
[ "$CODE" = "401" ] || fail "expected 401 without bearer token, got $CODE"
pass "requests without a bearer token are rejected (401)"

CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$HTTP_PORT/mcp" \
  -H "Authorization: Bearer $TOKEN" -H 'Origin: https://evil.example.com' \
  -H 'Content-Type: application/json' -d '{}')"
[ "$CODE" = "403" ] || fail "expected 403 for disallowed Origin, got $CODE"
pass "disallowed Origin is rejected (403)"

echo "== http: authenticated Inspector session =="
HTTP_LIST="$("${INSPECTOR[@]}" "http://127.0.0.1:$HTTP_PORT/mcp" --transport http \
  --header "Authorization: Bearer $TOKEN" --method tools/list --format json 2>/dev/null)"
HTTP_COUNT="$(jq '.result.tools | length' <<<"$HTTP_LIST")"
[ "$HTTP_COUNT" -eq "$EXPECTED_TOOLS" ] || fail "http tools/list: expected $EXPECTED_TOOLS, got $HTTP_COUNT"
pass "http transport lists $HTTP_COUNT tools with valid token"

echo
echo "MCP Inspector smoke test: all checks passed."
