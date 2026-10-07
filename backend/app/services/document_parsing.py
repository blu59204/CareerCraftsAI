"""Verified formats and bounded, isolated document text extraction."""

import io
import subprocess
import sys
import zipfile

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_XML_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 1_000_000


def sniff_content_type(content: bytes) -> str | None:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                names = {e.filename for e in entries}
                if not {"[Content_Types].xml", "word/document.xml", "_rels/.rels"} <= names:
                    return None
                if len(entries) > 512 or len(names) != len(entries):
                    return None
                if sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                    return None
                for entry in entries:
                    if entry.flag_bits & 1 or entry.file_size > MAX_ARCHIVE_BYTES:
                        return None
                    if entry.file_size > max(1, entry.compress_size) * 100:
                        return None
                    if entry.filename.endswith(".xml"):
                        if entry.file_size > MAX_XML_BYTES:
                            return None
                        xml = archive.read(entry)
                        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                            return None
                if b"wordprocessingml.document.main+xml" not in archive.read("[Content_Types].xml"):
                    return None
                return DOCX
        except (ValueError, OSError, zipfile.BadZipFile, RuntimeError):
            return None
    if (
        content.startswith((b"MZ", b"\x7fELF", b"\xff\xd8\xff", b"\x89PNG", b"GIF8"))
        or b"\x00" in content
    ):
        return None
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return "text/plain"


def extract_verified_text(content: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        import fitz

        with fitz.open(stream=content, filetype="pdf") as document:
            if document.page_count > 200:
                raise ValueError("Too many PDF pages")
            parts = []
            size = 0
            for page in document:
                value = page.get_text()
                size += len(value)
                if size > MAX_TEXT_CHARS:
                    raise ValueError("Too much extracted text")
                parts.append(value)
            return "\n".join(parts)
    if content_type == DOCX:
        from docx import Document

        value = "\n".join(p.text for p in Document(io.BytesIO(content)).paragraphs)
    elif content_type == "text/plain":
        value = content.decode("utf-8")
    else:
        raise ValueError("Unsupported document format")
    if len(value) > MAX_TEXT_CHARS:
        raise ValueError("Too much extracted text")
    return value


def parse_isolated(content: bytes, content_type: str) -> str:
    # A timeout actually terminates the parser, unlike cancelling a thread.
    result = subprocess.run(  # noqa: S603 — fixed executable/module, no shell
        [sys.executable, "-m", "app.services.document_parsing", content_type],
        input=content,
        capture_output=True,
        timeout=20,
        check=True,
    )
    return result.stdout.decode("utf-8")


if __name__ == "__main__":
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    payload = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
    if len(payload) > 10 * 1024 * 1024 or sniff_content_type(payload) != sys.argv[1]:
        raise ValueError("Invalid document")
    sys.stdout.buffer.write(extract_verified_text(payload, sys.argv[1]).encode("utf-8"))
