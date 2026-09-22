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

log_info "Checking backend health at ${API_URL}/health ..."
if curl -sf --max-time 10 "${API_URL}/health" > /dev/null 2>&1; then
    log_pass "Backend is healthy"
else
    log_fail "Backend is not reachable at ${API_URL}/health. Run: docker compose up -d"
    exit 1
fi

log_info "Checking frontend at ${WEB_URL} ..."
if curl -sf --max-time 10 "${WEB_URL}" > /dev/null 2>&1; then
    log_pass "Frontend is reachable"
else
    log_fail "Frontend is not reachable at ${WEB_URL}. Run: docker compose up -d"
    exit 1
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
