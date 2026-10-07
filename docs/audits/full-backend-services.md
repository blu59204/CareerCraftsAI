# Full backend agents, services and tools audit

Audit baseline: commit `3a27b1c`. Coverage is recorded with file hashes and line counts in `coverage-backend-services.csv`. Source was read in full before marking a file complete. No production calls or source changes were made by this reviewer.

## Confirmed findings

### P1 — Generic agent execution can read and overwrite another user's interview

`backend/app/agents/interview_coach_agent.py:355` passes the caller-controlled context session ID to `_get_interview_session`. Both the read at line 553 and write at line 586 filter only by session ID, without comparing the authenticated state's user ID. The generic `/agents/run` route accepts `evaluate_answer` and `interview_coach`, and its admission path does not validate interview ownership. Consequently, knowing another session UUID permits sending its question/context to the attacker's configured model provider and storing attacker-generated answers/scores in the victim's session. Ownership scoping in the dedicated interview endpoint does not protect this alternative path.

A local mocked node probe with different attacker/victim IDs returned `foreign_owner_different True result_status completed`, `foreign_question_sent_to_llm True foreign_session_written True`. It made no external calls and wrote no database rows. Require user ID in both session helper queries and reject foreign sessions before any LLM invocation.

### P2 — Interview scoring prompt and validated output disagree

`backend/app/agents/interview_coach_agent.py:80` instructs the provider to return `score` and `tips`, whereas `InterviewEvaluationOutput` at line 55 defines `clarity`, `relevance`, `depth`, `feedback` and `rating`, with zero/empty defaults. Pydantic discards the requested fields. The scoring path at lines 402–413 then computes zero from the default dimensions and loses the tips. A provider obeying the prompt therefore receives a zero score regardless of answer quality.

Local validation of `{'score':95,'tips':['Good answer']}` produced `{'clarity':0,'relevance':0,'depth':0,'feedback':'','rating':''}`. Align prompt, schema and score scale; require meaningful validated fields rather than silently defaulting a malformed evaluation.

### P2 — Generated company intelligence is incompatible with its retrieval contract

`backend/app/agents/company_research_agent.py:520` stores company chunks with company/source/chunk metadata, without `user_id` or `document_id`, and creates no corresponding live `UserDocument`. `backend/app/services/rag_service.py:239` requires both matching owner metadata and a live company document. The interview coach retrieves company context through that path, so generated company intelligence cannot be returned. Company retrieval has no raw-document fallback. Persist company intel through a storage contract compatible with scoped retrieval, or implement a separately scoped company-intel retrieval path. The synchronous `store.add_documents` call at line 531 also runs directly inside an async function and can block the shared worker event loop during provider/database work.

### P2 — Concurrent inbox scans can regress application status

`backend/app/services/application_status_service.py:107` loads eligible application rows without locking them, then computes status transitions using the previously loaded state and performs an unconditional ORM write. Distinct Gmail messages do not share the message-level uniqueness lock. Two scans can both read `applied`; one commits `rejected`, while another later commits `interview`, overwriting the terminal result. The same race permits `interview` to regress to `viewed`. Lock the application row before evaluating each transition, or use a conditional compare-and-update and retry against current state. This finding is source-traced; no live concurrent database probe was performed.

### P2 — Active JobSpy adapter fixes Indeed country to India

`backend/app/services/job_search_service.py:106` invokes `scrape_jobs` without its country argument. `backend/app/services/job_platforms_service.py:114` defaults that argument to India, which line 140 passes to `country_indeed`. The location-derived country helper is used only by the legacy aggregate caller. Thus active searches for US/UK locations target India's Indeed site, reducing or losing relevant results. Derive country in the active adapter as well.

## Findings coordinated with the API/workflow reviewer

### P2 — Cover-letter profile fallback is fetched then discarded

`backend/app/agents/cover_letter_agent.py:147` joins retrieved chunks into `context_text`, and lines 148–152 fetch the member's profile when retrieval is empty or fails. However, the actual `build_cover_prompt` call at line 173 receives `chunk_texts or None`; the fallback `context_text` never enters the prompt. During RAG outages or for users without indexed chunks, the letter is generated without the available candidate background, reducing personalization and factual grounding. Pass the resolved fallback as prompt context and verify the empty-RAG case with a sentinel profile value.

The tailored resume producer persists `doc_type='resume_tailored'`, while auto-apply submission and the extension narrative generator require `resume`. The auto-apply queue selects its newly generated tailored PDF and passes it to that incompatible loader. The parent reviewer owns this cross-module finding and its API evidence.

Direct legacy agent endpoints lack shared admission/durable run coverage; the parent reviewer owns their route evidence. LinkedIn outreach's approval path calls the retired browser service, which always raises; no successful browser send or duplicate-send vulnerability was asserted. Resume-file replacement during account erasure belongs to the parent review; new document creation was excluded because FK locks and upload compensation may protect that path.

## Architecture and scope limits

`backend/memory/routes.py` is unmounted legacy code. Its per-request manager lifetime is a maintenance issue, not an exposed production connection leak. Browser automation helpers include retired paths; current submission uses the extension flow. Company intelligence persistence/retrieval and interview evaluation show contract drift between producers and consumers. No speculative SQL injection or SSRF was reported without a reachable caller bypassing validation.

Tracked source is the coverage denominator. Dependencies, generated outputs, secrets, ignored local files and external services were not line-reviewed. A complete source reading does not establish absence of vulnerabilities; provider behavior and actual database concurrency require integration validation. Unit test source coverage is recorded separately as it is completed.

Completed coverage: all 115 assigned agent/service/tool/standalone-memory tracked files, plus 44 unit test files and the empty unit helper module in `coverage-backend-services-tests.csv`. Standalone memory tests are included in the first manifest. Unit files delegated back to the root reviewer: account deletion service, agents API, agent-run lifecycle, applications, auto-apply pipeline, and all four extension tests. Unit f–m files belong to the infrastructure reviewer; unit n–z files belong to the frontend reviewer. These are ownership boundaries, not global exclusions.

Test review observations: the ATS adapters rely on hand-crafted browser fixtures rather than verified provider contracts. Interview tests do not exercise the generic agent entry point with a foreign session, and cover-letter tests mock nonempty RAG context, leaving the fallback defect uncovered. `test_enhancement_pbt.py:56` implements suggestions inside the test rather than exercising production behavior; its keyword property at line 128 uses a `pass` loop and only verifies strings. `test_browser_use_naukri.py` is entirely integration-gated yet still references removed browser helpers, so its skipped state cannot establish the current submission path's safety. These gaps limit what the passing test count demonstrates.
