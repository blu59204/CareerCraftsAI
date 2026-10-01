"""Run inside the local backend with LibreOffice installed; synthetic data only."""

import json
import subprocess
import tempfile
from pathlib import Path

import fitz
from app.services.resume_export import PageOverflow, fit_resume, generate_resume_docx

results = []
with tempfile.TemporaryDirectory(prefix="agent-a-render-") as temp:
    root = Path(temp)
    for template in ("modern", "classic", "technical"):
        for target in (1, 2):
            for count in (2, 15, 30, 45, 65):
                text = (
                    "# Ada Lovelace\nada@example.com | London\n## SUMMARY\n"
                    "Engineer delivering reliable Python services.\n## EXPERIENCE\n"
                    "### Engineer | Example Ltd | Jan 2020 - Present\n"
                    + "".join(
                        f"- Delivered project {i} using Python and SQL with verified results.\n"
                        for i in range(count)
                    )
                    + "## EDUCATION\nBSc Computer Science, London University, 2019\n"
                    "## SKILLS\nPython, SQL, C++, C#\n"
                )
                try:
                    layout = fit_resume(text, template=template, page_target=target)
                except PageOverflow:
                    results.append(
                        {
                            "template": template,
                            "target": target,
                            "bullets": count,
                            "overflow": True,
                        }
                    )
                    continue
                path = root / f"{template}-{target}-{count}.docx"
                path.write_bytes(generate_resume_docx(layout))
                subprocess.run(
                    [
                        "libreoffice",
                        "-env:UserInstallation=file://" + str(root / "profile"),
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(root),
                        str(path),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                with fitz.open(path.with_suffix(".pdf")) as rendered:
                    extracted = "\n".join(page.get_text() for page in rendered)
                    assert all(
                        value in extracted
                        for value in (
                            "ada@example.com",
                            "Example Ltd",
                            "Jan 2020",
                            "2019",
                            "C++",
                            "C#",
                        )
                    )
                    assert all(f"project {i} " in extracted for i in range(count))
                    assert (
                        extracted.index("SUMMARY")
                        < extracted.index("EXPERIENCE")
                        < extracted.index("EDUCATION")
                        < extracted.index("SKILLS")
                    )
                    results.append(
                        {
                            "template": template,
                            "target": target,
                            "bullets": count,
                            "pdf_pages": layout.page_count,
                            "docx_pages": len(rendered),
                            "font": layout.theme.body_size,
                        }
                    )
    print(json.dumps(results, indent=2))
    assert all(
        row.get("docx_pages", 0) <= row["target"] for row in results
    ), "DOCX exceeded page target"
