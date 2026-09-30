"""Browser proof using a disposable Clerk account; no sends/submissions."""

import json
import os
from pathlib import Path
import tempfile

import httpx
from dotenv import dotenv_values
from playwright.sync_api import Error, expect, sync_playwright

state = json.loads((Path(tempfile.gettempdir()) / "careercraft-agent-a-live.json").read_text())
secret = dotenv_values(os.environ["CLERK_ENV_FILE"])["CLERK_SECRET_KEY"]
admin = httpx.Client(
    base_url="https://api.clerk.dev/v1/",
    headers={"Authorization": f"Bearer {secret}"},
    timeout=15,
    transport=httpx.HTTPTransport(retries=2),
)
response = admin.post(f"sessions/{state['session_id']}/tokens", json={})
response.raise_for_status()
client = httpx.Client(
    base_url="http://localhost:18180/api/v1/",
    headers={"Authorization": f"Bearer {response.json()['jwt']}"},
    timeout=30,
)
assert client.patch("users/me", json={"onboarding_completed": True}).status_code == 200
response = admin.post(
    "sign_in_tokens", json={"user_id": state["clerk_user_id"], "expires_in_seconds": 600}
)
response.raise_for_status()
ticket = response.json()["token"]
checks = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    page.goto("http://localhost:18180/login")
    page.wait_for_function("window.Clerk && window.Clerk.loaded", timeout=60000)
    try:
        page.evaluate(
            """async ticket => {
            const result = await window.Clerk.client.signIn.create({strategy: 'ticket', ticket});
            await window.Clerk.setActive({session: result.createdSessionId});
        }""",
            ticket,
        )
    except Error as exc:
        if "Execution context was destroyed" not in str(exc):
            raise
    page.wait_for_function("window.Clerk && window.Clerk.session", timeout=60000)
    page.goto(f"http://localhost:18180/resume?document={state['document_id']}")
    edit = page.get_by_role("button", name="Edit text", exact=True)
    expect(edit).to_be_enabled(timeout=60000)
    edit.click()
    editor = page.get_by_label("Resume text (markdown)")
    marker = "- Delivered 4 verified test projects using Python."
    editor.fill(editor.input_value() + "\n" + marker + "\n")
    with page.expect_response(
        lambda response: "/fix" in response.url and response.request.method == "POST", timeout=60000
    ) as saved:
        page.get_by_role("button", name="Save changes", exact=True).click()
    assert saved.value.status == 200
    page.reload()
    expect(edit).to_be_enabled(timeout=60000)
    edit.click()
    assert marker in editor.input_value()
    page.get_by_role("button", name="Cancel", exact=True).click()
    score = page.locator("section[aria-labelledby='primary-resume-heading']")
    expect(score).to_contain_text("Estimated ATS compatibility", timeout=30000)
    checks.append("Real Clerk browser: edit, save, reload, preserved text and current score")
    page.goto("http://localhost:18180/linkedin")
    page.get_by_label("LinkedIn profile PDF").set_input_files(
        {"name": "broken.pdf", "mimeType": "application/pdf", "buffer": b"%PDF- broken"}
    )
    page.get_by_label("Target role", exact=True).fill("Engineer")
    with page.expect_request(
        lambda request: "/linkedin/profile/optimize" in request.url, timeout=30000
    ) as uploaded:
        page.get_by_role("button", name="Analyze uploaded profile", exact=True).click()
    assert "multipart/form-data; boundary=" in uploaded.value.headers["content-type"]
    expect(page.get_by_role("alert")).to_contain_text("could not be read", timeout=30000)
    checks.append(
        "Real browser LinkedIn upload sends bounded multipart data and displays parse error"
    )
    browser.close()
print(json.dumps({"checks": checks, "count": len(checks)}, indent=2))
