"""Read-only Docker sampler; run on the SSH host during verify.py."""

import json
import subprocess
import time

for _ in range(50):
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    print(
        json.dumps(
            {
                "time": time.time(),
                "computers": [
                    row
                    for row in rows
                    if row["Name"].startswith("careercraft-sandbox-computer-")
                ],
                "shared": [
                    row
                    for row in rows
                    if row["Name"].startswith("careercraft-sandbox-")
                    and not row["Name"].startswith("careercraft-sandbox-computer-")
                ],
            }
        ),
        flush=True,
    )
    time.sleep(1)
