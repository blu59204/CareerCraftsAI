# Implementation Plan: JobAgent Platform Enhancements

## Overview

This plan implements 10 platform enhancements: 5 new LangGraph agents (Cover Letter, Interview Coach, Salary Intelligence, Company Research, NL Search) and 5 feature upgrades (Enhanced Kanban, Smart Follow-Up, ATS Analyzer, Multi-Resume Profiles, LinkedIn Outreach). Implementation proceeds bottom-up: database → services → agents → API routes → frontend components, with property tests wired in alongside each feature.

## Tasks

- [x] 1. Database migrations and ORM models
  - [x] 1.1 Create migration `0011_cover_letter_versions.sql`
    - Add `cover_letter_id` column to `job_applications`
    - Create `cover_letter_versions` table with FK constraints and index
    - _Requirements: 1.4, 1.5_

  - [x] 1.2 Create migration `0012_interview_sessions.sql`
    - Create `interview_sessions` table with JSONB columns for questions, answers, scores
    - Add index on `(user_id, created_at DESC)`
    - _Requirements: 2.6_

  - [x] 1.3 Create migration `0013_salary_reports.sql`
    - Create `salary_reports` table with percentile columns and `data_unavailable` flag
    - _Requirements: 3.5_

  - [x] 1.4 Create migration `0014_company_intel.sql`
    - Create `company_intel` table with UNIQUE constraint on `(user_id, company_name)`
    - _Requirements: 4.4_

  - [x] 1.5 Create migration `0015_resume_personas.sql`
    - Create `resume_personas` table with `target_keywords` text array
    - Create trigger `check_max_personas` enforcing max 10 per user
    - _Requirements: 9.1, 9.2, 9.7_

  - [x] 1.6 Create migration `0016_linkedin_outreach_queue.sql`
    - Create `linkedin_outreach_queue` table with status CHECK constraint
    - Add index on `(user_id, status)`
    - _Requirements: 10.5_

  - [x] 1.7 Create migration `0017_ats_scores.sql`
    - Create `ats_scores` table with composite, keyword, readability, format sub-scores
    - _Requirements: 8.6_

  - [x] 1.8 Add SQLAlchemy ORM models for all new tables
    - Add `CoverLetterVersion`, `InterviewSession`, `SalaryReport`, `CompanyIntelModel`, `ResumePersona`, `LinkedInOutreachQueue`, `AtsScore` to `app/models/`
    - Add Pydantic request/response schemas for each feature
    - _Requirements: 1.4, 2.6, 3.5, 4.4, 8.6, 9.7, 10.5_

- [x] 2. External service integrations
  - [x] 2.1 Implement `app/services/exa_service.py`
    - Create `ExaService` class with `search_salary(role, company, location)` method
    - Add `search_news(company)` and `search_tech_stack(company)` methods
    - Add API key configuration to `app/core/config.py`
    - _Requirements: 3.1, 4.1_

  - [x] 2.2 Implement `app/services/proxycurl_service.py`
    - Create `ProxycurlService` class with `find_contacts(company, role_context)` method
    - Return up to 10 contacts with name, title, LinkedIn URL
    - Add API key configuration to `app/core/config.py`
    - _Requirements: 10.1_

  - [x] 2.3 Enhance `app/services/ats_service.py`
    - Implement `compute_ats_score(resume_text, jd_text) -> AtsScoreResult`
    - Implement `compute_weighted_composite(keyword, readability, format_)` pure function
    - Add keyword extraction, Flesch-Kincaid readability, format compliance checks
    - Add `get_missing_keywords(resume_text, jd_text)` returning ordered keyword list
    - Add `generate_suggestions(score_result)` returning ≥3 suggestions when score < 60
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 2.4 Write property tests for ATS scoring (Properties 21, 22, 23, 24)
    - **Property 21: ATS composite score bounds and weighting** — verify score ∈ [0,100] and equals round(keyword×0.5 + readability×0.3 + format×0.2)
    - **Property 22: Missing keywords are set difference** — verify all returned keywords are in JD but absent from resume
    - **Property 23: Suggestions when score is low** — verify ≥3 suggestions when composite < 60
    - **Property 24: Input length validation** — verify HTTP 422 for text < 100 chars
    - **Validates: Requirements 8.1, 8.2, 8.4, 8.10**

