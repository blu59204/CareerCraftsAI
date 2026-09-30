# Agent A final review

Reviewed 2026-10-01 in `D:/CareerCraft-agent-a`, branch `agent-a/resume`. Read `master...agent-a/resume`; distinguish inherited changes using Agent A's starting commit `093ef54`. Main and B worktree edits were preserved. Shared gateway/dependency fixes were explicitly authorized by the user and coordinated in PLAN.md.

## Phase boundaries

| Phase | Status | Exit evidence |
|---|---|---|
| 1 ? Plan | Complete | Four workstreams, vendor citations, Mermaid, contracts, file map, migrations decision, phased tasks, risks and defaults. Current Workday grading, Lever fit ranking and Taleo prescreening sources verified; unavailable support/detail pages identified honestly. |
| 2 ? Implement | Complete | Persistence/versioning, pure deterministic estimator, safe PDF/DOCX fitting, LinkedIn PDF analysis and optional GitHub consumer delivered. Regression tests, lint, typecheck and build pass. |
| 3 ? Review/harden | Complete | Review fixes committed; Windows/Linux suites, authenticated API/browser checks, real model runs, rendered DOCX checks, audits and worker startup verified. |

## Findings by severity

| Severity / status | File:line | Evidence | Fix | Verification |
|---|---|---|---|---|
| Critical / fixed | frontend/package-lock.json:6804 | Original Next.js ImageResponse RCE advisory | Update to Next.js 16.3.8 | Build/typecheck/lint; npm audit zero |
| High / fixed | backend/app/core/llm_gateway.py:123 | Native Anthropic/Google received OpenAI payloads; configured providers absent | Reuse native model_router adapters behind encrypted-key/session boundary; normalize text/usage | Provider transport tests; real configured Ollama calls |
| High / fixed | backend/app/main.py:143 | Live gateway call returned Clerk 401 before gateway auth | Gateway uses its Redis sessions; other API auth remains Clerk | Failing reproduction; eleven transport cases; live model runs |
| High / fixed | backend/constraints.txt:5 | Original fresh container had vulnerable LangChain/LangGraph; JobSpy required vulnerable Markdownify | Audited provider pins; unused python-jose removed; explicit runtime dependencies before tools with obsolete pins | Full Windows/Linux suites; imports/conversion; worker startup; fresh pip-audit zero |
| High / fixed | backend/app/api/v1/resume.py:466 | Writes could overwrite newer edits and retain stale scores | Locked expected-version check, content hash, deterministic general/job recompute | Save/reload score change; concurrent 200/409; overflow preserves prior version |
| High / fixed | frontend/src/app/(app)/resume/page.tsx:777 | Display could use score for another document/version/target | Single query owner; reject stale responses; scoring/error states | Node regressions; browser stale-response injection displays Score unavailable |
| Medium / fixed | backend/app/services/resume_export.py:72 | A one-page PDF rendered as two-page DOCX | Exact point spacing, frame padding, contact/bullet spacing and shared heading rules | Regression and 30-case LibreOffice matrix |
| Medium / fixed | backend/app/api/v1/resume.py:654 | Live query pages=1 failed integer Literal validation | Bounded integer Query | Endpoint tests; authenticated 1/2-page downloads |
| Medium / fixed | frontend/src/components/linkedin/ProfilePdfUpload.tsx:23 | Default JSON header blocked multipart | Existing upload pattern | Real browser boundary inspection and safe parse error |
| Medium / fixed | backend/app/services/linkedin_profile.py:66 | Continuation-page experience lost | Retain section independently per column | Failing reproduction/regression; education excluded |
| Medium / fixed | backend/app/services/linkedin_profile.py:112 | Valid short skills SQL/C++ could not be quoted | Short quotes accepted only as complete source lines | Short-fact regression; arbitrary fragments rejected |
| Medium / fixed | backend/app/services/linkedin_profile.py:136 | Weak models returned schemas or unsupported edits | Explicit instance shape; one bounded repair; same-section literal/numeric guards on both attempts | Repair/usage regressions; real grounded four-section result; unsafe outputs still fail safely |
| Medium / fixed | backend/app/agents/_llm_json.py:40 | Validation warning could echo model output | Structured schema/error-type warning | Regression proves private output absent from log |
| Medium / fixed | backend/app/api/v1/linkedin.py:88 | Failure could lose usage/terminal run state | Token callbacks and final status/duration logging | Failure regressions; successful run timestamps and positive usage |
| Medium / fixed | backend/app/api/v1/resume.py:675 | Rerender could alter approval-pinned bytes | Serve stored approved PDF | Exact-byte regression; send/submit gates preserved |
| Medium / inherited, to B | backend/app/services/rag_service.py:200 | Live ingest cannot create generic HNSW on dimensionless embeddings | Requests to B item 6; no destructive schema conversion | Retrieval/generation succeed; dimension-aware indexing/query work needed for production scale |
| Low / fixed | frontend/package-lock.json:4524 | DOMPurify/brace-expansion advisories | Compatible lock updates | npm audit zero |

