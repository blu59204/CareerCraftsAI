import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.rag import MAX_SIZE_BYTES, _read_bounded
from app.services.document_parsing import parse_isolated, sniff_content_type


def _archive(body, content_type=True):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", body)
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr(
            "[Content_Types].xml",
            "wordprocessingml.document.main+xml" if content_type else "invalid",
        )
    return output.getvalue()


def test_expansion_and_entity_documents_rejected():
    assert sniff_content_type(_archive("a" * 1_000_000)) is None
    assert sniff_content_type(_archive('<!DOCTYPE x [<!ENTITY x "boom">]><x/>')) is None
    assert sniff_content_type(_archive("<document/>", False)) is None


def test_arbitrary_zip_is_not_docx():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("resume.txt", "Hello")
    assert sniff_content_type(output.getvalue()) is None


def test_verified_content_controls_isolated_parser():
    # A filename never enters parser selection.
    assert parse_isolated(b"Hello resume", "text/plain") == "Hello resume"
    with pytest.raises(Exception):
        parse_isolated(b"Hello resume", "application/pdf")


@pytest.mark.asyncio
async def test_upload_reads_only_limit_plus_one():
    stream = io.BytesIO(b"a" * (MAX_SIZE_BYTES + 500_000))
    with pytest.raises(HTTPException) as error:
        await _read_bounded(UploadFile(stream))
    assert error.value.status_code == 413
    assert stream.tell() == MAX_SIZE_BYTES + 1