- [x] 3. Checkpoint - Ensure migrations and services pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Cover Letter Agent
  - [x] 4.1 Implement `app/agents/cover_letter_agent.py`
    - Create `cover_letter_node(state: AgentState)` LangGraph node
    - Implement tone validation (formal/casual/bold), default to formal
    - Retrieve top 5 resume chunks via RAG_Agent
    - Store result in `user_documents` and `cover_letter_versions`
    - Log run to `agent_runs` with `agent_type='cover_letter'`
    - Route LLM calls through `model_router`
    - Return `awaiting_approval` status for HITL gate
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 1.8, 1.9_

  - [x] 4.2 Register Cover Letter Agent in harness and orchestrator
    - Add task_type routing in `app/agents/harness.py`
    - Wire into `app/agents/orchestrator.py` supervisor graph
    - _Requirements: 1.8_

  - [x] 4.3 Create `app/api/v1/cover_letter.py` route handler
    - `POST /api/v1/cover-letter/generate` — trigger cover letter generation
    - `GET /api/v1/cover-letter/{app_id}/history` — return version history descending
    - Validate primary resume exists (422 if not)
    - Register router in `app/main.py`
    - _Requirements: 1.5, 1.6, 1.10, 1.11_

  - [x] 4.4 Write property tests for Cover Letter (Properties 1, 2)
    - **Property 1: Tone validation is exhaustive** — verify only formal/casual/bold accepted, all others rejected
    - **Property 2: Cover letter version ordering** — verify versions returned in strictly descending `created_at` order
    - **Validates: Requirements 1.2, 1.5, 1.6**

- [x] 5. Interview Coach Agent
  - [x] 5.1 Implement `app/agents/interview_coach_agent.py`
    - Create `start_session_node(state)` — generate questions covering all 3 types (or filtered)
    - Create `evaluate_answer_node(state)` — score 0-100, rating label, tips
    - Implement `compute_rating_label(score)` and `compute_session_summary(scores)` pure functions
    - Validate answer minimum 10 words
    - Retrieve company intel if available for question generation
    - Log run to `agent_runs` with `agent_type='interview_coach'`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 2.8, 2.9, 2.11_

  - [x] 5.2 Register Interview Coach Agent in harness and orchestrator
    - Add task_type routing in `harness.py`
    - Wire into `orchestrator.py`
    - _Requirements: 2.9_

  - [x] 5.3 Create `app/api/v1/interview.py` route handler
    - `POST /api/v1/interview/session/start` — start new session
    - `POST /api/v1/interview/session/{id}/answer` — submit answer, get evaluation
    - `GET /api/v1/interview/session/{id}/summary` — session summary
    - Register router in `app/main.py`
    - _Requirements: 2.10_

  - [x] 5.4 Write property tests for Interview Coach (Properties 4, 5, 6, 7, 8)
    - **Property 4: Question type coverage** — verify all 3 types present when no filter
    - **Property 5: Question type filter exclusivity** — verify filtered sessions only contain specified type
    - **Property 6: Evaluation bounds and rating consistency** — score ∈ [0,100], rating matches range, tips non-empty
    - **Property 7: Session summary is arithmetic mean** — overall_score == round(mean(scores))
    - **Property 8: Short answer rejection** — answers < 10 words get 422
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.5, 2.11**

- [x] 6. Salary Intelligence Agent
  - [x] 6.1 Implement `app/agents/salary_agent.py`
    - Create `salary_report_node(state)` LangGraph node
    - Implement `classify_offer(offer, p25, p50, p75)` pure function
    - Query Exa service for salary data
    - Generate negotiation script with opening, counter-offer at p75, 2 justifications
    - Handle `data_unavailable` case (HTTP 206)
    - Log run to `agent_runs` with `agent_type='salary_intelligence'`
    - Return `awaiting_approval` for negotiation script HITL
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 3.10_

  - [x] 6.2 Create `app/api/v1/salary.py` route handler
    - `POST /api/v1/salary/report` — generate salary report
    - `GET /api/v1/salary/report/{id}` — retrieve report
    - Store report in `salary_reports` table
    - Register router in `app/main.py`
    - _Requirements: 3.5, 3.9_

  - [x] 6.3 Write property tests for Salary Agent (Properties 9, 10, 11)
    - **Property 9: Salary percentile ordering** — verify p25 ≤ p50 ≤ p75 and all positive
    - **Property 10: Offer classification correctness** — verify below_market/at_market/above_market boundaries
    - **Property 11: Negotiation script structure** — verify opening, counter == p75, ≥2 justifications
    - **Validates: Requirements 3.2, 3.3, 3.4**

