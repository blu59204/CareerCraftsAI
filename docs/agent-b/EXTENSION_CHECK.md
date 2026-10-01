# Extension approval verification

Automated checks:

```powershell
cd D:\CareerCraft-agent-b\backend
& 'D:\CareerCraft AI\backend\.venv\Scripts\python.exe' -m pytest tests/unit/test_extension_submit_gate.py tests/unit/test_extension_backend.py -q
cd ..
node extension/test/submit_sender.test.mjs
node --check extension/src/background.js
node --check extension/src/content/runner.js
```

Manual browser script (requires a development Clerk account, PostgreSQL,
Temporal worker and matching migrated API; never use a real application):

1. Load `extension/` unpacked in Chrome. Serve the recorded forms in
   `extension/test/fixtures` on a controlled public HTTPS test host. Configure
   a test application with that URL and an owned, approved PDF. Local HTTP
   job forms are deliberately rejected; localhost HTTP is allowed for the app.
2. Pair from Settings or the popup. Verify the Next.js `/api/v1` rewrite reaches
   FastAPI. A wrong app URL, invalid token and stopped backend must produce a
   visible error. Revoke the device; subsequent device calls must return 401.
3. Start prepare-apply. On an unfamiliar host, deny permission, then grant it
   through the popup. The existing claimed task must continue, without a new
   application or an automatic submit. Observe zero submits in the test host.
4. Fill/edit required fields in the job-page panel. Request final review. Open
   the extension popup: check URL, final values and uploaded file names. Close
   the popup without approval: the test host still has zero submits.
5. Confirm **Submit this application** in the popup. Exactly one submit is
   allowed; repeated popup clicks or terminal events must return conflict.
   Confirm `ApplicationAttempt` transitions to submitting, then verified only
   with confirmation text. Device tokens and capability plaintext must not
   appear in logs or workflow history.
6. Repeat with the form changed after review, review older than five minutes,
   another task/tab/frame, or another device. Each must fail before any click.
7. Kill/restart the extension worker after approval or navigate after clicking.
   No refill or second submit is allowed. Missing confirmation, cancelled tab
   and workflow timeout after approval must leave `outcome_unknown`; no retry.
8. Walk recorded Greenhouse/Lever and LinkedIn/Naukri fixtures. Check login and
   CAPTCHA stop for manual input and human delays remain. Naukri additional
   questions after its initial Apply require manual completion; CareerCraft
   never automates a second submit under the first approval.

The previous `e2e_live.py` assumes HTTP job fixtures and page-panel-only approval.
It is not evidence for this contract. The steps above replace it until the MV3
runner is updated. No live external applications were submitted during checks.


Controlled MV3 gate automation: `python extension/test/mv3_gate.py` launches unpacked Chromium against a disposable fixture API. It opens the real browser action popup, uses a trusted CDP mouse click, and verifies no content-script approval, unchanged snapshot acceptance despite Chrome storage key order, changed snapshot rejection, and single-consumption replay rejection. This check passed; it sends no external application. The server-side event authorization and final ledger paths are checked separately on real disposable PostgreSQL by the durable integration suite.
