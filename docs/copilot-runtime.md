# Career Copilot runtime

The `/copilot` page connects directly to the authenticated AG-UI endpoint at
`/api/v1/agents/chat` using a self-managed `HttpAgent`. A CopilotKit runtime URL
is unnecessary because the Python server speaks AG-UI directly. The fetch
transport gets a Clerk session token for every request.

The copilot can start whitelisted career tasks, check runs, list applications,
and search public job boards. Run creation goes through `queue_agent_run`,
including ownership checks, admission locking, concurrency caps, database
logging, and Temporal dispatch. The model is resolved from the member's settings
using their database UUID and a key-free gateway session.

Chat cards poll the owner-scoped run-detail endpoint. Auto-apply cards also show
the child application runs. Review approval opens the existing approval dialog,
which sends the user's decision to `POST /agents/{run_id}/approve`. There is no
model tool for approval or submission. Auto-apply accepts a target role, location,
and up to five applications; it does not schedule weekly work or take saved-job
IDs.

The paired browser extension is responsible for form interactions. Server
browser task execution is retired: `run_browser_task` raises an error and
`AutoApplyWorkflow` rejects execution modes other than `extension`.
This integration does not provision a new isolated
terminal or computer, or give the chat model arbitrary shell access.

Threads use per-account browser storage and owner-scoped server checkpoint keys.
New chat creates a fresh client agent. The server checkpoint store is in memory:
history does not survive backend restarts and is not shared across API replicas.
Use one API process for this v1 chat deployment until durable checkpoints land.

For a live smoke test, start PostgreSQL, Redis, Temporal, the Temporal worker,
the API, and the frontend using the project's existing development setup. Sign
in and configure an active model under Settings → Models. Ask the copilot to
start a job search with a role and location. Its card should progress from queued
to running to awaiting approval. Open Review approval, inspect the full payload,
and approve or reject. Confirm the same run progresses on the Agents page.
For auto-apply, approve the prepared batch, then review each application in
the paired extension. Generic agent approval cannot submit an extension
application. Final submission uses the extension's own approval gate.

See [OpenDots sandbox comparison](opendots-sandbox.md) for the additional
computer layer required by the user's sandbox request.
