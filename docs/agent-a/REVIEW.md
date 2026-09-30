# Agent A review and release verdict

Reviewed 2026-10-01 in `D:/CareerCraft-agent-a`, branch `agent-a/resume`. Baseline `093ef54`. The requested `master...agent-a/resume` diff includes 139 files inherited from the baseline; Agent A changes are identified using `093ef54` and the scoped file list below. Main-worktree edits were preserved.

## Phase status

- Phase 1: plan artifact complete; vendor source access limitations explicitly recorded.
- Phase 2: scoped implementation and regression tests delivered. Earlier implementation gate passed local tests/lint/typecheck/build; review subsequently found shared gateway compliance and live-model gaps. These remain unresolved requirements, so full delivery is not complete.
- Phase 3: scoped defect review and authenticated API verification performed. Exit criteria are **not met**: successful live BYOK analysis, authenticated browser e2e, clean backend dependency audit, and rendered DOCX pagination remain unverified or blocked.

## Findings by severity

| Severity / status | File:line | Evidence | Fix / disposition | Verification |
|---|---|---|---|---|
| Critical / fixed | frontend/package-lock.json:6804 | npm audit reported Next.js ImageResponse RCE GHSA-vcvr-r3jv-pc5j on 16.3.4 | Compatible lock update to 16.3.8 | Production build, typecheck, lint and npm audit zero vulnerabilities |
| High / open shared dependency | backend/app/core/llm_gateway.py:58; backend/app/agents/resume_agent.py:206 | Gateway lacks DeepSeek/Ollama and forwards OpenAI payloads to native Anthropic/Google APIs. Local active provider is DeepSeek; resume node still uses baseline model_router | Requests to B in PLAN; shared provider adapters and sync gateway entry point required | Static trace; no successful live model call claimed |
| High / open inherited dependencies | backend/constraints.txt:1; docs/agent-a/container-pip-audit.json | Fresh container audit: 25 advisory records across 10 packages, including duplicate aliases. Local venv: 47 across 15 | Requests to B for compatible LangChain/LangGraph/browser dependency upgrade | pip-audit artifacts; no clean audit claimed |
| High / fixed | backend/app/api/v1/resume.py:466 | Old full-text writes could overwrite current content and no-JD edits retained old scores | Content identity, locked expected-version check, deterministic general/job recompute; first-party clients pass version | Regression tests; authenticated concurrent writes yield 200/409; save/reload score changes |
| High / fixed | frontend/src/app/(app)/resume/page.tsx:777 | Edited document score could fall back to primary upload or stale/manual result | One version/target query owner; reject mismatched response, discard errored data, show scoring/error state | Frontend regressions and typecheck/build; browser e2e not passed |
| Medium / fixed | backend/app/api/v1/resume.py:654 | Live `pages=1` was rejected because integer Literal did not coerce query string | Bounded integer Query 1..2 | Endpoint test accepts 1/2 and rejects 0/3/non-number; authenticated PDF/DOCX downloads |
| Medium / fixed | frontend/src/components/linkedin/ProfilePdfUpload.tsx:23 | API client default JSON header prevented correct FormData submission | Explicit multipart header using existing upload pattern | Lint/typecheck/build; browser multipart proof remains unverified |
| Medium / fixed | backend/app/services/linkedin_profile.py:66 | Experience continuation on subsequent PDF pages was discarded | Preserve section independently per column across pages | Failing reproduction now passes; education boundary remains excluded |
| Medium / fixed | backend/app/api/v1/linkedin.py:88; backend/app/api/v1/resume.py:199 | Grounding failure could lose token usage; unexpected resume failure could leave running row | Existing token/redaction callbacks, terminal run logging, safe errors and input metadata | Failure regression tests assert tokens/status/duration and no private error echo |
| Medium / fixed | backend/app/api/v1/resume.py:675 | Rerendering an approval-pinned document could change approved bytes | Serve stored pinned PDF bytes | Exact-byte regression test; approval/send/submit gates untouched |
| Medium / fixed | backend/app/agents/resume_agent.py:65 | General generation could retain model self-grade and persist through a JD-only scorer | Pure estimate for persistence and general generation | General score/persistence regressions |
| Low / fixed | frontend/package-lock.json:4524 | DOMPurify detached event-handler advisory plus initial brace-expansion advisory | Compatible audited lock updates | npm audit zero vulnerabilities |

## Verification

