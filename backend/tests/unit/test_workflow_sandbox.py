"""Every workflow must load inside Temporal's workflow sandbox.

The sandbox re-imports each workflow module with restricted builtins, so any
module-level import that touches the filesystem (pydantic-settings reading
.env via Path.expanduser, for one) makes the worker refuse to start with
"Failed validating workflow ...". These tests run the same validation the
Worker constructor runs, without a Temporal server.
"""

import pytest

temporalio = pytest.importorskip("temporalio")

from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner  # noqa: E402

from app.workflows.notification_registry import (  # noqa: E402
    NOTIFICATION_WORKFLOWS,
)
from app.workflows.registry import WORKFLOWS  # noqa: E402


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "workflow_cls",
    [*WORKFLOWS, *NOTIFICATION_WORKFLOWS],
    ids=lambda cls: cls.__name__,
)
async def test_workflow_passes_sandbox_validation(workflow_cls, tmp_path, monkeypatch):
    # A real .env next to the process, as on the servers: this is what
    # pydantic-settings tries to open when config is imported unsandboxed.
    (tmp_path / ".env").write_text("APP_ENV=test\n")
    monkeypatch.chdir(tmp_path)
    from temporalio.workflow import _Definition

    defn = _Definition.must_from_class(workflow_cls)
    SandboxedWorkflowRunner().prepare_workflow(defn)
