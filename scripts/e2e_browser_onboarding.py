"""Sign in with an existing user, then drive the onboarding wizard to completion."""
import os
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:4400")
EMAIL = os.environ["E2E_EMAIL"]
PASSWORD = os.environ["E2E_PASSWORD"]
CODE = "424242"
SHOTS = "../e2e_shots"
os.makedirs(SHOTS, exist_ok=True)

problems, console, api_bad = [], [], []

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.on("console", lambda m: console.append(m.text[:170]) if m.type == "error" else None)
    pg.on("response", lambda r: api_bad.append(f"{r.status} {r.request.method} {r.url[-52:]}")
          if "/api/v1/" in r.url and r.status >= 400 else None)

    # ---- sign in (password -> emailed second factor) ----
    pg.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    pg.fill("input[type=email]", EMAIL)
    pg.fill("input[type=password]", PASSWORD)
    pg.click("button[type=submit]")
    pg.wait_for_timeout(9000)
    code_in = (pg.query_selector("input[name=code]")
               or pg.query_selector("input[inputmode=numeric]")
               or pg.query_selector("input[maxlength='6']"))
    if code_in:
        code_in.fill(CODE)
        pg.wait_for_timeout(500)
        sb = pg.query_selector("button[type=submit]")
        (sb.click() if sb and sb.is_enabled() else pg.keyboard.press("Enter"))
        pg.wait_for_timeout(10000)
    signed = pg.evaluate("!!(window.Clerk && window.Clerk.user)")
    print("signed_in:", signed, "| landed:", pg.url.replace(BASE, "")[:50])
    if not signed:
        problems.append("could not sign in")
        b.close()
        raise SystemExit(1)

    # ---- onboarding ----
    pg.goto(f"{BASE}/onboarding", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(5000)
    print("\n=== ONBOARDING WIZARD ===")
    seen = []
    for step in range(1, 12):
        head = pg.evaluate(
            "document.body.innerText.slice(0,130).replace(/\\s+/g,' ')")
        fields = pg.evaluate(
            "[...document.querySelectorAll('input,textarea,select')].filter(e=>e.offsetParent)"
            ".map(e=>(e.tagName.toLowerCase())+':'+(e.name||e.placeholder||e.type)).slice(0,8)")
        btns = pg.evaluate(
            "[...document.querySelectorAll('button')].filter(b=>b.offsetParent)"
            ".map(b=>b.innerText.trim()).filter(Boolean).slice(0,8)")
        sig = head[:60]
        print(f"\n  step {step}: {head[:96]!r}")
        print(f"    fields : {fields}")
        print(f"    buttons: {btns}")
        pg.screenshot(path=os.path.join(SHOTS, f"onb-{step:02d}.png"))

        if sig in seen:
            problems.append(f"onboarding stuck — step {step} repeats a previous screen")
            print("    !! screen repeated; stopping")
            break
        seen.append(sig)

        # populate any visible empty control so the advance button enables
        pg.evaluate("""() => {
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
          const tsetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
          document.querySelectorAll('input,textarea').forEach(e=>{
            if(!e.offsetParent) return;
            if(e.type==='file') return;                 // set via set_input_files
            if(e.type==='checkbox'||e.type==='radio'){ if(!e.checked){ e.click(); } return; }
            if(e.value) return;
            const v = e.type==='number' ? '3'
                    : /salary|ctc|lpa/i.test(e.name+e.placeholder) ? '1200000'
                    : /location|city/i.test(e.name+e.placeholder) ? 'Bangalore'
                    : /role|title|job/i.test(e.name+e.placeholder) ? 'Software Engineer'
                    : 'Software Engineer';
            (e.tagName==='TEXTAREA'?tsetter:setter).call(e, v);
            e.dispatchEvent(new Event('input',{bubbles:true}));
            e.dispatchEvent(new Event('change',{bubbles:true}));
          });
        }""")
        pg.wait_for_timeout(900)

        # Real upload on the resume step — also exercises the local-disk
        # storage rewrite and the parse/RAG path behind it.
        fi = pg.query_selector("input[type=file]")
        if fi:
            fi.set_input_files("tests/fixtures/test_resume.pdf")
            print("    uploaded tests/fixtures/test_resume.pdf")
            pg.wait_for_timeout(9000)
            print("    after upload:", pg.evaluate(
                "document.body.innerText.slice(0,150).replace(/\s+/g,' ')")[:130])

        nxt = None
        for label in ("Continue", "Next", "Finish", "Complete", "Get started", "Save", "Done", "Let's go"):
            el = pg.query_selector(f"button:has-text('{label}')")
            if el and el.is_enabled() and el.is_visible():
                nxt = (el, label)
                break
        if not nxt:
            enabled = pg.evaluate(
                "[...document.querySelectorAll('button')].filter(b=>b.offsetParent && !b.disabled)"
                ".map(b=>b.innerText.trim()).slice(0,6)")
            problems.append(f"step {step}: no advance button (enabled buttons: {enabled})")
            print(f"    !! no advance button; enabled = {enabled}")
            break
        print(f"    -> clicking {nxt[1]!r}")
        nxt[0].click()
        pg.wait_for_timeout(4500)
        if "/onboarding" not in pg.url:
            print(f"    left onboarding -> {pg.url.replace(BASE,'')[:50]}")
            break

    print("\nfinal url:", pg.url.replace(BASE, "")[:60])
    pg.screenshot(path=os.path.join(SHOTS, "onb-final.png"))

    # did it persist?
    prof = pg.evaluate("""async () => {
      try { const r = await fetch('/api/v1/users/me', {headers:{}}); return r.status; }
      catch(e){ return String(e).slice(0,60); } }""")
    print("users/me from browser:", prof)

    for path in ("/dashboard", "/jobs", "/settings/models"):
        pg.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(3500)
        txt = pg.evaluate("document.body.innerText.slice(0,80).replace(/\\s+/g,' ')")
        onb = "/onboarding" in pg.url
        print(f"  {path:<18} -> {pg.url.replace(BASE,'')[:26]:<26} {'(still onboarding)' if onb else 'OK'} {txt[:44]!r}")

    b.close()

print("\n=== failing /api/v1 ===")
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
