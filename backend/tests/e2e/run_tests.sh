#!/usr/bin/env bash
# Compatibility entry point; one maintained runner owns preflight and safety.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "$root/scripts/run_e2e_tests.sh" "$@"
