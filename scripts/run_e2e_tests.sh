#!/usr/bin/env bash
# run_e2e_tests.sh — reproducible live E2E runner for CareerCraft AI.
#
# Signs in through the real Clerk UI, exercises every authenticated screen,
# and drives the agent matrix against a real running stack. Never approves
# an email send, LinkedIn outreach, or job application submit — those stay
# gated behind ALLOW_LIVE_SENDS=1 (see backend/tests/e2e/conftest.py::live_safety).
#
# Required environment variables:
#   TEST_JWT       Clerk session JWT for the API client
#   TEST_EMAIL     Clerk test account email (use a +clerk_test alias)
#   TEST_PASSWORD  Clerk test account password
#   WEB_URL        Frontend origin, e.g. http://localhost:3000
#   API_URL        Backend API base, e.g. http://localhost:8000/api/v1
#
# Optional:
#   TEST_OTP_CODE  Clerk test OTP (defaults to the fixed test code 424242)
#
# Usage:
#   ./scripts/run_e2e_tests.sh

set -euo pipefail

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }

echo ""
echo "=========================================="
echo " CareerCraft AI — Live E2E Test Runner"
echo "=========================================="
echo ""

# ── Step 1: Check Required Environment Variables ───────────────────────────

log_info "Checking environment variables..."

MISSING_VARS=()
for VAR in TEST_JWT TEST_EMAIL TEST_PASSWORD WEB_URL API_URL; do
    if [ -z "${!VAR:-}" ]; then
        MISSING_VARS+=("$VAR")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    log_fail "Missing required environment variables: ${MISSING_VARS[*]}"
    echo ""
    echo "Set them before running:"
    echo "  export TEST_JWT='eyJ...'"
    echo "  export TEST_EMAIL='cc.e2e+clerk_test@gmail.com'"
    echo "  export TEST_PASSWORD='your-password'"
    echo "  export WEB_URL='http://localhost:3000'"
    echo "  export API_URL='http://localhost:8000/api/v1'"
    echo ""
    echo "Optional:"
    echo "  export TEST_OTP_CODE='424242'   # defaults to the Clerk test code"
    echo "  export ALLOW_LIVE_SENDS=1       # opt in to real email/outreach/apply sends"
    exit 1
fi

export TEST_OTP_CODE="${TEST_OTP_CODE:-424242}"
log_pass "All required environment variables set"

# ── Step 2: Check Both Health URLs ──────────────────────────────────────────

# /health is served at the app root, not under the /api/v1 prefix that
# API_URL includes (see backend/app/main.py's @app.get("/health")) — strip
# the suffix before appending /health.
HEALTH_URL="${API_URL%/api/v1}/health"

log_info "Checking backend health at ${HEALTH_URL} ..."
if curl -sf --max-time 10 "${HEALTH_URL}" > /dev/null 2>&1; then
    log_pass "Backend is healthy"
else
    log_fail "Backend is not reachable at ${HEALTH_URL}. Run: docker compose up -d"
    exit 1
fi

log_info "Checking frontend at ${WEB_URL} ..."
if curl -sf --max-time 10 "${WEB_URL}" > /dev/null 2>&1; then
    log_pass "Frontend is reachable"
else
    log_fail "Frontend is not reachable at ${WEB_URL}. Run: docker compose up -d"
    exit 1
fi

# ── Step 2b: Check Authenticated Access ─────────────────────────────────────

log_info "Checking authenticated access at ${API_URL}/users/me ..."
ME_STATUS=$(curl -s -o /tmp/careercraft_preflight_me.json -w '%{http_code}' --max-time 10 \
    -H "Authorization: Bearer ${TEST_JWT}" "${API_URL}/users/me" 2>/dev/null || echo "000")
if [ "$ME_STATUS" = "200" ]; then
    log_pass "Authenticated /users/me reachable"
else
    log_fail "Authenticated /users/me returned HTTP ${ME_STATUS}. Check that TEST_JWT is a valid, unexpired Clerk session token."
    exit 1
fi

# ── Step 2c: Check the Configured Model Responds ────────────────────────────
# Also doubles as the embedding-provider check: RAG picks its embedding
# provider from the same active model (see get_embedding_provider in
# backend/app/services/rag_service.py), falling back to the backend's own
# EMBEDDING_PROVIDER env var for providers with no embeddings API (Anthropic,
# NVIDIA NIM) -- a backend-only setting this script has no way to read
# remotely, so that fallback case is a warning, not a failure.

