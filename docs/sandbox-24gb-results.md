# SSH 24gb sandbox test — 2026-10-05

Implemented and tested on the user-authorized host: ARM64, four CPU cores,
23.41 GiB RAM. Existing unrelated services were retained. CareerCraft's app,
database and Temporal remain local; the remote host supplies browser computers.
This test therefore does not size the complete application backend or LLM costs.

The local test entry point is http://localhost:18180/copilot. Start the computer,
open the default synthetic employer URL, and use the browser task box or chat.
Settings → Models must have an active model before an LLM can propose actions.
Each proposed browser change appears as a reviewable approval card.

## Measured fixture workload

Computer allocation and readiness completed before the timed operation. The
browser itself starts lazily on the first navigation. Independent users then
loaded the fixture and took a snapshot simultaneously.

| Browsers | Mean first navigation + snapshot | Slowest request | Three concurrent snapshot rounds |
|---|---:|---:|---:|
| 1 | 0.754 s | 0.754 s | 0.336 s |
| 4 | 1.697 s | 1.899 s | 1.081 s |
| 8 | 3.297 s | 3.864 s | 2.213 s |

Across seven Docker samples with eight computers present, their maximum combined
working memory was **1,867.4 MiB (1.82 GiB)**. Maximum sampled CPU was **274.85%**,
equivalent to **2.75 cores**; Docker's 100% represents one fully used core.
Sampling mixes startup, loaded pages and subsequent actions, so this is neither
a steady-state CPU allocation nor a high-frequency peak measurement. Individual
loaded fixture computers used approximately 230–240 MiB. Shared relay, supervisor,
proxy and fixture service added approximately 160 MiB during these observations.

Each computer has a **1 GiB memory ceiling**, which is a cap rather than reserved
RAM. Pool capacity is eight. The ninth start returned 429 without allocating.
These results support multiple lightweight browsers on shared CPUs; they do not
establish 15 continuously active browsers per CPU or capacity for 10,000 active
browsers. Real career portals, long sessions and uploads need further measurement.

## Verified behavior

- Filled synthetic name/email/cover letter and confirmed exactly one fixture receipt.
- Refused actions with stale computer runs and stale snapshots.
- Denied model screenshot, human typing and credential-fill capabilities.
- Kept one user's workspace file invisible to another user.
- Refused saved-login filling on a different origin.
- Blocked model read/snapshot/navigation during private login.
- Kept an unmasked password private and refused releasing the block on its
  original page, even after the password field became an ordinary text input.
- Retained the private-input block and workspace through stop/start.
- Verified Chromium localStorage survives computer stop/start using the
  fixture's persisted submission counter.
- Invalidated old actions after human takeover and handback.
- Blocked private-service and cloud-metadata navigation through the egress proxy.
- Stopped an inactive computer despite repeated screenshot polling; sleeping
  screenshot requests returned 409 instead of allocating a computer.
- Stopped all generated benchmark computers afterward.

All **62 focused app tests passed** against the rebuilt backend container. They
cover planner approval, immutable payloads, unknown outcomes,
owner scope, secret-safe validation, and existing chat/workflow behavior.
Frontend compilation and backend startup were checked. No real job application
or email was sent. The current test account has no active provider configured,
so provider-backed autonomous planning remains unverified in that account.

The largest current savings come from using the shared job catalog/HTTP adapters
for discovery, keeping ordinary chat/resume work outside browser computers, and
sleeping browsers during waits. The next scale step is a durable browser queue
and measured admission policy; the current full-pool behavior is an explicit busy
response. Browser isolation, credential boundaries and human approvals remain.

See [deployment and boundaries](../deploy/computers/README.md).
