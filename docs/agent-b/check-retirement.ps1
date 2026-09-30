$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$containerName = 'careercraft-b-retirement-check'

function Invoke-CheckedDocker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker failed: $($args[0])" }
}

# No published ports, network, production credentials or mounted volumes.
Invoke-CheckedDocker run --rm --detach --name $containerName --network none --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine | Out-Null
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        & docker exec $containerName pg_isready -U postgres 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Disposable PostgreSQL did not start' }

    $scripts = @(
        'backend/tests/fixtures/b_retirement_setup.sql',
        'supabase/migrations/20260909180254_durable_agent_workflows.sql',
        'backend/tests/fixtures/b_retirement_seed.sql',
        'supabase/migrations/20260930090000_b_retire_browser_execution.sql',
        'backend/tests/fixtures/b_retirement_check.sql',
        # Applying the retirement again must be idempotent.
        'supabase/migrations/20260930090000_b_retire_browser_execution.sql',
        'docs/agent-b/rollback/b_retire_browser_execution.sql',
        'backend/tests/fixtures/b_retirement_rollback_check.sql'
    )
    foreach ($script in $scripts) {
        $scriptPath = Join-Path $repoRoot $script
        Invoke-CheckedDocker cp $scriptPath "${containerName}:/tmp/check.sql"
        Invoke-CheckedDocker exec $containerName psql -U postgres -v ON_ERROR_STOP=1 -f /tmp/check.sql | Out-Null
    }
    Write-Output 'Retirement apply, repeated apply, rollback, data and RLS checks: PASS'
} finally {
    Invoke-CheckedDocker stop $containerName | Out-Null
}
