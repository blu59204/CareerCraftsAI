"""Retired server browser execution cannot fill or submit an application.

These local tests replace integration-gated tests of removed browser helpers.
The paired extension's review gates are covered by the extension suites.
"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("portal", ["naukri", "linkedin", "greenhouse"])
async def test_retired_server_execution_rejects_any_application_task(portal):
    from app.services.browser_control_service import run_browser_task

    llm = MagicMock()
    with pytest.raises(RuntimeError, match="paired browser extension"):
        await run_browser_task(llm, f"Submit an application at {portal}", "owner")
    llm.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_retry_wrapper_does_not_revive_server_execution():
    from app.services.browser_control_service import run_browser_task_with_captcha_retry

    with pytest.raises(RuntimeError, match="paired browser extension"):
        await run_browser_task_with_captcha_retry(MagicMock(), "Apply at Naukri", "owner")