- [x] 7. Company Research Agent
  - [x] 7.1 Implement `app/agents/company_research_agent.py`
    - Create `company_research_node(state)` LangGraph node
    - Fetch from 4 sources: website (Firecrawl), news (Exa), tech stack (Exa), Glassdoor (Exa)
    - Compile `CompanyIntel` dataclass with graceful degradation on source failures
    - Implement 7-day cache check (skip external calls if fresh)
    - Embed in `{user_id}_company` pgvector collection
    - Persist structured JSON in `company_intel` table
    - Log run to `agent_runs` with `agent_type='company_research'`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 4.8, 4.10_

  - [x] 7.2 Create `app/api/v1/company.py` route handler
    - `POST /api/v1/company/research` — trigger company research
    - `GET /api/v1/company/{name}/intel` — get cached intel
    - Register router in `app/main.py`
    - _Requirements: 4.9_

  - [x] 7.3 Write property tests for Company Research (Properties 12, 13, 14)
    - **Property 12: Company Intel structure completeness** — verify all required fields present unless partial_data
    - **Property 13: Graceful degradation** — verify partial output on source failures with exact failed sources listed
    - **Property 14: Cache freshness** — verify cached data returned without API calls when < 7 days old
    - **Validates: Requirements 4.2, 4.8, 4.10**

- [x] 8. Checkpoint - Ensure all agent tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. NL Search Agent
  - [x] 9.1 Implement `app/agents/nl_search_agent.py`
    - Create `nl_search_node(state)` LangGraph node
    - Implement `SearchParameters` dataclass and `extract_parameters(llm, query)` function
    - Implement `validate_search_params(params)` pure function
    - Return structured interpretation for user confirmation before execution
    - Reject queries without role title (HTTP 422)
    - Pass structured query to existing Job_Search_Agent via PinchTab
    - Log run to `agent_runs` with `agent_type='nl_job_search'`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 9.2 Extend `app/api/v1/jobs.py` with NL search endpoint
    - `POST /api/v1/jobs/search/natural` — accept NL query, return interpretation + results
    - _Requirements: 5.8, 5.9_

  - [x] 9.3 Write property tests for NL Search (Properties 15, 16)
    - **Property 15: Parameter extraction completeness** — verify all identifiable params appear in SearchParameters
    - **Property 16: Role title required** — verify 422 when no role title extractable
    - **Validates: Requirements 5.1, 5.2, 5.4, 5.5**

- [x] 10. Smart Follow-Up Enhancement
  - [x] 10.1 Enhance `app/agents/followup_agent.py` with Company Intel integration
    - Query RAG_Agent for `{user_id}_company` collection before composing email
    - Incorporate at least one company-specific detail when intel available
    - Retrieve original JD and tailored resume from `job_applications` and `user_documents`
    - Generate distinct emails for different applications to same company
    - Fallback to JD + resume context when no Company Intel exists
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 10.2 Write property tests for Follow-Up (Properties 19, 20)
    - **Property 19: Email incorporates company intel** — verify body contains detail from intel when available
    - **Property 20: Distinct emails per application** — verify different content for same-company different-role apps
    - **Validates: Requirements 7.2, 7.4**

- [x] 11. Resume Persona Manager
  - [x] 11.1 Implement persona service functions in `app/services/persona_service.py`
    - Implement `compute_keyword_overlap(persona_keywords, jd_keywords) -> float` pure function
    - Implement `select_best_persona(personas, jd_text) -> tuple[Persona, float]` pure function
    - Handle below-threshold notification (< 20% overlap)
    - _Requirements: 9.3, 9.4, 9.5_

  - [x] 11.2 Create `app/api/v1/resume.py` persona endpoints (extend existing)
    - `GET /api/v1/resume/personas` — list user's personas
    - `POST /api/v1/resume/personas` — create persona (enforce max 10)
    - `PUT /api/v1/resume/personas/{id}` — update persona
    - `DELETE /api/v1/resume/personas/{id}` — delete persona
    - _Requirements: 9.1, 9.2, 9.8_

  - [x] 11.3 Write property tests for Persona Manager (Properties 25, 26, 27, 28, 29)
    - **Property 25: CRUD round-trip** — create then read returns identical data
    - **Property 26: Persona count cap** — never > 10 active personas per user
    - **Property 27: Best-fit maximizes overlap** — selected persona has highest keyword score
    - **Property 28: Below-threshold notification** — notify when max overlap < 20%
    - **Property 29: Resume deletion cascades** — primary_resume_id becomes null on document deletion
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.9**

