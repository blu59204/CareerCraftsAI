# Database Schema

CareerCraft AI uses Supabase (PostgreSQL 16 + pgvector 0.7+). All user data tables live in the `public` schema with Row-Level Security enforced at the database layer.

---

## Tables

### `public.users`

User profiles. Created automatically by a Postgres trigger `on_auth_user_created` when a user signs up via Supabase Auth.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Internal user ID |
| `supabase_uid` | `uuid` | NOT NULL, UNIQUE, FK → `auth.users.id` | Links to Supabase Auth |
| `email` | `text` | NOT NULL | Email (mirrors Auth) |
| `full_name` | `text` | | Display name |
| `avatar_url` | `text` | | Profile picture URL |
| `headline` | `text` | | Professional headline |
| `location` | `text` | | Current location |
| `target_role` | `text` | | Job search target role |
| `target_salary` | `integer` | | Target compensation (USD) |
| `created_at` | `timestamptz` | default `now()` | Account creation |
| `updated_at` | `timestamptz` | | Last profile update |

**RLS:** `USING (supabase_uid = auth.uid())`

---

### `public.user_model_settings`

BYOK AI provider configuration. API keys stored AES-256-GCM encrypted.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Settings row ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `provider` | `text` | NOT NULL | anthropic, openai, google, ollama, nvidia |
| `model_name` | `text` | NOT NULL | Model name (e.g. claude-sonnet-4-6) |
| `api_key_enc` | `text` | | AES-256-GCM encrypted API key |
| `is_active` | `boolean` | default false | Currently selected provider |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

**Note:** The PBKDF2 salt and AES-GCM nonce are embedded in the `api_key_enc` ciphertext itself (first 16 bytes = salt, next 12 = nonce, remainder = ciphertext). No separate `api_key_salt` column exists. The key is decrypted only at runtime in `model_router.py` and `security.py` — never stored in plaintext.

---

### `public.user_preferences`

UI and feature preferences per user.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `user_id` | `uuid` | PK, FK → `users.id` | Owner |
| `theme` | `text` | default 'dark' | dark, light, system |
| `notifications_email` | `boolean` | default true | Email notification opt-in |
| `auto_followup` | `boolean` | default true | Auto-schedule follow-ups |
| `default_tone` | `text` | default 'professional' | Default email/cover letter tone |
| `linkedin_auto_mode` | `boolean` | default false | Automated LinkedIn outreach |
| `updated_at` | `timestamptz` | | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.documents`

User-uploaded documents (resumes, achievements, etc.) and their Supabase Storage references.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Document ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `persona_id` | `uuid` | FK → `resume_personas.id`, nullable | Associated persona |
| `filename` | `text` | NOT NULL | Original filename |
| `doc_type` | `text` | NOT NULL | resume, achievements, certifications, portfolio, notes |
| `s3_url` | `text` | | Supabase Storage URL |
| `mime_type` | `text` | | application/pdf, etc. |
| `file_size_bytes` | `integer` | | File size |
| `chunks_count` | `integer` | | Number of pgvector chunks ingested |
| `rag_collection` | `text` | | pgvector collection name |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.resume_personas`

Multiple resume versions for targeting different roles.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Persona ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `name` | `text` | NOT NULL | e.g. "Backend Engineer" |
| `description` | `text` | | Notes on this persona's focus |
| `is_default` | `boolean` | default false | Used when no persona specified |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.applications`

Job application pipeline (kanban state machine).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Application ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `job_title` | `text` | NOT NULL | Role name |
| `company` | `text` | NOT NULL | Company name |
| `job_url` | `text` | | Original job posting URL |
| `platform` | `text` | | linkedin, indeed, naukri, manual |
| `status` | `text` | NOT NULL | saved, applied, interviewing, offer, rejected, withdrawn |
| `applied_at` | `timestamptz` | | When application was submitted |
| `last_activity_at` | `timestamptz` | | Last status change |
| `next_followup_at` | `timestamptz` | | Scheduled follow-up time |
| `resume_document_id` | `uuid` | FK → `documents.id` | Which resume was submitted |
| `cover_letter_id` | `uuid` | FK → `cover_letter_versions.id` | Which cover letter |
| `notes` | `text` | | Free-form notes |
| `created_at` | `timestamptz` | default `now()` | |

**Status transitions:** `saved` → `applied` → `interviewing` → `offer` or `rejected`. `withdrawn` from any state.

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.agent_runs`

