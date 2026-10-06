"""POST /jobs/applications/export-sheet: CSV -> Drive (converted to a Sheet)."""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1 import jobs
from app.services import drive_service
from app.services.drive_service import DriveError

SHEET = "application/vnd.google-apps.spreadsheet"


def _row(**kw):
    base = {
        "company": "Acme",
        "role": "=HYPERLINK(1)",
        "location": "Remote",
        "match_score": 88,
        "status": "saved",
        "found_at": datetime(2026, 10, 1, tzinfo=UTC),
        "job_url": "https://x.test/j",
        "source": "greenhouse",
    }
    return SimpleNamespace(**{**base, **kw})


async def _call(monkeypatch, upload):
    monkeypatch.setattr(jobs, "_filtered_applications", AsyncMock(return_value=[_row()]))
    monkeypatch.setattr(drive_service, "upload_to_drive", upload)
    db = MagicMock(commit=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4())
    out = await jobs.export_applications_sheet(
        db=db,
        current_user=user,
        status=None,
        location=None,
        source=None,
        min_match=None,
        found_after=None,
        found_before=None,
        sort=None,
    )
    return out, db


@pytest.mark.asyncio
async def test_export_uploads_csv_as_sheet_and_logs(monkeypatch):
    upload = MagicMock(return_value={"id": "f1", "webViewLink": "https://docs.google.com/s/f1"})
    out, db = await _call(monkeypatch, upload)
    assert out["url"] == "https://docs.google.com/s/f1"
    _, name, content, mime, convert_to = upload.call_args.args
    assert name.startswith("CareerCraft jobs ") and mime == "text/csv" and convert_to == SHEET
    lines = content.decode().split("\r\n")
    assert lines[0].startswith(
        '"Company","Role","Location","Match","Status","Found","URL","Source"'
    )
    assert '"\'=HYPERLINK(1)"' in lines[1]  # formula-injection guard
    assert db.add.call_args.args[0].action == "export_sheet"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_export_drive_not_connected_is_409(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        await _call(monkeypatch, MagicMock(side_effect=DriveError("nope", not_connected=True)))
    assert exc.value.status_code == 409 and exc.value.detail == "google_drive_not_connected"


@pytest.mark.asyncio
async def test_export_rejected_upload_is_not_a_reconnect(monkeypatch):
    """A connected Drive that rejects the upload must not restart the connect flow."""
    with pytest.raises(HTTPException) as exc:
        await _call(
            monkeypatch, MagicMock(side_effect=DriveError("Google Drive rejected the upload"))
        )
    assert exc.value.status_code == 502


def test_upload_to_drive_convert_to_in_metadata(monkeypatch):
    seen = {}

    def fake_proxy(**kw):
        seen["body"] = kw["content"].decode()
        return SimpleNamespace(data={"id": "x"})

    monkeypatch.setattr(drive_service, "proxy_request", fake_proxy)
    drive_service.upload_to_drive("u", "n", b"a,b", "text/csv", convert_to=SHEET)
    meta = seen["body"].split("\r\n\r\n")[1].split("\r\n")[0]
    assert json.loads(meta) == {"name": "n", "mimeType": SHEET}
    drive_service.upload_to_drive("u", "n", b"a,b", "text/csv")
    assert "mimeType" not in seen["body"].split("\r\n\r\n")[1].split("\r\n")[0]
