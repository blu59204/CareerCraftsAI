#!/usr/bin/env bash
# test_agents_smoke.sh — Smoke-test all CareerCraft AI agents.
# Requires: JWT env var set, backend running at localhost:8000.
# Usage: JWT=eyJ... bash scripts/test_agents_smoke.sh

set -euo pipefail

BASE="${BASE:-http://localhost:8000/api/v1}"
AUTH="${AUTH:-Authorization: Bearer ${JWT:?set JWT env var}}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

log_pass() { echo -e "${GREEN}PASS${NC} $1"; PASS=$((PASS+1)); }
log_fail() { echo -e "${RED}FAIL${NC} $1 — $2"; FAIL=$((FAIL+1)); }
log_skip() { echo -e "${YELLOW}SKIP${NC} $1 — $2"; }

run_agent_smoke() {
  local label="$1"; shift
  local task_type="$1"; shift
  local context="$1"; shift
  local expect="$1"; shift

  echo "--- $label ---"

  local resp
  resp=$(curl -s -m 10 -X POST "${BASE}/agents/run" \
    -H "${AUTH}" \
    -H "Content-Type: application/json" \
    -d "{\"task_type\":\"${task_type}\",\"context\":${context}}" 2>/dev/null || true)

  local run_id
  run_id=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null || true)

  if [ -z "$run_id" ]; then
    log_fail "$label" "No run_id received. Response: ${resp:0:200}"
    return
  fi

  local events=""
  local deadline=$(( $(date +%s) + 60 ))

  while [ $(date +%s) -lt $deadline ]; do
    events=$(curl -s -m 5 "${BASE}/agents/${run_id}/stream" -H "${AUTH}" 2>/dev/null || true)
    if echo "$events" | grep -q "event: complete\b"; then
      log_pass "$label"
      return
    fi
    if echo "$events" | grep -q "event: error\b"; then
      local err
      err=$(echo "$events" | grep "event: error" | python3 -c "import sys; print(sys.stdin.read().split('data:')[-1].strip()[:200])" 2>/dev/null || echo "unknown")
      log_fail "$label" "$err"
      return
    fi
    if echo "$events" | grep -q "event: checkpoint\b" && [ "$expect" = "checkpoint" ]; then
      log_pass "$label"
      return
    fi
    sleep 2
  done

  log_fail "$label" "Timed out after 60s"
}

echo "CareerCraft AI Agent Smoke Test"
echo "================================"
echo ""

run_agent_smoke "1. NL Search" "nl_job_search" '{"query":"backend engineer remote India"}' "checkpoint"
run_agent_smoke "2. Job Search" "job_search" '{"query":"Python developer","location":"Bengaluru"}' "complete"
run_agent_smoke "3. Resume Optimize" "resume_optimize" '{"jd_text":"We need a Python engineer with 5 years experience"}' "complete"
run_agent_smoke "4. Cover Letter" "cover_letter" '{"job_description":"Python engineer role at Google","company_name":"Google"}' "complete"
run_agent_smoke "5. LinkedIn Optimize" "linkedin_optimize" '{"target_role":"Software Engineer","industry":"Technology"}' "complete"
run_agent_smoke "6. Company Research" "company_research" '{"company_name":"Infosys"}' "complete"
run_agent_smoke "7. Salary Intelligence" "salary_intelligence" '{"role":"SDE-2","location":"Bangalore","experience_years":5}' "complete"
run_agent_smoke "8. Interview Coach" "interview_coach" '{"role":"Backend Engineer","interview_type":"behavioral","num_questions":2}' "complete"
run_agent_smoke "9. Interview Prep" "interview_prep" '{"role":"Backend Engineer","interview_type":"technical"}' "complete"
run_agent_smoke "10. Email (checkpoint)" "email" '{"recruiter_name":"Jane","recruiter_company":"Google","job_title":"SWE"}' "checkpoint"

echo ""
echo "================================"
echo -e "Results: ${GREEN}${PASS} PASS${NC}  ${RED}${FAIL} FAIL${NC}"
echo "================================"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