Audit log of every agent execution.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Run ID |
| `user_id` | `uuid` | FK → `users.id` | Who triggered the run |
| `task` | `text` | NOT NULL | Task name (e.g. optimize_resume) |
| `status` | `text` | NOT NULL | queued, running, complete, error, cancelled |
| `input` | `jsonb` | | Task input parameters |
| `output` | `jsonb` | | Task result |
| `error_message` | `text` | | Error detail if status=error |
| `tokens_used` | `integer` | default 0 | LLM tokens consumed |
| `duration_ms` | `integer` | | Wall-clock execution time |
| `model_provider` | `text` | | Which provider was used |
| `model_name` | `text` | | Which model was used |
| `created_at` | `timestamptz` | default `now()` | |
| `completed_at` | `timestamptz` | | When run finished |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

**Index:** `(user_id, created_at DESC)` for dashboard history queries.

---

### `public.cover_letter_versions`

Versioned cover letters generated by the CoverLetterAgent.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Version ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `application_id` | `uuid` | FK → `applications.id`, nullable | Linked application |
| `job_title` | `text` | | Role targeted |
| `company` | `text` | | Company targeted |
| `tone` | `text` | | professional, concise, enthusiastic |
| `content` | `text` | NOT NULL | Full cover letter text |
| `word_count` | `integer` | | |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.interview_sessions`

Mock interview session records.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Session ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `job_title` | `text` | | Role practiced |
| `company` | `text` | | Company (for company-specific questions) |
| `interview_type` | `text` | | technical, behavioral, system_design, mixed |
| `questions_asked` | `integer` | | Total questions in session |
| `avg_clarity_score` | `numeric(3,1)` | | Average clarity score (0–10) |
| `avg_relevance_score` | `numeric(3,1)` | | Average relevance score (0–10) |
| `avg_depth_score` | `numeric(3,1)` | | Average depth score (0–10) |
| `transcript` | `jsonb` | | Full Q&A transcript |
| `feedback_summary` | `text` | | AI-generated session summary |
| `completed_at` | `timestamptz` | | |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.salary_reports`

Salary benchmarking results.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Report ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `role` | `text` | NOT NULL | Role benchmarked |
| `location` | `text` | NOT NULL | Market location |
| `experience_years` | `integer` | | |
| `p25` | `integer` | | 25th percentile salary |
| `p50` | `integer` | | Median salary |
| `p75` | `integer` | | 75th percentile |
| `p90` | `integer` | | 90th percentile |
| `total_comp_base` | `integer` | | Base salary (p50) |
| `total_comp_equity` | `integer` | | Annual equity value |
| `total_comp_bonus` | `integer` | | Annual bonus |
| `negotiation_script` | `text` | | Generated negotiation script |
| `sources` | `jsonb` | | Data sources used |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.company_intel`

Cached company research results.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Intel record ID |
| `company_name` | `text` | NOT NULL | Normalized company name |
| `culture` | `text` | | Culture summary |
| `glassdoor_rating` | `numeric(2,1)` | | Glassdoor rating |
| `glassdoor_reviews_count` | `integer` | | |
| `interview_process` | `text` | | Interview process description |
| `recent_news` | `jsonb` | | Array of news items |
| `funding_summary` | `text` | | Funding history summary |
| `headcount` | `text` | | Employee count range |
| `key_people` | `jsonb` | | Array of {name, role, linkedin} |
| `sources` | `jsonb` | | URLs used for research |
| `cached_at` | `timestamptz` | | When researched |
| `expires_at` | `timestamptz` | | Cache expiry (7 days) |

**No RLS** — company intel is shared/public data, not user-specific.

**Index:** `(company_name, expires_at)` for cache lookups.

---

### `public.leads`

Recruiter contact leads.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Lead ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `name` | `text` | NOT NULL | Recruiter name |
| `title` | `text` | | Job title |
| `company` | `text` | | Company |
| `email` | `text` | | Email (from Hunter.io or manual) |
| `linkedin_url` | `text` | | LinkedIn profile URL |
| `status` | `text` | default 'new' | new, contacted, responded, converted, closed |
| `source` | `text` | | hunter_io, proxycurl, manual |
| `notes` | `text` | | |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.linkedin_outreach_queue`

Outreach messages queued for user approval and sending.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Outreach item ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `lead_id` | `uuid` | FK → `leads.id` | Target lead |
| `message_type` | `text` | | connection_request, inmail, followup |
| `message` | `text` | NOT NULL | Drafted message |
| `status` | `text` | default 'pending' | pending, approved, sent, failed, cancelled |
| `scheduled_at` | `timestamptz` | | When to send (if scheduled) |
| `sent_at` | `timestamptz` | | When actually sent |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

