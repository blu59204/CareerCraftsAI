"""
test_rls_policies.py

Static analysis of Supabase migration SQL files to verify:
1. Key tables have ENABLE ROW LEVEL SECURITY in migration history.
2. All INSERT/UPDATE/ALL policies on user-scoped tables have WITH CHECK clauses.
3. The langchain_pg_embedding HNSW index has explicit m and ef_construction params.

These tests do NOT require a running database — they parse raw SQL text.
"""

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Resolve migrations dir: walk up from this file to the repo root.
# Layout (worktree):  <repo>/.claude/worktrees/swarm-fix/backend/tests/unit/test_rls_policies.py
#   parents[0] = unit/, [1] = tests/, [2] = backend/, [3] = swarm-fix/ (worktree root)
# Layout (main repo): <repo>/backend/tests/unit/test_rls_policies.py
#   parents[0] = unit/, [1] = tests/, [2] = backend/, [3] = repo root
# In both cases parents[3] / "supabase" / "migrations" resolves correctly IF the
# worktree has the migrations dir — but the worktree only has the new file 0032.
# So we prefer the main checkout's migrations dir when the worktree's copy is
# incomplete (< 30 files), falling back to the worktree path.

def _find_migrations_dir() -> Path:
    # Use os.path.abspath to avoid Path.resolve() adding a spurious drive prefix
    # in Git Bash on Windows (/d/ -> D:\d\).
    _this_file = Path(os.path.abspath(__file__))
    # Layout (main repo): <repo>/backend/tests/unit/test_rls_policies.py
    #   parents[3] = repo root  -> repo/supabase/migrations  (full set, 30+ files)
    # Layout (worktree): <repo>/.claude/worktrees/<name>/backend/tests/unit/...
    #   parents[3] = worktree root -> worktree/supabase/migrations  (only 0032)
    for depth in (3, 4, 5):
        if depth >= len(_this_file.parents):
            continue
        candidate = _this_file.parents[depth] / "supabase" / "migrations"
        if candidate.exists() and len(list(candidate.glob("*.sql"))) >= 20:
            return candidate
    # Fallback: if we're in the worktree but the main repo has the full set,
    # detect by checking if any ancestor has supabase/migrations with 20+ files.
    _path = _this_file
    for _ in range(8):
        _path = _path.parent
        candidate = _path / "supabase" / "migrations"
        if candidate.exists() and len(list(candidate.glob("*.sql"))) >= 20:
            return candidate
    raise FileNotFoundError(f"Cannot locate supabase/migrations from {__file__}")

MIGRATIONS_DIR = _find_migrations_dir()


