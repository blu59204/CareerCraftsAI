# Browser application execution

Applications execute in the user's paired Chrome extension. The server does
not hold job-board sessions or run an application browser pool.

The backend authenticates revocable device tokens, claims tasks for one
device, resolves approved documents and records task events. Temporal owns
task lifecycle and the application-attempt ledger. The extension owns portal
navigation, form filling and the user's explicit review before submission.
Uncertain submission outcomes require manual verification rather than retry.

LinkedIn and Naukri are optional. Interactions use human-paced delays and stop
for login, CAPTCHA or anti-bot challenges. No challenge solving, proxy rotation
or bot-detection evasion is permitted.

Public job discovery uses independent source connectors. Source failures must
not start a server application browser or share another user's credentials.

See [ARCHITECTURE.md](ARCHITECTURE.md), [extension/README.md](../extension/README.md)
and [Agent B plan](agent-b/PLAN.md) for contracts, deployment and verification.
