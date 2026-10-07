# OpenDots sandbox comparison

Research date: 2026-10-05. The comparison below informed the implementation.
A bounded test sandbox is now deployed on SSH `24gb` and connected to the local
Copilot. See [measured results and remaining gaps](sandbox-24gb-results.md) and
[deployment instructions](../deploy/computers/README.md) for its current status.

## Intended experience

The member asks for a career task in chat and watches the agent perform it
in a persistent isolated computer. For example, "Find remote Python jobs
and prepare three applications" should search, tailor documents, show the
drafts, fill the approved applications, and present each completed form for
final review. The member can take control for login or missing information.
After the member explicitly approves submission, the system records the
outcome and schedules the existing follow-up workflow.

Automatic preparation is compatible with CareerCraft's mandatory human
review. Unattended submission is not. Supported tasks must be backed by real
capabilities; arbitrary requests cannot be promised as completed work.

## What OpenDots supplies

[Computer documentation](https://github.com/CopilotKit/OpenDots/blob/main/docs/COMPUTERS.md)
describes separate persistent computers, browser/file/shell capabilities,
live browser inspection, and takeover that pauses agent input. These come
from OpenBot, not from the AG-UI chat transport. Workspace and browser
profile volumes survive stop/start. Computer permissions are checked by
the server and start disabled. Service failure never falls back to host
execution.

[Deployment reference](https://github.com/CopilotKit/OpenDots/blob/main/deployment/computers/README.md)
pins OpenBot revision `b6932d31a8d6e7896c15139dfc27a6c6911deb27` and patches
the supervisor to give each computer its own derived credential. Master
credentials remain in the trusted application and supervisor. Only the
supervisor mounts the Docker socket. Adoption should preserve these
boundaries and review any later source revision before upgrading.

OpenDots uses ordinary Docker isolation and does not configure restricted
network egress. Its single-owner template needs account ownership controls
before reuse in a multi-user application such as CareerCraft.

## Credentials and portal access

Reviewed the OpenBot documentation and source at the pinned revision above:
[architecture](https://github.com/CopilotKit/OpenBot/blob/b6932d31a8d6e7896c15139dfc27a6c6911deb27/docs/architecture.md),
[credential vault](https://github.com/CopilotKit/OpenBot/blob/b6932d31a8d6e7896c15139dfc27a6c6911deb27/server/src/credentials.ts),
and [computer gateway](https://github.com/CopilotKit/OpenBot/blob/b6932d31a8d6e7896c15139dfc27a6c6911deb27/server/src/computer/gateway.ts).
The moving `main` branch has additional capabilities; it must not be treated
as the contract of the pinned computer image.

There are two distinct mechanisms:

- The server credential vault encrypts secret values with AES-GCM using a
  configured 32-byte encryption key, a fresh 12-byte IV, and a versioned
  encrypted envelope. APIs expose status and references rather than plaintext.
  Trusted server integrations resolve live credentials for use; missing and
  revoked credentials are refused. Rotation is transactional. This is not
  evidence of an automatic password-login adapter for every website.
- Portal login can use human takeover or the dedicated browser secret-entry
  path. The agent requests a field using a current element reference and
  snapshot ID. The member supplies the value through `human/secret`; the
  computer types it directly into that field and forgets the request. It
  returns only delivery metadata and character count, and does not submit
  the login form. The gateway audits secret request/supply without the value.

Once login succeeds, the isolated persistent Chromium profile retains the
site's session subject to that site's expiry and authentication rules. Later
tasks use the browser session. MFA, CAPTCHA, expired sessions, or consent
screens can still require the member to take over. Profiles contain sensitive
session material: persistence is not a claim that browser cookies are
encrypted with the credential vault's key.

For CareerCraft, reuse the existing model-key encryption and gateway rather
than deploying a second model vault. Add private secret entry and takeover
to the computer panel for portal login. If saved portal passwords are added,
they need account-scoped encrypted storage and a trusted, exact-origin
injection path; pass the agent a credential reference, never the decrypted
password. Do not put secrets into chat, workspace files, task context,
Temporal history, or agent action output. Do not expose shell or arbitrary
browser scripting that can read profiles or retrieve injected passwords.

## Current CareerCraft behavior

| Capability | Current implementation | Sandbox gap |
| --- | --- | --- |
| Natural-language task routing | `chat_orchestrator.py` starts whitelisted runs through existing admission checks | Computer tools are absent |
| Long-running jobs | Temporal workflows and application attempt ledger | Add a computer executor through workflow activities |
| Application preparation | Auto-apply searches and prepares drafts; account mode determines batch actions | Display the computer's actual browser state |
| Form execution | `AutoApplyWorkflow` accepts extension mode only | No container executor is active |
| Server browser compatibility helper | `run_browser_task` explicitly raises an error | Do not revive retired host browser execution |
| Review | Batch review through agent approval; final form review through extension approval | Computer submission needs an explicit review-bound path |
| Run UI | Copilot run cards and existing Agents page | No computer panel, takeover, workspace, or terminal |
| Model execution | BYOK gateway and `agent_runs` logging | Retain both for all computer agent calls |

Evidence is in `backend/app/workflows/auto_apply.py`,
`backend/app/workflows/starters.py`,
`backend/app/services/workflow_service.py`,
`backend/app/services/browser_control_service.py`, and
`backend/tests/unit/test_extension_only_execution.py`. Legacy helper names
and old reference documentation are not evidence of a functioning server
executor.

## Integration boundaries

1. Reuse the pinned OpenBot computer and supervisor deployment. Give each
   member's Career Copilot a separate server-derived computer identity and
   persistent volumes. The authenticated backend selects that identity;
   client or model arguments cannot select another member's computer.
2. Expose browser inspection and workspace operations through an
   authenticated backend. Proxy screen and takeover actions without sending
   supervisor or computer credentials to the frontend. Shell starts disabled.
   Never mount CareerCraft secrets or its host workspace into the computer.
3. Keep the gateway, Temporal, admission limits, and application attempt
   ledger as their existing owners. Container lifecycle is not a replacement
   for durable workflow state or duplicate-submission protection.
4. Add computer execution as an explicitly supported application workflow
   path. Preserve extension execution and account ownership. Existing
   workflows must remain replay-compatible during deployment.
5. Require both document review and final-form review. A free-form browser
   click, shell command, or arbitrary network request can also submit a form;
   merely omitting a tool named `submit` or adding a prompt instruction does
   not enforce the gate. Submission-capable tools must remain behind an
   approval-bound executor. A generic computer session must not silently
   acquire application submission authority.
6. Takeover pauses the executor, with a fresh browser snapshot on handback.
   Login, site challenges, missing fields, rejection, cancellation, and
   uncertain submission outcomes must become visible workflow states.

## Required proof before calling this complete

- Two accounts cannot inspect or control each other's computers or files.
- Stop/start retains the correct account's workspace and browser profile.
- Unavailable services fail clearly without executing on the host.
- Takeover prevents concurrent agent input; handback refreshes page state.
- A local mock job portal exercises search, documents, filling, rejection,
  explicit final approval, submission receipt, and application logging.
- A model cannot bypass final review using other browser or computer tools.
- Retried approvals and workflow activities do not duplicate submission.
- Live model execution is tested using the member's configured provider.

The current local deployment is usable for testing chat orchestration. It
does not yet satisfy the persistent computer sandbox described above, and
end-to-end model execution still needs an active model in Settings → Models.

For efficient fleet sizing, use the proposed
[browser-on-demand architecture](sandbox-capacity-architecture.md). A persistent
account workspace/profile does not require an always-running account computer.