log_info "Checking active model configuration at ${API_URL}/users/me/models ..."
MODELS_JSON=$(curl -sf --max-time 10 -H "Authorization: Bearer ${TEST_JWT}" "${API_URL}/users/me/models" 2>/dev/null || echo "")
ACTIVE_MODEL=$(printf '%s' "$MODELS_JSON" | python -c "
import json, sys
try:
    models = json.load(sys.stdin)
except ValueError:
    models = []
active = next((m for m in models if m.get('is_active')), None)
print(f\"{active['id']}|{active.get('provider','')}\" if active else '')
" 2>/dev/null || echo "")

if [ -z "$ACTIVE_MODEL" ]; then
    log_warn "No active model configured for the test account — skipping model test and embedding provider checks"
else
    ACTIVE_MODEL_ID="${ACTIVE_MODEL%%|*}"
    ACTIVE_PROVIDER="${ACTIVE_MODEL#*|}"

    MODEL_TEST_STATUS=$(curl -s -o /tmp/careercraft_preflight_model_test.json -w '%{http_code}' --max-time 65 \
        -H "Authorization: Bearer ${TEST_JWT}" -H "Content-Type: application/json" \
        -d "{\"model_id\": \"${ACTIVE_MODEL_ID}\"}" \
        "${API_URL}/users/me/models/test" 2>/dev/null || echo "000")
    if [ "$MODEL_TEST_STATUS" = "200" ]; then
        log_pass "Active model (${ACTIVE_PROVIDER}) responded to a live test call"
    else
        log_fail "Model test returned HTTP ${MODEL_TEST_STATUS}. Check the active model's API key at /settings/models."
        exit 1
    fi

    case "$ACTIVE_PROVIDER" in
        openai|google|ollama)
            log_pass "Embedding provider available via active model provider: ${ACTIVE_PROVIDER}"
            ;;
        *)
            log_warn "Active model provider '${ACTIVE_PROVIDER}' has no native embeddings API; RAG depends on the backend's EMBEDDING_PROVIDER fallback, which this script cannot verify remotely. Confirm EMBEDDING_PROVIDER is set to openai, google, or ollama in the deployed backend.env."
            ;;
    esac
fi

# ── Step 2d: Check Nango Connectivity ────────────────────────────────────────
# GET /integrations round-trips to Nango live (see list_connections in
# backend/app/api/v1/integrations.py) and returns 503 if the provider is
# unreachable or misconfigured -- exactly the signal we want here.

log_info "Checking integration provider connectivity at ${API_URL}/integrations ..."
INTEGRATIONS_STATUS=$(curl -s -o /tmp/careercraft_preflight_integrations.json -w '%{http_code}' --max-time 15 \
    -H "Authorization: Bearer ${TEST_JWT}" "${API_URL}/integrations" 2>/dev/null || echo "000")
if [ "$INTEGRATIONS_STATUS" = "200" ]; then
    log_pass "Nango integration gateway reachable"
else
    log_fail "Integrations endpoint returned HTTP ${INTEGRATIONS_STATUS} from ${API_URL}/integrations. Check NANGO_* configuration on the backend."
    exit 1
fi

# ── Step 2e: Temporal worker is polling ───────────────────────────────────
# Every agent run, job search and application executes on the Temporal
# worker. The API's /health reports how many workers poll the task queue;
# zero means runs would sit in "queued" forever, so fail fast here.
HEALTH_URL="${API_URL%/api/v1}/health"
HEALTH_JSON=$(curl -s --max-time 15 "$HEALTH_URL" 2>/dev/null || echo "")
if echo "$HEALTH_JSON" | grep -q '"workers":[1-9]'; then
    log_pass "Temporal worker is polling the task queue"
elif echo "$HEALTH_JSON" | grep -q '"temporal"'; then
    log_fail "No Temporal worker is polling (health: $(echo "$HEALTH_JSON" | tr -d '\n' | head -c 300)). Start the temporal-worker service."
    exit 1
else
    log_warn "Could not read ${HEALTH_URL} — skipping the Temporal worker check"
fi

# ── Step 3: Generate Test Fixtures ──────────────────────────────────────────

log_info "Generating test fixtures..."
if python backend/tests/fixtures/create_test_fixtures.py; then
    log_pass "Test fixtures created"
else
    log_fail "Failed to create test fixtures"
    exit 1
fi

# ── Step 4: Verify Chromium Installed ───────────────────────────────────────

log_info "Checking Playwright Chromium..."
if python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch(); p.stop()" 2>/dev/null; then
    log_pass "Chromium is ready"
else
    log_fail "Chromium not installed. Run: playwright install chromium"
    exit 1
fi

# ── Step 5: Run the Live Suite ───────────────────────────────────────────────

mkdir -p backend/tests/e2e/.artifacts

echo ""
echo "=========================================="
echo " Running Live E2E Test Suite"
echo "=========================================="
echo ""

export RUN_LIVE_E2E=1

RUN_LIVE_E2E=1 python -m pytest \
    backend/tests/e2e/test_harness_contract.py \
    backend/tests/e2e/test_live_screen_smoke.py \
    backend/tests/e2e/test_live_user_journeys.py \
    backend/tests/e2e/test_agent_matrix.py \
    -m e2e -v --tb=short \
    2>&1 | tee backend/tests/e2e/results.log

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
echo " Test Suite Complete"
echo "=========================================="
echo "  Log: backend/tests/e2e/results.log"
echo "=========================================="

exit "$EXIT_CODE"
