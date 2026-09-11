"""E2E sign-in through the real UI using the email_code first factor.

Uses a Clerk test email (+clerk_test), whose verification code is always 424242
on a development instance, so no mailbox access is needed.
"""
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:3000")
EMAIL = os.environ.get("E2E_EMAIL", "cc.e2e+clerk_test@gmail.com")
CODE = "424242"
SHOTS = "../e2e_shots"
os.makedirs(SHOTS, exist_ok=True)

problems, console = [], []

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.on("console", lambda m: console.append(m.text[:180]) if m.type == "error" else None)
    api_bad = []
    pg.on("response", lambda r: api_bad.append(f"{r.status} {r.url[-58:]}")
          if "/api/v1/" in r.url and r.status >= 400 else None)

    pg.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)

    pg.fill("input[type=email]", EMAIL)
    pw = pg.query_selector("input[type=password]")
    if pw:
        pw.fill(os.environ["E2E_PASSWORD"])
    pg.wait_for_timeout(300)
    pg.click("button[type=submit]")
    pg.wait_for_timeout(9000)
    pg.screenshot(path=os.path.join(SHOTS, "code-01-after-identifier.png"))

    body = pg.evaluate("document.body.innerText.slice(0,220).replace(/\\s+/g,' ')")
    print("after identifier submit:", body[:170])

    code_input = (pg.query_selector("input[name=code]")
                  or pg.query_selector("input[inputmode=numeric]")
                  or pg.query_selector("input[maxlength='6']"))
    if not code_input:
        problems.append("no code field appeared — email_code fallback did not trigger")
        print("!! no code input")
    else:
        code_input.fill(CODE)
        pg.wait_for_timeout(500)
        sb = pg.query_selector("button[type=submit]")
        if sb and sb.is_enabled():
            sb.click()
        else:
            pg.keyboard.press("Enter")
        pg.wait_for_timeout(10000)

    signed = pg.evaluate("!!(window.Clerk && window.Clerk.user)")
    print("signed_in:", signed, "| url:", pg.url[:80])
    pg.screenshot(path=os.path.join(SHOTS, "code-02-after-code.png"))
    if not signed:
        problems.append("session not established after submitting the code")
        print("page:", pg.evaluate("document.body.innerText.slice(0,220).replace(/\\s+/g,' ')")[:200])

    if signed:
        for path in ("/dashboard", "/agents", "/jobs", "/resume",
                     "/applications", "/settings/models"):
            pg.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(3500)
            bounced = "/login" in pg.url
            txt = pg.evaluate("document.body.innerText.slice(0,90).replace(/\\s+/g,' ')")
            print(f"  {path:<18} {'BOUNCED' if bounced else 'OK':<8} {txt[:62]!r}")
            pg.screenshot(path=os.path.join(SHOTS, "code-page" + path.replace("/", "-") + ".png"))
            if bounced:
                problems.append(f"{path} bounced to login while signed in")

    b.close()

print("\n=== failing /api/v1 calls ===")
for f in dict.fromkeys(api_bad):
    print("  ", f)
if not api_bad:
    print("   none")
print("=== console errors ===")
for c in list(dict.fromkeys(console))[:8]:
    print("  ", c[:150])
if not console:
    print("   none")
print("=== problems ===")
for x in problems:
    print("  -", x)
if not problems:
    print("   none")