- [x] 12. LinkedIn Outreach
  - [x] 12.1 Implement `app/services/linkedin_outreach_service.py`
    - Implement `filter_contacts_by_title(contacts, filter_keywords)` pure function
    - Implement `validate_message_length(message, max_chars=300)` pure function
    - Implement message drafting with contact name, title, user experience, company intel
    - _Requirements: 10.2, 10.3, 10.4_

  - [x] 12.2 Extend `app/api/v1/linkedin.py` with outreach endpoints
    - `POST /api/v1/linkedin/outreach/identify` — find contacts via Proxycurl, filter, draft messages
    - `GET /api/v1/linkedin/outreach/queue` — view pending messages
    - `POST /api/v1/linkedin/outreach/{id}/approve` — approve/reject/edit message
    - Enforce HITL gate: no send without approval
    - Execute approved sends via PinchTab with ≥3s delay between actions
    - Log to `agent_runs` with `agent_type='linkedin_outreach'`
    - _Requirements: 10.1, 10.5, 10.6, 10.7, 10.8, 10.9, 10.11, 10.12_

  - [x] 12.3 Write property tests for LinkedIn Outreach (Properties 30, 31, 32, 33)
    - **Property 30: Contact title filtering** — only recruiter/talent/hiring/engineering/director titles pass
    - **Property 31: Message personalization and length** — contains name+title AND ≤ 300 chars
    - **Property 32: Queue status invariant** — enters as pending_approval, never sent without approved
    - **Property 33: Human-like send delay** — inter-send delay ≥ 3000ms
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5, 10.6, 10.12**

- [x] 13. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Enhanced Kanban Board frontend
  - [x] 14.1 Implement drag-and-drop Kanban with status columns
    - Create `KanbanBoard` component with DnD between status columns (saved, applied, viewed, interview, offer, rejected)
    - Update `job_applications.status` on drop via API within 500ms
    - Add confirmation indicator on card after status change
    - Support filtering by status, company name, date range (no page reload)
    - Persist column sort order in `user_preferences`
    - _Requirements: 6.1, 6.2, 6.8, 6.9, 6.10_

  - [x] 14.2 Implement Activity Timeline component
    - Create `ActivityTimeline` component showing chronological events per application
    - Display status changes, agent actions (from `agent_runs`), email events
    - Create backend endpoint to aggregate timeline events
    - _Requirements: 6.3_

  - [x] 14.3 Implement AI next-action suggestions on application cards
    - Show at least one AI-suggested action per card based on status and days_since_last_activity
    - Auto-suggest Interview Coach when moved to `interview` status
    - Auto-suggest Salary Agent when moved to `offer` status
    - Display linked email thread count with inline expansion
    - _Requirements: 6.4, 6.5, 6.6, 6.7_

  - [x] 14.4 Write property test for Activity Timeline (Property 17)
    - **Property 17: Chronological ordering** — events sorted by timestamp ascending
    - **Validates: Requirements 6.3**

- [x] 15. Cover Letter frontend
  - [x] 15.1 Create `/cover-letter` page with `CoverLetterGenerator` component
    - Tone selector (formal/casual/bold), job application picker
    - Show generated cover letter with HITL approval UI
    - Version history panel showing all versions with tone labels
    - _Requirements: 1.2, 1.5, 1.6, 1.9_

- [x] 16. Interview Coach frontend
  - [x] 16.1 Create `/interview` page with `InterviewCoach` component
    - Session start form: role, company, question type filter
    - Interactive Q&A chat interface with real-time scoring
    - Session summary display with overall score, strengths, improvements
    - _Requirements: 2.1, 2.3, 2.5, 2.10_

- [x] 17. Salary Intelligence frontend
  - [x] 17.1 Create `/salary` page with `SalaryReport` component
    - Input form: role, company, location, offer amount (optional)
    - Percentile visualization (p25/p50/p75 chart)
    - Offer classification badge (below/at/above market)
    - Negotiation script display with HITL approval
    - _Requirements: 3.2, 3.3, 3.4, 3.9, 3.10_

- [x] 18. Company Research frontend
  - [x] 18.1 Create `/company/{name}` page with `CompanyIntelView` component
    - Display overview, culture, news (≥3 items), tech stack, Glassdoor sentiment
    - Show partial_data warnings for failed sources
    - Force refresh button, last researched timestamp
    - _Requirements: 4.2, 4.8, 4.9, 4.10_

