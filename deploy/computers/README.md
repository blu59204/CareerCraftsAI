# Private on-demand computers

Test deployment: SSH alias `24gb`, isolated directory `~/careercraft-sandbox`.
The local CareerCraft app stays at http://localhost:18180/copilot. Its backend
and Temporal worker reach the relay through an SSH tunnel on their private
Docker network. The remote relay is published only on `127.0.0.1:14312`.

OpenBot source is pinned to `b6932d31a8d6e7896c15139dfc27a6c6911deb27`.
Build the base before the private computer image. Retain the upstream license.

```sh
docker compose --env-file .env build computer-image
docker compose --env-file .env build private-computer-image supervisor relay egress
docker compose --env-file .env up -d supervisor relay egress test-portal
```

Create `.env` outside source control with independent random 32-byte secrets:
`COMPUTER_TOKEN`, `COMPUTER_SUPERVISOR_TOKEN`, `SANDBOX_RELAY_TOKEN`.
The local `deploy/local/up.ps1` reads the relay token from gitignored
`deploy/secrets/local/sandbox.env`. `sandbox-tunnel` mounts only the SSH key and
known-hosts file from that directory. It verifies the server host key.
The tunnel targets the user-authorized `24gb` host; change `tunnel.sh` if moving it.

There are eight computer slots and a 90-second inactivity timeout. Screen and
control polling neither allocates a computer nor renews its lease. Profiles and
workspace files survive sleep. A full pool returns 429; it does **not** silently
queue another browser. Temporal persists approval waits without a browser.

Browsers use an internal Docker network and a mandatory Squid egress proxy.
Private addresses and metadata endpoints are denied. The sole private HTTP
exception is the synthetic `test-portal`; remove that exception and fixture
service when leaving the test deployment. Proxy request logging is disabled.
Only the supervisor holds Docker socket access. Each child gets its own HMAC
token and isolated profile/workspace volumes.

The pinned image uses Docker isolation with Chromium's own process sandbox off
under the default Docker seccomp policy. This deployment is for testing. Before
production, configure a supported Chromium sandbox policy or a stronger container
runtime and test it with the target portals.

The model gets accessibility snapshots, never screenshots, cookies, shell,
scripts, Docker access, or credential retrieval. Browser mutations require
an immutable app approval, current computer run and reviewed snapshot.
Takeover and restarts invalidate old actions; uncertain actions are not retried.
In the expanded browser, a focused native input surface forwards mouse clicks,
text, paste and navigation keys through the human-only routes in order. Esc
leaves keyboard capture. Text is buffered briefly outside chat/state; queued
input drains before toolbar actions and is discarded on loss of control.
`verify-keyboard.py` checks typing, editing, Unicode and privacy on the fixture.
Credentials are encrypted with the existing AES-256-GCM helper, owner scoped,
and filled only into inputs belonging to the exact saved HTTPS origin.
Browser processes necessarily receive the plaintext to sign in. Session-cookie
volumes are private filesystem data, not encrypted by this vault feature.

Private typing/filling persists a marker outside the model workspace. Model page
access remains blocked until the user leaves the login page, checks that no
secrets are visible, and chooses **Finish private input**. Release human control
afterward. Deleting a saved login does not revoke portal session cookies.
Unmasking a password or changing only a URL query/fragment cannot release the
private-input block on the same page.

Verification uses only generated accounts and synthetic fixture data:

```sh
docker cp verify.py careercraft-sandbox-relay-1:/tmp/verify.py
docker exec careercraft-sandbox-relay-1 python /tmp/verify.py
# Run on the host alongside it for Docker CPU/RAM samples:
python3 observe.py > resource-samples.jsonl
```

Start with a free pool. Verification stops every computer it creates. It keeps
its profiles so workspace persistence can be inspected; do not delete other
users' volumes when cleaning synthetic test data. After changing a Compose
network, force-recreate its services so Docker DNS aliases are restored.

This is a bounded test sandbox, not a claim of support for every portal. CAPTCHA,
MFA, browser-detection challenges and login require human takeover. Saved resume
uploads use an owner-scoped document ID, a current file-input ref and a reviewed
snapshot. File bytes go directly from document storage to the browser, without
giving the model a filesystem path or file-reading capability. The user can
upload manually while holding control; agent uploads require approval.
Generic-portal submission reconciliation with the application ledger remains
unconnected; the extension workflow is the supported path for tracking those.
An active user model is required for planning. Public search and resume storage
work without one. Run `verify-upload.py` inside the relay to check uploads and
stale-approval rejection against the synthetic portal.
CopilotKit's self-managed-agent production license must be resolved before sale.
