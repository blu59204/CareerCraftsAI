"""Real local model validation under the disposable Clerk user; no paid keys."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import fitz
import httpx
from dotenv import dotenv_values

state = json.loads(
    (Path(tempfile.gettempdir()) / "careercraft-agent-a-live.json").read_text()
)
seed = """
import asyncio,json,sys,uuid
from sqlalchemy import select,delete
from app.core.database import AsyncSessionLocal
from app.models.db import UserModelSettings,UserDocument
from app.services.rag_service import ingest_document
async def main():
 data=json.load(sys.stdin)
 async with AsyncSessionLocal() as db:
  uid=uuid.UUID(data['user_id'])
  await db.execute(delete(UserModelSettings).where(UserModelSettings.user_id==uid))
  model=UserModelSettings(user_id=uid,provider='ollama',model_name=data['model'],ollama_url='http://ollama:11434',is_active=True)
  db.add(model)
  existing=(await db.execute(select(UserDocument).where(UserDocument.id==uuid.UUID(data['document_id']),UserDocument.user_id==uid))).scalar_one()
  source=UserDocument(user_id=uid,doc_type='resume',filename='agent-a-source.pdf',storage_path=existing.storage_path,is_primary=True,
   raw_text='# Ada Lovelace\\nada@example.com | London\\n## SUMMARY\\nEngineer building Python services.\\n## EXPERIENCE\\n### Engineer | Example Ltd | London | Jan 2020 - Present\\n- Reduced latency by 30% using Python.\\n## EDUCATION\\n### BSc Computer Science | London University | London | 2019\\n## SKILLS\\nPython, SQL\\n')
  db.add(source);await db.commit()
  await asyncio.to_thread(ingest_document,str(uid),'resume',source.raw_text,{'document_id':str(source.id)},model)
asyncio.run(main())
"""
subprocess.run(
    ["docker", "exec", "-i", "careercraft-local-prod-backend-1", "python", "-c", seed],
    input=json.dumps({**state, "model": os.environ["LOCAL_REVIEW_MODEL"]}),
    text=True,
    check=True,
)
secret = dotenv_values(os.environ["CLERK_ENV_FILE"])["CLERK_SECRET_KEY"]
response = httpx.post(
    f"https://api.clerk.com/v1/sessions/{state['session_id']}/tokens",
    headers={"Authorization": f"Bearer {secret}"},
    json={},
    timeout=30,
)
response.raise_for_status()
client = httpx.Client(
    base_url="http://localhost:18180/api/v1/",
    timeout=180,
    headers={"Authorization": f"Bearer {response.json()['jwt']}"},
)
pdf = fitz.open()
page = pdf.new_page()
page.insert_text(
    (220, 60),
    "Ada Lovelace\nPython Engineer\nSummary\nEngineer building Python services.\nExperience\nEngineer at Example Ltd\nReduced latency by 30% using Python.\nSkills\nPython\nSQL",
    fontsize=11,
)
if os.environ.get("REVIEW_RESUME_ONLY"):
    linkedin = json.loads(
        (Path(tempfile.gettempdir()) / "agent-a-linked-in-result.json").read_text()
    )
else:
    response = client.post(
        "linkedin/profile/optimize",
        data={"target_role": "Python Engineer"},
        files={"file": ("profile.pdf", pdf.tobytes(), "application/pdf")},
    )
    print("LinkedIn status:", response.status_code, flush=True)
    if response.status_code != 200:
        print(response.text[:500], flush=True)
    response.raise_for_status()
    linkedin = response.json()
assert linkedin["status"] == "completed"
assert len(linkedin["sections"]) == 4
assert all(
    edit["source_quotes"]
    for edit in linkedin["sections"]
    if edit["before"] and edit["after"]
)
response = client.post(
    "resume/optimize",
    json={
        "jd_text": "Python Engineer. Build reliable Python services using SQL.",
        "template": "modern",
        "page_target": 1,
    },
)
print("Resume status:", response.status_code, flush=True)
if response.status_code != 200:
    print(response.text[:500], flush=True)
response.raise_for_status()
resume = response.json()
assert resume["status"] == "awaiting_approval" and resume["pdf_document_id"], {
    "status": resume["status"],
    "warnings": resume.get("warnings"),
}
audit = """
import asyncio,json,sys,uuid
from sqlalchemy import select
from app.models.db import AgentRun
from app.core.database import AsyncSessionLocal
async def main():
 ids=json.load(sys.stdin)
 async with AsyncSessionLocal() as db:
  rows=(await db.execute(select(AgentRun).where(AgentRun.id.in_([uuid.UUID(i) for i in ids])))).scalars().all()
  assert len(rows)==2 and all(r.tokens_used>0 and r.duration_ms>0 and r.completed_at for r in rows)
  print(json.dumps([{'agent':r.agent_type,'status':r.status,'tokens':r.tokens_used,'duration_ms':r.duration_ms} for r in rows]))
asyncio.run(main())
"""
rows = subprocess.run(
    ["docker", "exec", "-i", "careercraft-local-prod-backend-1", "python", "-c", audit],
    input=json.dumps([linkedin["run_id"], resume["run_id"]]),
    text=True,
    capture_output=True,
    check=True,
)
result = {
    "checks": [
        "Real configured local model: LinkedIn before/after edits with supporting quotes",
        "Real configured local model: resume generation retains approval state",
        "Both runs persisted with positive token usage and terminal timestamps",
    ],
    "runs": json.loads(rows.stdout),
}
Path(__file__).with_name("model-results.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
