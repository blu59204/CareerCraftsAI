"""Run GitHub CLI using the configured Git credential helper, without logging credentials."""
import os
import subprocess
import sys


def main():
    result = subprocess.run(
        ["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
        text=True, capture_output=True,
    )
    if result.returncode:
        raise SystemExit("No GitHub credential available through Git credential helper")
    credential = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    token = credential.get("password")
    if not token:
        raise SystemExit("Git credential helper returned no token")
    env = {**os.environ, "GH_TOKEN": token}
    cli = os.environ.get("GH_EXECUTABLE", "gh")
    raise SystemExit(subprocess.run([cli, *sys.argv[1:]], env=env).returncode)


if __name__ == "__main__":
    main()