- Full backend unit/security suite: **1103 passed, 72 skipped, one inherited deprecation warning** (56.48 seconds). `backend-tests.txt` records the final run.
- Scoped Ruff and Black (repository 100-character setting) pass. No new migrations or tables; rollback is reverting the code. Existing local user_documents/agent_runs have RLS enabled and owner policies. API runs as table owner, so endpoint owner filters are the enforcing boundary; verified with a second real Clerk user.
- Frontend lint, typecheck, six node regression tests, and production build pass on Next.js 16.3.8; all 41 routes build. npm audit is clean.
- Bandit reports inherited LOW findings outside changed behavior; no new high/medium finding. Backend pip-audit remains non-clean, separately measured for local venv and fresh container.
- Nine authenticated API check groups pass against `deploy/local`: real Clerk session; edit/save/reload; simultaneous edit conflict; failed overflow preservation; deterministic general/per-job scores; three templates ? two page targets ? PDF/DOCX text round trips; malformed/type/size/image-only LinkedIn rejection; missing-model safe error; cross-owner read/edit/score/download denial. See `live-results.json` and `live_review.py`.
- Unit round trips additionally assert section order, headings/contact/dates/skills/bullets, minimum PDF font 10pt, no PDF images, and no DOCX tables/drawings/text boxes. Irreducible content returns guidance instead of dropping facts.
- LinkedIn unit tests cover encrypted/excess-page/malformed/scanned PDFs, section mapping, injection passed as untrusted data, quote/number grounding and failed run usage. Successful real-model suggestions have not been verified.
- Browser e2e was attempted with disposable Clerk tickets: navigation destroyed activation context; later session readiness timed out, and some attempts encountered Clerk API connection timeouts. **Not passed.** API auth proof is independent and passed. `browser-results.json` records this limitation; `live_browser.py` is a rerunnable proof.
- No schema migration introduced: new migration RLS/apply/down checks are not applicable. Existing schema was inspected without resetting user data.

## Remaining risks and release conditions

**NO-GO for release.** Resolve the shared gateway provider adapters and route resume generation through llm_gateway; upgrade inherited vulnerable backend packages; run successful real BYOK LinkedIn analysis and authenticated browser e2e. Agent A scoped fixes are reviewable, but the requested complete gates must not be represented as passed.

DOCX preserves text and fitted style but Word may paginate differently; no Word/LibreOffice renderer was available. The deterministic semantic match is a bounded alias approximation, not embedding similarity or a vendor algorithm. Source quotes/numeric guards constrain LinkedIn output but do not prove every rewritten claim semantically entailed; user review remains required. Legacy callers may omit expected_version; all first-party writers supply it. GitHub endpoint item shapes remain B-owned and unverified; optional 404 is silently skipped. Workday/Lever/Taleo/SmartRecruiters source gaps are explicit in PLAN; no universal ATS score claim is made.

Local runtime used the branch Docker overlay and then copied reviewed backend source into its container for live fixes. Rebuild images from final commits before deployment; no production deploy, email send or application submit occurred. Disposable Clerk accounts and synthetic local rows were used; credentials remain in OS temp and are never included in artifacts.

## Changed files

The following includes Agent A implementation and hardening, excluding inherited baseline changes:

- `backend/app/agents/resume_agent.py`
- `backend/app/api/v1/linkedin.py`
- `backend/app/api/v1/resume.py`
- `backend/app/services/ats_estimator.py`
- `backend/app/services/ats_service.py`
- `backend/app/services/linkedin_profile.py`
- `backend/app/services/pdf_service.py`
- `backend/app/services/resume_export.py`
- `backend/app/services/resume_version.py`
- `backend/tests/unit/test_ats_estimator.py`
- `backend/tests/unit/test_ats_service.py`
- `backend/tests/unit/test_linkedin_profile.py`
- `backend/tests/unit/test_resume_agent.py`
- `backend/tests/unit/test_resume_download.py`
- `backend/tests/unit/test_resume_export.py`
- `backend/tests/unit/test_resume_fix_api.py`
- `docs/agent-a/PLAN.md`
- `docs/agent-a/REVIEW.md`
- `docs/agent-a/backend-tests.txt`
- `docs/agent-a/bandit.json`
- `docs/agent-a/browser-results.json`
- `docs/agent-a/container-pip-audit.json`
- `docs/agent-a/container-requirements.txt`
- `docs/agent-a/live-results.json`
- `docs/agent-a/live_browser.py`
- `docs/agent-a/live_review.py`
- `docs/agent-a/local.override.yml`
- `docs/agent-a/npm-audit.json`
- `docs/agent-a/pip-audit.json`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/app/(app)/linkedin/page.tsx`
- `frontend/src/app/(app)/resume/page.tsx`
- `frontend/src/components/linkedin/ProfilePdfUpload.tsx`
- `frontend/src/components/resume/GithubProjects.tsx`
- `frontend/src/components/resume/ResumeFixPanel.tsx`
- `frontend/src/components/resume/ScoreExplanation.tsx`
- `frontend/src/lib/profile-contracts.test.mjs`
- `frontend/src/lib/profile-contracts.ts`
- `frontend/src/lib/resume-api.ts`
- `frontend/src/lib/resume-insights.test.mjs`
- `frontend/src/lib/resume-insights.ts`
- `frontend/src/lib/resume-state.test.mjs`
- `frontend/src/lib/resume-state.ts`
- `frontend/src/lib/resume-types.ts`
