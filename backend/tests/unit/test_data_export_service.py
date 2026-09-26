import json
import zipfile
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.db import User
from app.services.data_export_service import build_user_data_export


def _empty_execute_result():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


@pytest.mark.asyncio
async def test_export_contains_profile_and_readme_but_not_encrypted_columns():
    user = User(
        id=uuid4(),
        email="export-test@example.com",
        full_name="Export Test",
        linkedin_email_enc="should-never-appear",
        linkedin_password_enc="should-never-appear",
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute_result())

    archive = await build_user_data_export(db, user)

    with zipfile.ZipFile(BytesIO(archive)) as zf:
        names = zf.namelist()
        assert "profile.json" in names
        assert "README.txt" in names

        profile = json.loads(zf.read("profile.json"))
        assert profile["email"] == "export-test@example.com"
        assert "linkedin_email_enc" not in profile
        assert "linkedin_password_enc" not in profile

        readme = zf.read("README.txt").decode()
        assert "LinkedIn" in readme


@pytest.mark.asyncio
async def test_export_skips_tables_with_no_rows_for_this_user():
    user = User(id=uuid4(), email="empty-tables@example.com")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute_result())

    archive = await build_user_data_export(db, user)

    with zipfile.ZipFile(BytesIO(archive)) as zf:
        names = zf.namelist()
        # Only the always-present files — no table produced any rows.
        assert set(names) == {"profile.json", "README.txt"}
