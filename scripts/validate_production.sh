#!/usr/bin/env bash
# =============================================================================
# CareerCraft AI — Production Validation Script
# =============================================================================
# Run: bash scripts/validate_production.sh
# Requires: curl, jq, nc, openssl, psql, docker
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0
total=0

pass() { echo -e "${GREEN}[PASS]${NC} $1"; pass_count=$((pass_count + 1)); total=$((total + 1)); }
fail() { echo -e "${RED}[FAIL]${NC} $1 — $2"; fail_count=$((fail_count + 1)); total=$((total + 1)); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Load env
: "${APP_ENV:=}"
: "${APP_SECRET_KEY:=}"
: "${DOMAIN:=localhost}"
: "${DATABASE_URL:=}"
: "${SUPABASE_URL:=}"

echo "========================================="
echo " CareerCraft AI Production Validation"
echo " DOMAIN=${DOMAIN}"
echo "========================================="
echo ""

# ── 1. APP_ENV ────────────────────────────────────────────────
if [ "${APP_ENV}" = "production" ]; then
  pass "APP_ENV is set to production"
else
  fail "APP_ENV is not production (got: ${APP_ENV:-unset})" "Set APP_ENV=production in .env"
fi

# ── 2. APP_SECRET_KEY length ──────────────────────────────────
key_len=$(printf "%s" "${APP_SECRET_KEY}" | wc -c | tr -d ' ')
if [ "${key_len}" -ge 64 ]; then
  pass "APP_SECRET_KEY is 64+ characters (got ${key_len})"
else
  fail "APP_SECRET_KEY too short (${key_len} chars, need 64+)" "Generate: openssl rand -hex 32"
fi

# ── 3. Health endpoint ────────────────────────────────────────
if curl -sf "https://${DOMAIN}/health" > /dev/null 2>&1; then
  health=$(curl -s "https://${DOMAIN}/health")
  if echo "$health" | grep -q '"status":"ok"'; then
    pass "GET /health returns status=ok"
  else
    fail "GET /health returns unexpected body" "Expected {\"status\":\"ok\"}, got: $health"
  fi
else
  fail "GET /health is unreachable" "Check that backend is running and TLS is configured"
fi

# ── 4. /internal/ returns 404 ─────────────────────────────────
internal_code=$(curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}/internal/")
if [ "${internal_code}" = "404" ]; then
  pass "GET /internal/ returns 404 (blocked)"
else
  fail "GET /internal/ returns ${internal_code} (not blocked)" "Check nginx location /internal/ block rule"
fi

# ── 5. /docs returns 404 (disabled in production) ──────────────
docs_code=$(curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}/docs")
if [ "${docs_code}" = "404" ]; then
  pass "GET /docs returns 404 (disabled in production)"
else
  warn "GET /docs returns ${docs_code} — docs may be exposed in production"
fi

# ── 6. SSL certificate check ──────────────────────────────────
if command -v openssl &> /dev/null; then
  if cert_info=$(echo | openssl s_client -servername "${DOMAIN}" -connect "${DOMAIN}:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null); then
    expiry=$(echo "$cert_info" | sed 's/notAfter=//')
    expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$expiry" +%s 2>/dev/null || echo 0)
    now_epoch=$(date +%s)
    days_left=$(( (expiry_epoch - now_epoch) / 86400 ))
    if [ "$days_left" -gt 30 ]; then
      pass "SSL certificate valid for ${days_left} days"
    else
      fail "SSL certificate expires in ${days_left} days (< 30)" "Renew with certbot"
    fi
  else
    fail "SSL certificate check failed" "Verify TLS is configured on port 443"
  fi
fi

# ── 7. Redis not exposed publicly ─────────────────────────────
if command -v nc &> /dev/null; then
  if nc -zv -w3 "${DOMAIN}" 6379 2>/dev/null; then
    fail "Redis port 6379 is reachable from public internet" "Block port 6379 in firewall"
  else
    pass "Redis port 6379 is not publicly reachable"
  fi
fi

# ── 8. Docker containers healthy ───────────────────────────────
if command -v docker &> /dev/null && command -v jq &> /dev/null; then
  unhealthy=$(docker compose ps --format json 2>/dev/null | jq -r 'select(.Health != "healthy") | .Name' 2>/dev/null || echo "")
  if [ -z "$unhealthy" ]; then
    pass "All Docker containers healthy"
  else
    fail "Unhealthy containers: ${unhealthy}" "Run: docker compose ps"
  fi
else
  warn "Skipping Docker container check (docker/jq not available)"
fi

# ── 9. BullMQ queue not stuck ─────────────────────────────────
if [ -n "${DATABASE_URL:-}" ] || command -v redis-cli &> /dev/null; then
  if command -v redis-cli &> /dev/null; then
    queue_len=$(redis-cli llen "bull:agent-queue:wait" 2>/dev/null || echo "-1")
    if [ "${queue_len}" = "-1" ] || [ "${queue_len}" = "" ]; then
      warn "Could not check BullMQ queue length (Redis unreachable or key format changed)"
    elif [ "${queue_len}" -lt 100 ]; then
      pass "BullMQ wait queue length: ${queue_len} (OK, < 100)"
    else
      fail "BullMQ wait queue has ${queue_len} items (stuck?)" "Check worker logs"
    fi
  else
    warn "redis-cli not available — skipping BullMQ queue check"
  fi
fi

# ── 10. pgvector extension enabled ─────────────────────────────
if [ -n "${DATABASE_URL:-}" ] && command -v psql &> /dev/null; then
  pgvector=$(psql "${DATABASE_URL}" -t -c "SELECT extname FROM pg_extension WHERE extname='vector';" 2>/dev/null | tr -d '[:space:]')
  if [ "${pgvector}" = "vector" ]; then
    pass "pgvector extension enabled"
  else
    fail "pgvector extension not enabled" "Run: CREATE EXTENSION IF NOT EXISTS vector;"
  fi
else
  warn "Skipping pgvector check (psql not available or DATABASE_URL not set)"
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "========================================="
echo -e " RESULTS: ${GREEN}${pass_count} PASS${NC} / ${RED}${fail_count} FAIL${NC} / ${YELLOW}$((total - pass_count - fail_count)) WARN${NC}"
echo "========================================="

if [ "${fail_count}" -gt 0 ]; then
  exit 1
else
  exit 0
fi
