"""Fail without printing values when staged files contain local configured secrets."""
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
values = []
for relative in ("backend/.env", "frontend/.env.local", "worker/.env"):
    for key, value in dotenv_values(root / relative).items():
        if value and len(value) >= 20 and any(part in key for part in ("SECRET", "PASSWORD", "SERVICE_KEY", "API_KEY", "DATABASE_URL")):
            values.append(value.encode())
names = subprocess.check_output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]).decode().split("\0")
bad = []
for name in filter(None, names):
    blob = subprocess.check_output(["git", "show", f":{name}"])
    if any(value in blob for value in values) or re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", blob):
        bad.append(name)
if bad:
    raise SystemExit("Potential secrets in staged files: " + ", ".join(bad))
print(f"Checked {len([n for n in names if n])} staged files; no configured private secrets or private keys found")
