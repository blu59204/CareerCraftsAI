"""Run as root on Oracle for the dedicated CareerCraft deployment only."""
import json
from pathlib import Path
import subprocess
import urllib.request

directory = Path("/opt/careercraft-secrets")
if not directory.is_dir():
    raise SystemExit("Dedicated secret directory is missing")
with urllib.request.urlopen("http://127.0.0.1:14041/api/tunnels", timeout=10) as response:
    tunnels = json.load(response)["tunnels"]
origin = next(t["public_url"] for t in tunnels if t["proto"] == "https")
path = directory / "backend.env"
lines = [line for line in path.read_text().splitlines() if not line.startswith(("FRONTEND_URL=", "CORS_ORIGINS=", "ALLOWED_ORIGINS=", "NEXT_PUBLIC_APP_URL="))]
for key in ("FRONTEND_URL", "CORS_ORIGINS", "ALLOWED_ORIGINS", "NEXT_PUBLIC_APP_URL"):
    lines.append(f"{key}={json.dumps(origin)}")
path.write_text("\n".join(lines) + "\n")
path.chmod(0o600)
# Redis runs unprivileged and needs to read only this single mounted config.
(directory / "redis.conf").chmod(0o644)
unit = Path("/etc/systemd/system/careercraft-ngrok.service")
unit.write_text("""[Unit]
Description=CareerCraft isolated ngrok tunnel
After=network-online.target
Wants=network-online.target
[Service]
ExecStart=/usr/local/bin/ngrok http http://127.0.0.1:18180 --config /opt/careercraft-secrets/ngrok.yml
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
""")
subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(["systemctl", "enable", "careercraft-ngrok.service"], check=True)
print("Configured CareerCraft public origin and its dedicated tunnel unit:", origin)
