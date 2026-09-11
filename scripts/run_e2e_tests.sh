#!/usr/bin/env bash
# run_tests.sh — Full CareerCraft AI E2E test suite runner.
#
# Usage:
#   bash tests/e2e/run_tests.sh
#
# Prerequisites:
#   1. Docker Compose stack running: docker compose up -d
#   2. Test user exists in Supabase with uploaded resume and configured API key
#   3. Environment variables set (see checks below)
#   4. Python deps installed: pip install pytest-playwright playwright httpx reportlab
#   5. Chromium installed: playwright install chromium

set -euo pipefail

cd "$(dirname "$0")/../.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }

echo ""
echo "=========================================="
echo " CareerCraft AI — E2E Test Suite Runner"
echo "=========================================="
echo ""

# ── Step 1: Check Required Environment Variables ──────────────────────────

log_info "Checking environment variables..."

MISSING_VARS=()
for VAR in TEST_EMAIL TEST_PASSWORD TEST_JWT; do
    if [ -z "${!VAR:-}" ]; then
        MISSING_VARS+=("$VAR")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    log_fail "Missing required environment variables: ${MISSING_VARS[*]}"
    echo ""
    echo "Set them before running:"
    echo "  export TEST_EMAIL='testuser@email.com'"
    echo "  export TEST_PASSWORD='your-password'"
    echo "  export TEST_JWT='eyJ...'"
    echo ""
    echo "Optional but recommended:"
    echo "  export TEST_JOB_URL='https://www.naukri.com/job-listings/...'"
    echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
    exit 1
fi

for VAR in TEST_JOB_URL ANTHROPIC_API_KEY; do
    if [ -z "${!VAR:-}" ]; then
        log_warn "$VAR not set — tests that need it will be skipped"
    fi
done

export RUN_E2E=1
log_pass "All required environment variables set"

# ── Step 2: Check Docker Stack Health ──────────────────────────────────────

log_info "Checking backend health at http://localhost:8000/api/v1/health ..."
if curl -sf --max-time 10 "http://localhost:8000/api/v1/health" > /dev/null 2>&1; then
    log_pass "Backend is healthy"
else
    log_fail "Backend is not reachable. Run: docker compose up -d"
    exit 1
fi

# ── Step 3: Check Frontend ─────────────────────────────────────────────────

log_info "Checking frontend at http://localhost:3000 ..."
if curl -sf --max-time 10 "http://localhost:3000" > /dev/null 2>&1; then
    log_pass "Frontend is running"
else
    log_warn "Frontend not reachable at http://localhost:3000 — UI tests will fail"
fi

# ── Step 5: Generate Test Fixtures ─────────────────────────────────────────

log_info "Generating test fixtures..."
if python tests/fixtures/create_test_fixtures.py; then
    log_pass "Test fixtures created"
else
    log_fail "Failed to create test fixtures"
    exit 1
fi

# ── Step 6: Verify Chromium Installed ──────────────────────────────────────

log_info "Checking Playwright Chromium..."
if python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch(); p.stop()" 2>/dev/null; then
    log_pass "Chromium is ready"
else
    log_fail "Chromium not installed. Run: playwright install chromium"
    exit 1
fi

# ── Step 7: Create Output Directories ──────────────────────────────────────

mkdir -p tests/e2e/screenshots tests/e2e/videos tests/e2e/outputs tests/fixtures
log_info "Output directories created"

# ── Step 8: Run the Test Suite ─────────────────────────────────────────────

echo ""
echo "=========================================="
echo " Running E2E Test Suite"
echo "=========================================="
echo ""

START_TIME=$(date +%s)

pytest \
    tests/e2e/test_careercraft_full.py \
    -v \
    -s \
    --headed \
    --slowmo=500 \
    --tb=short \
    --color=yes \
    2>&1 | tee tests/e2e/results.log

EXIT_CODE=${PIPESTATUS[0]}

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# ── Step 9: Print Summary ──────────────────────────────────────────────────

echo ""
echo "=========================================="
echo " Test Suite Complete"
echo "=========================================="
echo "  Duration: ${DURATION}s"

PASS_COUNT=$(grep -c "PASSED" tests/e2e/results.log 2>/dev/null || echo 0)
FAIL_COUNT=$(grep -c "FAILED" tests/e2e/results.log 2>/dev/null || echo 0)

echo -e "  Result:   ${GREEN}PASSED=${PASS_COUNT}${NC} ${RED}FAILED=${FAIL_COUNT}${NC}"
echo "  Log:      tests/e2e/results.log"
echo "  Screens:  tests/e2e/screenshots/"
echo "  Videos:   tests/e2e/videos/"
echo "=========================================="

exit $EXIT_CODE