- [x] 19. ATS Score frontend
  - [x] 19.1 Enhance `/resume/optimize` with `ATSScorePanel` component
    - Display overall score + 3 sub-score breakdown
    - Missing keywords list ordered by importance
    - Actionable suggestions (≥3 when score < 60)
    - Readability metrics (Flesch-Kincaid, sentence length)
    - Format compliance checklist (contact info, no tables, standard headings)
    - Allow triggering from both `/resume/optimize` and `/jobs/[id]`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.7, 8.8, 8.9_

- [x] 20. Resume Personas frontend
  - [x] 20.1 Enhance `/resume/versions` with `PersonaManager` component
    - List all personas with name, description, resume filename, keywords
    - Create/edit/delete persona forms (max 10 enforcement UI)
    - Best-fit persona selection display with match score during job application
    - Below-threshold (< 20%) warning notification
    - _Requirements: 9.1, 9.4, 9.5, 9.10_

- [x] 21. LinkedIn Outreach frontend
  - [x] 21.1 Create `/linkedin/outreach` page with `OutreachQueue` component
    - Company input with "Find Contacts" trigger button
    - Contact list display (name, title, LinkedIn URL)
    - Draft message cards with per-message approve/reject/edit actions
    - Queue status view (pending_approval, approved, sent)
    - _Requirements: 10.1, 10.3, 10.5, 10.6, 10.8, 10.9_

- [x] 22. NL Search frontend
  - [x] 22.1 Enhance `/jobs` page with natural language search input
    - Text input accepting plain language job queries
    - Structured interpretation display for user confirmation
    - Show extracted parameters alongside search results
    - _Requirements: 5.3, 5.8, 5.9_

- [x] 23. HITL Gate property test
  - [x] 23.1 Write property test for HITL gate (Property 3)
    - **Property 3: HITL gate state transition** — verify all approval-required actions pass through awaiting_approval before completed
    - **Validates: Requirements 1.9, 3.10, 7.6, 10.6**

  - [x] 23.2 Write property test for AI next-action suggestion (Property 18)
    - **Property 18: AI next-action suggestion availability** — verify at least one suggestion generated for any application status + days_since_last_activity combo
    - **Validates: Requirements 6.4**

- [x] 24. Integration and wiring
  - [x] 24.1 Wire Company Intel into Cover Letter, Resume, and Follow-Up agents
    - Update RAG_Agent retrieval to include `{user_id}_company` collection context
    - Ensure Cover_Letter_Agent, Resume_Agent, and Follow_Up_Agent retrieve top 3 company intel chunks
    - _Requirements: 4.5_

  - [x] 24.2 Wire Kanban status change triggers
    - On move to `interview` → suggest Interview Coach
    - On move to `offer` → suggest Salary Agent
    - Add orchestrator routing for trigger-based agent suggestions
    - _Requirements: 6.6, 6.7_

  - [x] 24.3 Write integration tests
    - Cover letter E2E: RAG → generate → HITL → store
    - Interview session: multi-turn → summary → persist
    - Company research: multi-source → pgvector → cache
    - LinkedIn outreach: Proxycurl → filter → draft → approve
    - _Requirements: 1.1-1.11, 2.1-2.11, 4.1-4.10, 10.1-10.12_

- [x] 25. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend: Python 3.12 / FastAPI / SQLAlchemy / LangGraph
- Frontend: TypeScript 5 / Next.js 14 / shadcn/ui / TanStack Query
- All new agents follow harness registration pattern: node file → harness.py → orchestrator.py → API route → main.py

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"] },
    { "id": 1, "tasks": ["1.8", "2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "4.1", "5.1", "6.1", "7.1", "9.1"] },
    { "id": 3, "tasks": ["2.4", "4.2", "4.3", "5.2", "5.3", "6.2", "7.2", "9.2", "10.1", "11.1", "12.1"] },
    { "id": 4, "tasks": ["4.4", "5.4", "6.3", "7.3", "9.3", "10.2", "11.2", "11.3", "12.2"] },
    { "id": 5, "tasks": ["12.3", "14.1", "14.2", "15.1", "16.1", "17.1", "18.1", "19.1", "20.1", "21.1", "22.1"] },
    { "id": 6, "tasks": ["14.3", "14.4", "23.1", "23.2", "24.1", "24.2"] },
    { "id": 7, "tasks": ["24.3"] }
  ]
}
```