### `public.ats_scores`

ATS analysis results for generated resumes.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Score record ID |
| `user_id` | `uuid` | FK → `users.id` | Owner |
| `document_id` | `uuid` | FK → `documents.id` | Analyzed document |
| `job_title` | `text` | | Target job title |
| `score` | `integer` | | Overall ATS score (0–100) |
| `keyword_score` | `integer` | | Keyword match score |
| `section_score` | `integer` | | Section completeness score |
| `format_score` | `integer` | | Formatting compliance score |
| `missing_keywords` | `text[]` | | Keywords in JD but not resume |
| `matched_keywords` | `text[]` | | Keywords found in both |
| `suggestions` | `jsonb` | | Array of improvement suggestions |
| `created_at` | `timestamptz` | default `now()` | |

**RLS:** `USING (user_id = (SELECT id FROM users WHERE supabase_uid = auth.uid()))`

---

## pgvector Collections

Vector embeddings are stored in `langchain_pg_embedding` (managed by `langchain-postgres`).

| Collection name pattern | Used for |
|---|---|
| `{user_id}_resume` | Resume chunks |
| `{user_id}_achievements` | Achievement bullets |
| `{user_id}_certifications` | Certifications |
| `{user_id}_portfolio` | Portfolio/project descriptions |
| `{user_id}_notes` | User-added notes |

**Chunk config:** size=500 tokens, overlap=50 tokens

**Index:**
```sql
CREATE INDEX ON langchain_pg_embedding
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

---

## Row-Level Security Summary

| Table | RLS Predicate |
|---|---|
| `users` | `supabase_uid = auth.uid()` |
| `user_model_settings` | Via `users.supabase_uid = auth.uid()` join |
| `user_preferences` | Via `users.supabase_uid = auth.uid()` join |
| `documents` | Via `users.supabase_uid = auth.uid()` join |
| `resume_personas` | Via `users.supabase_uid = auth.uid()` join |
| `applications` | Via `users.supabase_uid = auth.uid()` join |
| `agent_runs` | Via `users.supabase_uid = auth.uid()` join |
| `cover_letter_versions` | Via `users.supabase_uid = auth.uid()` join |
| `interview_sessions` | Via `users.supabase_uid = auth.uid()` join |
| `salary_reports` | Via `users.supabase_uid = auth.uid()` join |
| `leads` | Via `users.supabase_uid = auth.uid()` join |
| `linkedin_outreach_queue` | Via `users.supabase_uid = auth.uid()` join |
| `ats_scores` | Via `users.supabase_uid = auth.uid()` join |
| `company_intel` | No RLS (shared data) |

---

## Migration History

| # | File | What it adds |
|---|---|---|
| 0001 | `create_users.sql` | `public.users`, trigger `on_auth_user_created` |
| 0002 | `create_model_settings.sql` | `user_model_settings` |
| 0003 | `create_documents.sql` | `documents`, Supabase Storage bucket |
| 0004 | `create_applications.sql` | `applications` + status enum |
| 0005 | `create_leads.sql` | `leads` |
| 0006 | `create_agent_runs.sql` | `agent_runs` |
| 0007 | `create_pgvector_indexes.sql` | pgvector extension, HNSW index |
| 0008 | `enable_rls.sql` | RLS policies on all user tables |
| 0009 | `clerk_to_supabase_migration.sql` | Auth provider migration backfill |
| 0010 | `create_user_preferences.sql` | `user_preferences` |
| 0011 | `create_cover_letters.sql` | `cover_letter_versions` |
| 0012 | `create_interview_sessions.sql` | `interview_sessions` |
| 0013 | `create_salary_reports.sql` | `salary_reports` |
| 0014 | `create_company_intel.sql` | `company_intel` |
| 0015 | `create_resume_personas.sql` | `resume_personas`, FK on `documents` |
| 0016 | `create_linkedin_outreach.sql` | `linkedin_outreach_queue` |
| 0017 | `create_ats_scores.sql` | `ats_scores` |
| 0018 | `fix_rls_supabase_uid.sql` | RLS predicate fix for supabase_uid column |
| 0019 | `linkedin_credentials.sql` | LinkedIn OAuth credentials + auto_mode flag |

---

## Running Migrations

```bash
# Apply all pending migrations
supabase db push --db-url "$DATABASE_URL"

# Reset (WARNING: drops all data)
supabase db reset --db-url "$DATABASE_URL"

# Check migration status
supabase migration list
```