def _all_migration_sql() -> str:
    """Return the concatenated content of all migration files in order."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    assert files, f"No migration files found in {MIGRATIONS_DIR}"
    parts = []
    for f in files:
        parts.append(f"-- FILE: {f.name}\n")
        parts.append(f.read_text(encoding="utf-8"))
        parts.append("\n")
    return "\n".join(parts)


def _migration_sql_for(filename: str) -> str:
    path = MIGRATIONS_DIR / filename
    assert path.exists(), f"Migration file not found: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture(scope="module")
def all_sql() -> str:
    return _all_migration_sql()


# ---------------------------------------------------------------------------
# Test 1: ENABLE ROW LEVEL SECURITY on core tables
# ---------------------------------------------------------------------------

CORE_RLS_TABLES = [
    "users",
    "user_model_settings",
    "user_documents",
    "job_applications",
    "agent_runs",
]

SECONDARY_RLS_TABLES = [
    "cover_letter_versions",
    "interview_sessions",
    "salary_reports",
    "company_intel",
    "resume_personas",
    "linkedin_outreach_queue",
    "ats_scores",
    "user_preferences",
    "agent_memory_episodes",
    "agent_memory_learnings",
    "agent_memory_preferences",
    "agent_memory_procedures",
    "user_memories",
    "agent_episodes",
    "agent_learnings",
    "memory_access_log",
]


@pytest.mark.parametrize("table", CORE_RLS_TABLES + SECONDARY_RLS_TABLES)
def test_rls_enabled_for_table(all_sql, table):
    """Each table must have ENABLE ROW LEVEL SECURITY in migration history."""
    # Match: ALTER TABLE [schema.]<table> ENABLE ROW LEVEL SECURITY
    # Also matches inside DO $$ blocks with EXECUTE format(...)
    pattern = re.compile(
        rf"ALTER\s+TABLE\s+(?:public\.)?['\"]?{re.escape(table)}['\"]?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
        re.IGNORECASE,
    )
    assert pattern.search(all_sql), (
        f"Table '{table}' never has ENABLE ROW LEVEL SECURITY in any migration"
    )


# ---------------------------------------------------------------------------
# Test 2: WITH CHECK clauses present on user-scoped tables
# ---------------------------------------------------------------------------

# Tables that hold user data and must have WITH CHECK on their policies.
# agent_learnings and langchain_* are excluded — they use deny/service_role
# policies with USING (false) / USING (true), not user-id checks.
USER_SCOPED_TABLES = [
    "users",
    "user_model_settings",
    "user_documents",
    "job_applications",
    "leads",
    "agent_runs",
    "cover_letter_versions",
    "interview_sessions",
    "salary_reports",
    "company_intel",
    "resume_personas",
    "linkedin_outreach_queue",
    "ats_scores",
    "user_preferences",
    "agent_memory_episodes",
    "agent_memory_learnings",
    "agent_memory_preferences",
    "agent_memory_procedures",
    "user_memories",
    "agent_episodes",
    "memory_access_log",
]


@pytest.mark.parametrize("table", USER_SCOPED_TABLES)
def test_insert_policies_have_with_check(all_sql, table):
    """
    For each user-scoped table, find all CREATE POLICY blocks that cover
    INSERT/UPDATE/ALL and assert that at least one uses WITH CHECK.

    Strategy: extract all CREATE POLICY ... ON <table> blocks and check
    that the final (latest) policy definition for that table includes
    WITH CHECK.
    """
    # Find all CREATE POLICY blocks for this table
    policy_pattern = re.compile(
        rf"CREATE\s+POLICY\s+\w+\s+ON\s+(?:public\.)?{re.escape(table)}\b(.*?)(?=CREATE\s+POLICY|DROP\s+POLICY|ALTER\s+TABLE|--\s*FILE:|$)",
        re.IGNORECASE | re.DOTALL,
    )
    matches = policy_pattern.findall(all_sql)
    assert matches, f"No CREATE POLICY found for table '{table}'"

    # The last match is the effective (most recent) policy body
    last_policy_body = matches[-1]

    # Check it contains WITH CHECK
    assert re.search(r"\bWITH\s+CHECK\b", last_policy_body, re.IGNORECASE), (
        f"Last policy on '{table}' is missing WITH CHECK clause.\n"
        f"Policy body snippet: {last_policy_body[:300]}"
    )


# ---------------------------------------------------------------------------
# Test 3: No USING (true) without WITH CHECK on user-scoped tables
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table", USER_SCOPED_TABLES)
def test_no_open_using_true_policy(all_sql, table):
    """
    Policies with USING (true) and no user_id filter allow all rows to be
    read — this is only acceptable for service_role/deny patterns, not for
    user-scoped tables.
    """
    policy_pattern = re.compile(
        rf"CREATE\s+POLICY\s+\w+\s+ON\s+(?:public\.)?{re.escape(table)}\b(.*?)(?=CREATE\s+POLICY|DROP\s+POLICY|ALTER\s+TABLE|--\s*FILE:|$)",
        re.IGNORECASE | re.DOTALL,
    )
    matches = policy_pattern.findall(all_sql)
    for body in matches:
        # If USING (true) appears, it must be scoped to service_role
        if re.search(r"USING\s*\(\s*true\s*\)", body, re.IGNORECASE):
            assert re.search(r"\bTO\s+service_role\b", body, re.IGNORECASE), (
                f"Table '{table}' has USING (true) policy not scoped to service_role.\n"
                f"Body: {body[:300]}"
            )


# ---------------------------------------------------------------------------
# Test 4: HNSW index on langchain_pg_embedding has correct params
# ---------------------------------------------------------------------------

def test_hnsw_index_langchain_embedding():
    """
    The HNSW index on langchain_pg_embedding must use:
    - vector_cosine_ops
    - m = 16
    - ef_construction = 64
    """
    sql = _migration_sql_for("0025_hnsw_index_embeddings.sql")

    assert re.search(r"vector_cosine_ops", sql, re.IGNORECASE), \
        "langchain_pg_embedding HNSW index must use vector_cosine_ops"

    assert re.search(r"\bm\s*=\s*16\b", sql), \
        "langchain_pg_embedding HNSW index must have m = 16"

    assert re.search(r"\bef_construction\s*=\s*64\b", sql), \
        "langchain_pg_embedding HNSW index must have ef_construction = 64"


# ---------------------------------------------------------------------------
# Test 5: HNSW indexes on user_memories / agent_episodes in 0032 fix
#         have explicit params
# ---------------------------------------------------------------------------

def test_hnsw_params_explicit_in_fix_migration():
    """
    Migration 0032 must recreate user_memories_hnsw and agent_episodes_hnsw
    with explicit m=16, ef_construction=64.
    """
    sql = _migration_sql_for("0032_rls_and_hnsw_fixes.sql")

    assert re.search(r"user_memories_hnsw", sql, re.IGNORECASE), \
        "0032 must recreate user_memories_hnsw"
    assert re.search(r"agent_episodes_hnsw", sql, re.IGNORECASE), \
        "0032 must recreate agent_episodes_hnsw"

    # Both must have explicit params
    assert len(re.findall(r"\bm\s*=\s*16\b", sql)) >= 2, \
        "0032 must set m=16 for both HNSW indexes"
    assert len(re.findall(r"\bef_construction\s*=\s*64\b", sql)) >= 2, \
        "0032 must set ef_construction=64 for both HNSW indexes"


# ---------------------------------------------------------------------------
# Test 6: agent_learnings gets a deny policy in 0032
# ---------------------------------------------------------------------------

def test_agent_learnings_gets_deny_policy():
    """
    Migration 0032 must add an explicit deny policy for authenticated users
    on agent_learnings (table has no user_id, RLS on with no prior policy
    was a silent-failure bug).
    """
    sql = _migration_sql_for("0032_rls_and_hnsw_fixes.sql")

    assert re.search(r"agent_learnings_deny_authenticated", sql, re.IGNORECASE), \
        "0032 must create agent_learnings_deny_authenticated policy"

    assert re.search(r"agent_learnings_service_role", sql, re.IGNORECASE), \
        "0032 must create agent_learnings_service_role policy"


# ---------------------------------------------------------------------------
# Test 7: Final policies all use auth.jwt()->>'sub' (not stale clerk_id)
# ---------------------------------------------------------------------------

def test_no_clerk_id_in_final_policies(all_sql):
    """
    The *final* (latest) policy for each named policy must not reference
    the old clerk_id column. Early migrations (0008) used clerk_id but
    were superseded by DROP POLICY + recreate in later migrations, so we
    only check that no policy name whose most recent CREATE uses clerk_id
    is still live (i.e. not followed by a DROP POLICY for that name).

    Strategy: collect every CREATE POLICY <name> block across all files,
    then for each policy name keep only the last CREATE. Check that last
    CREATE doesn't use clerk_id.
    """
    # Extract (name, body) pairs for every CREATE POLICY in document order
    pattern = re.compile(
        r"CREATE\s+POLICY\s+(\w+)\s+ON\s+\S+\b(.*?)(?=CREATE\s+POLICY|DROP\s+POLICY|ALTER\s+TABLE|--\s*FILE:|$)",
        re.IGNORECASE | re.DOTALL,
    )
    # Build dict: policy_name -> last seen body (later files overwrite earlier)
    latest: dict = {}
    for name, body in pattern.findall(all_sql):
        latest[name.lower()] = body

    for name, body in latest.items():
        assert not re.search(r"\bclerk_id\b", body, re.IGNORECASE), (
            f"Final policy '{name}' still references clerk_id:\n{body[:400]}"
        )
