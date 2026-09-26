"""Builds the self-service ZIP export of everything CareerCraft AI stores
for one user — the DPDP Act, 2023 "right to access" fulfilled without a
manual support request."""

import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.models.db import User


def _json_safe(value: object) -> object:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _row_to_dict(instance: object) -> dict:
    mapper = sa_inspect(instance).mapper
    return {
        column.name: _json_safe(getattr(instance, column.name))
        for column in mapper.columns
        # Columns ending in `_enc` hold encrypted secrets (API keys, LinkedIn
        # sign-in credentials, stored OAuth state) — credentials for acting on
        # the user's behalf, not informational data about them. Decrypting
        # them into a plaintext archive would be a bigger exposure than any
        # duty to include them.
        if not column.name.endswith("_enc")
    }


async def build_user_data_export(db: AsyncSession, user: User) -> bytes:
    """Collect every stored record tied to this user into a ZIP of JSON files,
    one file per table, plus a README explaining what's excluded and why."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("profile.json", json.dumps(_row_to_dict(user), indent=2))

        for mapper in Base.registry.mappers:
            model = mapper.class_
            if model is User or not hasattr(model, "user_id"):
                continue
            result = await db.execute(select(model).where(model.user_id == user.id))
            rows = [_row_to_dict(row) for row in result.scalars().all()]
            if rows:
                zf.writestr(f"{model.__tablename__}.json", json.dumps(rows, indent=2))

        zf.writestr(
            "README.txt",
            "This archive contains every record CareerCraft AI stores that is tied to "
            "your account, as one JSON file per table, plus your profile.\n\n"
            "Not included: your AI provider API key(s) and, if saved, your LinkedIn "
            "sign-in credentials. Those are encrypted secrets used to act on your "
            "behalf, not informational data about you, so they're deliberately left "
            "out of a plaintext export. You can review, rotate, or delete them from "
            "Settings at any time.\n",
        )

    return buffer.getvalue()
