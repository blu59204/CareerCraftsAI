"""Transfer selected application settings over SSH without printing secrets.

Run locally with NGROK_AUTHTOKEN in the environment. Writes only a new dedicated
remote directory and never touches existing ngrok or application configuration.
"""
import json
import os
import secrets
import subprocess
from pathlib import Path

from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parents[1]
    backend = dict(dotenv_values(root / "backend" / ".env"))
    frontend = dict(dotenv_values(root / "frontend" / ".env.local"))
    keys = {
        "APP_SECRET_KEY", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_JWT_SECRET",
        "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "HUNTER_API_KEY", "EXA_API_KEY",
        "PROXYCURL_API_KEY", "RESEND_API_KEY", "YOUTUBE_API_KEY", "TAVILY_API_KEY", "BRAVE_API_KEY",
    }
    values = {k: backend[k] for k in keys if backend.get(k)}
    required = {"APP_SECRET_KEY", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_JWT_SECRET"}
    if required - values.keys():
        raise SystemExit("Missing required backend configuration")
    redis_password = secrets.token_urlsafe(32)
    sandbox_key = secrets.token_urlsafe(32)
    values.update({
        "APP_ENV": "production", "LOG_LEVEL": "INFO",
        "REDIS_URL": f"redis://:{redis_password}@127.0.0.1:18179/0", "REDIS_PASSWORD": redis_password,
        "INTERNAL_SECRET": secrets.token_urlsafe(32), "BACKEND_INTERNAL_URL": "http://127.0.0.1:18100",
        "OPEN_SANDBOX_URL": "http://127.0.0.1:18190", "OPEN_SANDBOX_API_KEY": sandbox_key,
        "OPEN_SANDBOX_CHROME_IMAGE": "careercraft-browser:1", "SANDBOX_MAX_ACTIVE": "1",
        "WORKFLOW_WORKER_CONCURRENCY": "1", "WORKFLOW_TASK_TIMEOUT_S": "300",
        "SANDBOX_ALLOWED_DOMAINS": "boards.greenhouse.io,job-boards.greenhouse.io,*.greenhouse.io,jobs.lever.co,*.lever.co,www.linkedin.com,*.linkedin.com,*.licdn.com,www.naukri.com,*.naukri.com,*.naukimg.com,accounts.google.com,*.gstatic.com,*.googleusercontent.com",
    })
    public = {
        "NEXT_PUBLIC_SUPABASE_URL": frontend.get("NEXT_PUBLIC_SUPABASE_URL") or values["SUPABASE_URL"],
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": frontend.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""),
    }
    if not public["NEXT_PUBLIC_SUPABASE_ANON_KEY"]:
        raise SystemExit("Missing frontend Supabase publishable key")
    token = os.environ["NGROK_AUTHTOKEN"].strip()
    payload = {"backend": values, "public": public, "redis": redis_password, "sandbox": sandbox_key, "ngrok": token}
    # Payload travels via encrypted stdin, not command arguments or output.
    remote = """import sys,json,pathlib,os
d=json.load(sys.stdin)
p=pathlib.Path('/opt/careercraft-secrets')
p.mkdir(mode=0o700,exist_ok=False)
# redis:8-alpine drops privileges to uid 999/gid 1000, and compose bind-mounts
# redis.conf read-only, so the image entrypoint cannot chown/chmod it itself.
# Left root-owned, redis exits with "Fatal error, can't open config file"
# and the scheduler crash-loops behind it. Mode stays 0600 and only the owner
# changes, so requirepass remains unreadable to every other user on the host.
REDIS_OWNER=(999,1000)
def put(name,content,owner=None):
 f=p/name; f.write_text(content); f.chmod(0o600)
 if owner: os.chown(f,owner[0],owner[1])
def env(v): return ''.join(k+'='+json.dumps(str(value))+'\\n' for k,value in v.items())
put('backend.env',env(d['backend']))
put('public.env',env(d['public']))
put('sandbox.env',env({'OPENSANDBOX_SERVER_API_KEY':d['sandbox']}))
put('redis.conf','bind 127.0.0.1\\nport 18179\\nrequirepass '+d['redis']+'\\nappendonly yes\\ndir /data\\nmaxmemory 256mb\\nmaxmemory-policy noeviction\\n',REDIS_OWNER)
put('ngrok.yml','version: 3\\nagent:\\n  authtoken: '+d['ngrok']+'\\n  web_addr: 127.0.0.1:14041\\n  log: stdout\\n  log_format: json\\nendpoints:\\n  - name: careercraft\\n    upstream:\\n      url: http://127.0.0.1:18180\\n')
print('Dedicated CareerCraft secrets installed; values suppressed')
"""
    import base64
    encoded = base64.b64encode(remote.encode()).decode()
    command = f"sudo -n python3 -c \"import base64;exec(base64.b64decode('{encoded}'))\""
    subprocess.run(["ssh", "oraclevm", command], input=json.dumps(payload), text=True, check=True)


if __name__ == "__main__":
    main()
