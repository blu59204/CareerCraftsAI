# Security Audit — Implementation Tasks

## Status: ✅ Complete

All 10 security findings have been remediated.

## Tasks

- [x] 1. AUTH-001: Pin JWT algorithm to HS256 only
  - Rewrote `backend/app/core/supabase_auth.py` to use pinned `algorithms=["HS256"]`
  - Removed dual-algorithm path (ES256 fallback) that read alg from untrusted header
  - Tokens with alg:none or unsupported algorithms are rejected

- [x] 2. AUTHZ-001: Fix RLS policies to reference supabase_uid
  - Created `supabase/migrations/0018_fix_rls_supabase_uid.sql`
  - Drops old clerk_id-based policies, recreates with `supabase_uid = auth.jwt() ->> 'sub'`

- [x] 3. INFRA-001: Add Redis authentication
  - Added `--requirepass ${REDIS_PASSWORD:-changeme}` to Redis command in docker-compose.yml
  - Updated healthcheck to pass password
  - Added REDIS_PASSWORD to .env.example

- [x] 4. INFRA-002: Remove PinchTab port exposure
  - Removed `ports: - "9867:9867"` from PinchTab service
  - Service now only accessible via Docker internal network

- [x] 5. AGENT-001: Add prompt/data separation
  - Wrapped user context in `<user_data>` XML delimiters in harness.py
  - Added system instruction warning LLM not to follow instructions in user data

- [x] 6. AGENT-002: Validate reflection JSON with Pydantic
  - Added `LearningEntry` Pydantic model validation in reflect()
  - Invalid entries are discarded with warning log

- [x] 7. FE-001: Update Nginx CSP
  - Removed stale `clerk.com` and `api.clerk.com` from CSP
  - Added `*.supabase.co` and `wss://*.supabase.co` for realtime

- [x] 8. FE-002: Add DOMPurify for LLM output
  - Created `frontend/src/lib/sanitize.ts` with `sanitizeLLMOutput()` and `escapeHtml()`
  - Added `dompurify@^3.1.6` and `@types/dompurify@^3.0.5` to package.json

- [x] 9. Rate limiting improvements
  - Changed rate limiter key_func from IP-only to per-user (JWT sub extraction)
  - Added `@limiter.limit("5/minute")` on POST /me/models endpoint

- [x] 10. Production endpoint protection
  - Set `redoc_url=None` and `openapi_url=None` when `APP_ENV=production`
