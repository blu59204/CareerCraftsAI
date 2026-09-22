"""
test_harness_contract.py — verifies the e2e harness itself (route manifest,
safety fixture) before any live browser/API test depends on it.

Does not require RUN_LIVE_E2E or live credentials.
"""
from __future__ import annotations

from .screen_manifest import AUTHENTICATED_SCREENS


def test_manifest_covers_every_authenticated_route():
    paths = {item.path for item in AUTHENTICATED_SCREENS}
    assert len(paths) == 20
    assert {"/dashboard", "/agents", "/jobs", "/resume", "/email", "/settings"} <= paths


def test_live_writes_are_disabled_by_default(live_safety):
    assert live_safety.allow_external_writes is False
