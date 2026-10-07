"""Targeted browser-profile persistence proof with disposable fixture data."""

import json
import os
import uuid

import httpx

c = httpx.Client(
    base_url="http://127.0.0.1:4302",
    timeout=75,
    headers={"Authorization": "Bearer " + os.environ["SANDBOX_RELAY_TOKEN"]},
)
user = str(uuid.uuid4())
base = f"/users/{user}"


def action(op, params=None):
    response = c.post(
        base + "/action", json={"operation": op, "parameters": params or {}}
    )
    response.raise_for_status()
    return response.json()


try:
    c.post(base + "/start").raise_for_status()
    action("navigate", {"url": "http://test-portal/"})
    handoff = action("control/request", {"reason": "Profile persistence test"})
    request = handoff["request"]["id"]
    action("control/take", {"requestId": request})
    # User input simulation is intentionally private, even with synthetic data.
    snapshot = action("snapshot")
    refs = {x["name"]: x["ref"] for x in snapshot["elements"]}
    action("control/release", {"requestId": request})
    snapshot = action("snapshot")

    # These synthetic nonsecret fields can use the model action path.
    def agent(op, params):
        response = c.post(
            base + "/action",
            json={
                "operation": op,
                "parameters": params,
                "actor": "agent",
                "computer_run": snapshot["computer_run"],
                "approved_snapshot": snapshot["snapshotId"],
            },
        )
        response.raise_for_status()

    for label, value in [
        ("Full name", "Synthetic Profile Test"),
        ("Email", "fixture@example.com"),
        ("Cover letter", "Profile persistence test"),
    ]:
        refs = {x["name"]: x["ref"] for x in snapshot["elements"]}
        agent(
            "type",
            {"ref": refs[label], "snapshotId": snapshot["snapshotId"], "text": value},
        )
        snapshot = action("snapshot")
    refs = {x["name"]: x["ref"] for x in snapshot["elements"]}
    agent(
        "click",
        {"ref": refs["Submit test application"], "snapshotId": snapshot["snapshotId"]},
    )
    c.post(base + "/stop").raise_for_status()
    c.post(base + "/start").raise_for_status()
    request = action("control/request", {"reason": "Review restored browser"})[
        "request"
    ]["id"]
    action("control/take", {"requestId": request})
    action("human/navigate", {"url": "http://test-portal/"})
    action("control/release", {"requestId": request})
    # Snapshots list interactive elements; the receipt is ordinary page text.
    page = action("read")
    assert "Previously submitted test applications: 1" in json.dumps(page), page
    print("PASS: browser localStorage persisted through computer stop/start")
finally:
    c.post(base + "/stop")