## Final validation

- **Windows backend:** 1,118 passed, 72 skipped. See backend-tests.txt.
- **Linux rebuilt backend:** 1,115 passed, 75 skipped. See container-tests.txt. Repository SQL/scripts/frontend fixtures were supplied for tests; product logic was not changed for fixture lookup. Environment-dependent optional skips are not counted as passes.
- **Frontend:** lint, typecheck, six regression tests and production build pass; 41 routes. See frontend-*.txt.
- **Security:** isolated local and rebuilt container pip-audit zero known vulnerabilities; npm audit zero. Bandit reports 22 inherited LOW findings outside changed behavior, no HIGH/MEDIUM. Tool metadata pins deliberately conflict with audited versions: imports, JobSpy HTML conversion, suites and worker startup validate the tested runtime; pip-check is not claimed clean.
- **Authenticated API:** nine groups pass against the user's deploy/local: persistence/score change, 200/409 concurrency, overflow rollback, deterministic general/job scoring, three templates ? two targets ? two formats, invalid uploads, safe missing-model response and cross-user read/edit/score/download 404. See live-results.json.
- **Authenticated browser:** rapid drafts preserve only final text; real save/reload shows current scoring; deliberately stale response rejected; forced failed save retains draft and leaves server unchanged; multipart LinkedIn error state verified. See browser-results.json. Fault injection is explicitly identified; successful persistence uses real Clerk/API calls.
- **Real model:** configured local Ollama, no paid key copied. LinkedIn produced four before/after sections with literal quotes; resume produced a stored PDF and stayed awaiting_approval. Persisted runs recorded 1,804/2,040 tokens, duration and terminal timestamps. See model-results.json. This is successful-run evidence, not a claim every model attempt succeeds.
- **Rendered output:** 30 LibreOffice template/page/content cases: 24 accepted and six explicit overflows. Accepted PDF/DOCX stay within target pages and retain section order, contact info, dates and every project. Unit round trips assert readable PDF fonts, no images, and no DOCX tables/drawings/text boxes. See render-results.json.
- **Runtime:** final branch images built; backend healthy; updated Temporal worker connects and starts. Local deployment only; no email sent or application submitted.
- **Database:** no new tables/schema migrations; identity lives in existing JSONB. New migration apply/down is not applicable; rollback uses prior commits/images. Existing owner RLS and endpoint filters inspected, with IDOR verified using a second Clerk account. Temporal owns workflow persistence; no LangGraph persisted checkpointer requires migration for the upgrade.

## Remaining risks and verdict

**GO for the reviewed resume/LinkedIn changes. All three Agent A phase exits are met.** This is not a blanket verdict on B's features or the entire platform.

Before production-scale rollout, the shared RAG owner must fix the inherited dimensionless HNSW index/query mismatch. B's GitHub endpoint remains unverified; optional 404 is silently handled and resume works without it. Tool upgrades override obsolete upstream pins, so retain compatibility checks. Word/font substitutions can paginate differently from the tested LibreOffice renderer. Deterministic semantic matching is a disclosed alias approximation, not a vendor algorithm. Literal quotes/numeric guards do not prove complete semantic entailment; users review suggestions. Legacy clients can omit expected_version; first-party writers send it. The old main-worktree venv was preserved: use rebuilt images or audited requirements when integrating.

No production deployment, merge, email or application action occurred. Disposable account/data cleanup is recorded in cleanup-results.json.

## Changed files

CHANGED_FILES.txt contains the full Agent A list, including evidence artifacts, derived from 093ef54 plus final changes. Product changes are limited to resume/LinkedIn and user-authorized shared gateway, dependencies, middleware and JSON log hardening. B files and main uncommitted edits were preserved.
