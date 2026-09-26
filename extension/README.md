# CareerCraft AI — Apply Assistant (Chrome extension)

Applies to jobs **in your own browser**, where you are already signed in to
LinkedIn, Naukri and company career sites. CareerCraft never runs a browser
for you on its servers and never sees your job-site passwords or cookies.

Every application ends with **you** pressing **Submit application** in the
extension's review panel. Nothing is submitted before that.

## Install (unpacked, for now)

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Click **Load unpacked** and pick this `extension/` folder.
3. Pin **CareerCraft AI — Apply Assistant** to the toolbar.

Chrome 110 or newer (Edge and Brave work too).

## Connect it to your account

1. In CareerCraft open **Settings → Integrations → Browser extension** and
   click **Connect this browser**. When CareerCraft runs on `localhost` the
   extension picks the connection up by itself.
2. Otherwise copy the connection code (`ccx_…`), open the extension popup,
   enter your CareerCraft URL and the code, and press **Connect**. Chrome
   asks once for permission to talk to your CareerCraft site.

Each connected browser appears in Settings, where you can revoke it. The
code is shown once and only its hash is stored on the server.

## How applying works

1. Press **Apply** on a saved job in CareerCraft. The server starts a
   durable Temporal workflow and queues the application for your browser.
2. The extension picks it up within seconds (it also checks every 30 s),
   opens the job page in a new tab and fills what it can:
   - your saved answers and profile (name, email, phone, links…),
   - your resume PDF on upload fields,
   - a **draft** for free-text questions ("Why do you want to join?"),
     written by your own configured model and marked *Draft — review*.
3. A review panel lists every answer with where it came from. Questions it
   must never guess stay empty for you: visa sponsorship, work
   authorization, salary, notice period, and consent checkboxes.
   With **Remember my answers** on, what you type is reused next time.
4. You press **Submit application** in the panel. The extension clicks the
   site's submit control, reads the confirmation, and reports back.
   CareerCraft marks the job *Applied* and schedules day-5 and day-12
   follow-up drafts (which also wait for your approval).

Supported flows: LinkedIn **Easy Apply** (multi-step), **Naukri** (the review
panel appears *before* Naukri's one-click Apply) and single-page ATS forms
(Greenhouse, Lever, Ashby, Workday, most company career pages). Jobs that
send you to an external site from LinkedIn/Naukri are reported as such.

If you are signed out, a CAPTCHA appears, or a question needs you, the
panel says so and waits. Closing the tab cancels the application.

## Decisions on the page

When plain text matching is not enough — which button advances this form,
which dropdown option matches your saved answer, does this page confirm the
submission — the extension asks the backend's decision engine
(`POST /api/v1/extension/device/decide`). The server answers with a fast
typed-decision model: TypeSafe **Jev** (`TYPESAFE_API_KEY`) or a
self-hosted **Laya** (`LAYA_URL`, see `deploy/laya/`), falling back to
built-in heuristics. It acts only above a confidence threshold; anything
less is left to you.

## Please read

Automating job applications may breach some sites' terms of service —
LinkedIn's User Agreement, for example, restricts automated activity. You
stay responsible for how you use this: every submission is approved by you,
the extension paces its actions like a person, and it never solves CAPTCHAs.

## Development

- `src/background.js` — service worker: pairing, polling, all network calls.
- `src/content/*.js` — injected into the job tab: DOM helpers, review panel
  (closed shadow DOM), platform drivers, and the runner.
- `test/fixtures/` — Greenhouse-, LinkedIn- and Naukri-like pages.
- `test/e2e_live.py` — end-to-end run against a local stack (see its
  docstring): real API, Temporal worker and this extension in Chromium.

CI syntax-checks every script and the manifest.
