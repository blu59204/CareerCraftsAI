"""Authenticated local API proof. Credentials stay in OS temp, never in artifacts.

Requires a disposable Clerk session in careercraft-agent-a-live.json (OS temp),
CLERK_ENV_FILE pointing to a local dotenv file, and the Agent A local container.
Creates only synthetic resume rows under that disposable account.
"""

import concurrent.futures
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile

import fitz
import httpx
from docx import Document
from dotenv import dotenv_values

STATE = Path(tempfile.gettempdir()) / "careercraft-agent-a-live.json"
state = json.loads(STATE.read_text(encoding="utf-8"))
secret = dotenv_values(os.environ["CLERK_ENV_FILE"])["CLERK_SECRET_KEY"]
api = "http://localhost:18180/api/v1"
checks = []


def token():
    response = httpx.post(
        f"https://api.clerk.com/v1/sessions/{state['session_id']}/tokens",
        json={},
        headers={"Authorization": f"Bearer {secret}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["jwt"]


client = httpx.Client(headers={"Authorization": f"Bearer {token()}"}, timeout=60)
response = client.get(f"{api}/users/me")
assert response.status_code == 200
state["user_id"] = response.json()["id"]
assert client.post(f"{api}/users/me/consent").status_code == 200
checks.append("Clerk session verified; disposable user provisioned and consent recorded")

source = """# Agent A Review
review@example.com | London
## SUMMARY
Engineer building reliable Python services.
## EXPERIENCE
### Engineer | Example Ltd | London | Jan 2020 - Present
- Built Python services.
## SKILLS
Python, SQL, C++, C#
"""
seed = """
import asyncio,json,sys,uuid
from app.core.database import AsyncSessionLocal
from app.models.db import UserDocument
from app.services.resume_export import fit_resume
from app.services.storage_service import upload_file
data=json.load(sys.stdin)
async def main():
 async with AsyncSessionLocal() as db:
  layout=fit_resume(data['text'])
  path=upload_file(data['user_id'],'resume.pdf',layout.pdf,'application/pdf')
  doc=UserDocument(user_id=uuid.UUID(data['user_id']),doc_type='resume_tailored',
   filename='resume.pdf',storage_path=path,raw_text=data['text'],ats_score=70,
   ats_data={'template':'modern','page_target':2})
  db.add(doc);await db.commit();print("AGENT_A_DOCUMENT_ID="+str(doc.id))
asyncio.run(main())
"""
result = subprocess.run(
    ["docker", "exec", "-i", "careercraft-local-prod-backend-1", "python", "-c", seed],
    input=json.dumps({"user_id": state["user_id"], "text": source}),
    text=True,
    capture_output=True,
    check=True,
)
document_id = next(
    line.split("=", 1)[1]
    for line in result.stdout.splitlines()
    if line.startswith("AGENT_A_DOCUMENT_ID=")
)
state["document_id"] = document_id
STATE.write_text(json.dumps(state), encoding="utf-8")
path = f"{api}/resume/tailored/{document_id}"
before = client.get(path).json()
edited = source.replace(
    "- Built Python services.", "- Reduced latency by 30% using Python and SQL."
)
edited += "\n## EDUCATION\nBSc Computing, Example University, 2019\n"
response = client.post(
    path + "/fix",
    json={
        "resume_markdown": edited,
        "expected_version": before["content_version"],
        "remember": False,
    },
)
assert response.status_code == 200, response.status_code
saved = response.json()
assert saved["content_version"] != before["content_version"]
assert saved["ats_score"] != before["ats_score"]
assert client.get(path).json()["resume_markdown"] == saved["resume_markdown"]
checks.append("Edit/save/reload persists new text and recomputes general score")


def race(suffix):
    return client.post(
        path + "/fix",
        json={
            "resume_markdown": saved["resume_markdown"] + suffix,
            "expected_version": saved["content_version"],
            "remember": False,
        },
    )


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    replies = list(pool.map(race, ["\nProject: Alpha\n", "\nProject: Beta\n"]))
assert sorted(reply.status_code for reply in replies) == [200, 409]
current = client.get(path).json()
assert current["resume_markdown"] in [
    reply.json()["resume_markdown"] for reply in replies if reply.status_code == 200
]
checks.append("Concurrent full-text edits: one commit and one 409; winner survives reload")
response = client.post(
    path + "/fix",
    json={
        "resume_markdown": edited + "\n- Critical evidence from a long project.\n" * 250,
        "expected_version": current["content_version"],
        "page_target": 1,
        "remember": False,
    },
)
assert response.status_code == 422
assert client.get(path).json()["content_version"] == current["content_version"]
checks.append("Overflow save fails safely and leaves previous version intact")

scores = []
for target in ("", "Senior Engineer\nRequired: Python SQL AWS"):
    payload = {"document_id": document_id, "jd_text": target}
    one = client.post(f"{api}/resume/ats-score", json=payload)
    two = client.post(f"{api}/resume/ats-score", json=payload)
    assert one.status_code == two.status_code == 200 and one.json() == two.json()
    scores.append(one.json())
assert scores[0]["estimate"]["mode"] == "general"
assert scores[1]["estimate"]["mode"] == "target_job"
assert "aws" in scores[1]["missing_keywords"]
checks.append("General/per-job scores deterministic and bound to saved content")

for template in ("modern", "classic", "technical"):
    client.headers["Authorization"] = f"Bearer {token()}"
    response = client.post(
        path + "/fix",
        json={
            "template": template,
            "expected_version": current["content_version"],
            "remember": False,
        },
    )
    assert response.status_code == 200
    current = response.json()
    for pages in (1, 2):
        for fmt in ("pdf", "docx"):
            response = client.get(
                f"{api}/resume/download/{document_id}",
                params={"format": fmt, "pages": pages},
            )
            assert response.status_code == 200, (fmt, pages, response.status_code)
            if fmt == "pdf":
                with fitz.open(stream=response.content, filetype="pdf") as pdf:
                    assert len(pdf) <= pages
                    text = "\n".join(page.get_text() for page in pdf)
            else:
                text = "\n".join(p.text for p in Document(io.BytesIO(response.content)).paragraphs)
            for field in (
                "review@example.com",
                "Example Ltd",
                "Jan 2020",
                "30%",
                "C++",
                "C#",
                "EDUCATION",
            ):
                assert field in text
checks.append("Authenticated PDF/DOCX round trips: three templates, both page targets")

client.headers["Authorization"] = f"Bearer {token()}"
for filename, data, mime, expected in (
    ("bad.txt", b"bad", "text/plain", 415),
    ("broken.pdf", b"%PDF- broken", "application/pdf", 422),
    ("large.pdf", b"x" * (5 * 1024 * 1024 + 1), "application/pdf", 413),
):
    response = client.post(
        f"{api}/linkedin/profile/optimize",
        data={"target_role": "Engineer"},
        files={"file": (filename, data, mime)},
    )
    assert response.status_code == expected, response.status_code
with fitz.open() as pdf:
    pdf.new_page()
    response = client.post(
        f"{api}/linkedin/profile/optimize",
        data={"target_role": "Engineer"},
        files={"file": ("scan.pdf", pdf.tobytes(), "application/pdf")},
    )
    assert response.status_code == 422
checks.append("Authenticated LinkedIn wrong-type/malformed/oversized/image-only rejection")

with fitz.open() as pdf:
    page = pdf.new_page()
    page.insert_text(
        (260, 40),
        "Agent A Review\nEngineer\nSummary\nI build reliable Python services for customers.\nExperience\nEngineer at Example Ltd\nReduced latency by 30%.",
    )
    response = client.post(
        f"{api}/linkedin/profile/optimize",
        data={"target_role": "Engineer"},
        files={"file": ("profile.pdf", pdf.tobytes(), "application/pdf")},
    )
    assert response.status_code == 400 and "No active model" in response.text
checks.append("Valid LinkedIn PDF reaches gateway; missing model returns safe 400")

admin = httpx.Client(
    base_url="https://api.clerk.com/v1/",
    headers={"Authorization": f"Bearer {secret}"},
    timeout=30,
)
other_response = admin.post(
    "users",
    json={
        "email_address": ["agent-a-review-other-" + document_id[:8] + "@example.com"],
        "skip_password_requirement": True,
    },
)
other_response.raise_for_status()
state["other_clerk_user_id"] = other_response.json()["id"]
STATE.write_text(json.dumps(state), encoding="utf-8")
other_response = admin.post("sessions", json={"user_id": state["other_clerk_user_id"]})
other_response.raise_for_status()
other_response = admin.post(f"sessions/{other_response.json()['id']}/tokens", json={})
other_response.raise_for_status()
other = httpx.Client(
    headers={"Authorization": f"Bearer {other_response.json()['jwt']}"}, timeout=30
)
assert other.get(f"{api}/users/me").status_code == 200
assert other.post(f"{api}/users/me/consent").status_code == 200
for endpoint in (path, f"{api}/resume/download/{document_id}"):
    assert other.get(endpoint).status_code == 404
assert other.post(path + "/fix", json={"resume_markdown": edited}).status_code == 404
assert other.post(f"{api}/resume/ats-score", json={"document_id": document_id}).status_code == 404
checks.append("Second real Clerk user cannot read/edit/score/download the first user's resume")
print(json.dumps({"checks": checks, "count": len(checks)}, indent=2))
