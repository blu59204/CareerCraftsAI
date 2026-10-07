#!/usr/bin/env bash
# Safe production-check regression: every external command is a local fixture.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixtures=$(mktemp -d)
trap 'rm -rf "$fixtures"' EXIT
cat > "$fixtures/curl" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == *"/internal/"* || "$*" == *"/docs"* ]]; then
  printf 404
else
  printf '{"status":"ok","temporal":{"workers":1}}'
fi
SH
cat > "$fixtures/openssl" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == *x509* ]]; then printf 'notAfter=Jan 1 00:00:00 2035 GMT\n'; else cat >/dev/null; fi
SH
cat > "$fixtures/nc" <<'SH'
#!/usr/bin/env bash
exit 1
SH
cat > "$fixtures/date" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == *-d* ]]; then printf 2000000000; else printf 1800000000; fi
SH
cat > "$fixtures/docker" <<'SH'
#!/usr/bin/env bash
[[ "$*" == *"-p audit-fixture -f /fixture/compose.yml ps --all --format json"* ]] || exit 9
case "$AUDIT_COMPOSE_CASE" in
  error) exit 1 ;;
  empty) exit 0 ;;
  invalid) printf 'bad-json' ;;
  stopped) printf '{"Service":"backend","State":"exited","Health":"healthy"}\n' ;;
  unhealthy) printf '{"Service":"backend","State":"running","Health":"unhealthy"}\n' ;;
  missing) printf '{"Service":"another","State":"running","Health":"healthy"}\n' ;;
  healthy) printf '{"Service":"backend","State":"running","Health":"healthy"}\n' ;;
esac
SH
chmod +x "$fixtures/"*
export PATH="$fixtures:$PATH" APP_ENV=production DOMAIN=fixture.invalid
export APP_SECRET_KEY=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export COMPOSE_PROJECT=audit-fixture COMPOSE_FILE=/fixture/compose.yml REQUIRED_SERVICES=backend
export DATABASE_URL=''
for case in error empty invalid stopped unhealthy missing healthy; do
  export AUDIT_COMPOSE_CASE="$case"
  if bash "$root/scripts/validate_production.sh" >"$fixtures/result" 2>&1; then
    [[ "$case" == healthy ]] || { cat "$fixtures/result"; exit 1; }
  else
    [[ "$case" != healthy ]] || { cat "$fixtures/result"; exit 1; }
  fi
done
printf 'Compose failure, invalid/empty output, stopped/unhealthy/missing services and healthy stack verified.\n'
