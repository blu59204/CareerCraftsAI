"""
test_harness_contract.py — verifies the e2e harness itself (route manifest,
safety fixture) before any live browser/API test depends on it.

Does not require RUN_LIVE_E2E or live credentials.
"""
from __future__ import annotations

import pytest

from .screen_manifest import AUTHENTICATED_SCREENS

# `-m e2e` is how scripts/run_e2e_tests.sh selects the live suite files it
# explicitly runs this file alongside — without this marker these two tests
# are deselected by that filter even though (per conftest.py's
# pytest_collection_modifyitems carve-out for this file, matched on
# fspath) they never require live credentials or a running backend/browser.
# The marker (pytest -m selection) and the credential-gating carve-out are
# orthogonal: the marker only affects which tests `-m e2e` selects, while
# the carve-out only affects whether the missing-creds skip marker gets
# added. Adding pytest.mark.e2e here does not make these tests require
# credentials.
pytestmark = pytest.mark.e2e


def test_manifest_covers_every_authenticated_route():
    paths = {item.path for item in AUTHENTICATED_SCREENS}
    assert len(paths) == 20
    assert {"/dashboard", "/agents", "/jobs", "/resume", "/email", "/settings"} <= paths


def test_live_writes_are_disabled_by_default(live_safety):
    assert live_safety.allow_external_writes is False
