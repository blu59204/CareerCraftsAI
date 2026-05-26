# Product: JobAgent AI

JobAgent AI is a multi-agent job search automation platform. Users bring their own AI API keys (BYOK) and the platform deploys specialized AI agents to handle every step of the job search process.

## Core Value Proposition

- Automates resume tailoring, job discovery, application submission, LinkedIn optimization, and recruiter follow-ups
- Users pay only for their own AI API usage — no platform subscription for AI costs
- Human-in-the-loop gate: no email is sent and no application is submitted without explicit user approval

## Agent Harness

| Agent | Responsibility |
|---|---|
| Orchestrator | LangGraph supervisor — routes tasks, manages state |
| Job Search | Browses job boards via PinchTab, scores matches 0–100 |
| Resume | RAG-powered resume rewriting per job description, PDF generation |
| LinkedIn | Rewrites headline, About, and experience bullets |
| Email | Reads Gmail threads, drafts personalized outreach |
| Follow-Up | Schedules day-5 and day-12 follow-up emails after application |
| RAG | Retrieves context from user documents via pgvector |

## Key Constraints

- **Human approval required** before any email send or job application submit — this is enforced server-side via the `/approve` endpoint
- **BYOK model router** — never hardcode a model; always route through `model_router` using the user's active `user_model_settings`
- **API keys encrypted at rest** — AES-256-GCM; never store or log plaintext keys
- **All agent actions logged** to `agent_runs` table (status, input, output, tokens_used, duration_ms)
- LinkedIn/Naukri automation may violate platform ToS — PinchTab interactions must use human-like delays
