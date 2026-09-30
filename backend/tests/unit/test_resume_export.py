import io
import zipfile

import fitz
import pytest
from docx import Document

from app.services.resume_export import PageOverflow, fit_resume, generate_resume_docx

TEXT = """# Ada Lovelace
ada@example.com | London
## SUMMARY
Engineer delivering reliable applications.
## EXPERIENCE
### Senior Engineer | Example Ltd | London | Jan 2020 - Present
- Reduced latency by 30% using Python and SQL.
## EDUCATION
BSc Computer Science, London University, 2019
## SKILLS
Python, C++, C#, SQL
"""


@pytest.mark.parametrize("template", ["modern", "classic", "technical"])
@pytest.mark.parametrize("pages", [1, 2])
def test_pdf_docx_roundtrip_preserves_fields_order_and_safe_structure(template, pages):
    layout = fit_resume(TEXT, template=template, page_target=pages)
    with fitz.open(stream=layout.pdf, filetype="pdf") as pdf:
        assert len(pdf) <= pages
        extracted = "\n".join(page.get_text() for page in pdf)
        assert all(not page.get_images() for page in pdf)
        assert all(
            span["size"] >= 10
            for page in pdf
            for block in page.get_text("dict")["blocks"]
            if "lines" in block
            for line in block["lines"]
            for span in line["spans"]
        )
    data = generate_resume_docx(layout)
    docx = Document(io.BytesIO(data))
    doc_text = "\n".join(p.text for p in docx.paragraphs)
    for text in (extracted, doc_text):
        for value in ("ada@example.com", "Example Ltd", "Jan 2020", "Present", "30%", "C++", "C#"):
            assert value in text
        assert (
            text.index("SUMMARY")
            < text.index("EXPERIENCE")
            < text.index("EDUCATION")
            < text.index("SKILLS")
        )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml")
        assert b"<w:tbl" not in xml and b"<w:txbxContent" not in xml and b"<w:drawing" not in xml


def test_irreducible_overflow_does_not_silently_drop_content():
    text = TEXT + "\n" + "- Delivered an important project with critical evidence.\n" * 200
    with pytest.raises(PageOverflow, match="have not been removed"):
        fit_resume(text, page_target=1)
