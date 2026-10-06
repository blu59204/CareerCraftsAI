"""Unmasking a password must not clear the model's private-input block."""

import json
import os
import uuid

import httpx

c = httpx.Client(
    base_url="http://127.0.0.1:4302",
    timeout=75,
    headers={"Authorization": "Bearer " + os.environ["SANDBOX_RELAY_TOKEN"]},
)
base = "/users/" + str(uuid.uuid4())


def action(op, params=None, actor="human", expected=200, run=None):
    result = c.post(
        base + "/action",
        json={
            "operation": op,
            "parameters": params or {},
            "actor": actor,
            "computer_run": run,
        },
    )
    assert result.status_code == expected, (op, result.status_code)
    return result.json()


try:
    c.post(base + "/start").raise_for_status()
    action("navigate", {"url": "http://test-portal/login.html"})
    snapshot = action("snapshot")
    refs = {e["name"]: e["ref"] for e in snapshot["elements"]}
    action(
        "credentials/fill",
        {
            "origin": "http://test-portal",
            "username": "fixture@example.com",
            "password": "synthetic-private-password",
            "usernameRef": refs["Email"],
            "passwordRef": refs["Password"],
            "snapshotId": snapshot["snapshotId"],
        },
        run=snapshot["computer_run"],
    )
    request = action("control/request", {"reason": "Synthetic privacy test"})[
        "request"
    ]["id"]
    action("control/take", {"requestId": request})
    action("human/key", {"key": "Tab"})
    action("human/key", {"key": "Enter"})
    assert "Hide password" in json.dumps(action("snapshot"))
    action("read", actor="agent", expected=409)
    action("snapshot", actor="agent", expected=409)
    action("privacy/release", expected=409)
    action("human/navigate", {"url": "http://test-portal/"})
    action("privacy/release")
    action("control/release", {"requestId": request})
    action("snapshot", actor="agent")
    print("PASS: unmasked password remains private; release requires leaving its page")
finally:
    c.post(base + "/stop")
