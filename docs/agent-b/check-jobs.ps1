$ErrorActionPreference='Stop'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$containerName='careercraft-b-jobs-migration-check'
function Invoke-CheckedDocker { & docker @args; if($LASTEXITCODE -ne 0){throw "Docker check failed: $($args[0])"} }
Invoke-CheckedDocker run --rm --detach --name $containerName --network none --env POSTGRES_HOST_AUTH_METHOD=trust pgvector/pgvector:pg16 | Out-Null
try {
  for($i=0;$i -lt 20;$i++){ & docker exec $containerName pg_isready -U postgres 2>$null | Out-Null; if($LASTEXITCODE -eq 0){break}; Start-Sleep -Seconds 1 }
  $scripts=@('backend/tests/fixtures/b_jobs_setup.sql',
    'supabase/migrations/20261001090000_b_job_search_defaults.sql',
    'supabase/migrations/20261001091000_b_job_catalog.sql',
    'supabase/migrations/20261001092000_b_github_profiles.sql',
    'backend/tests/fixtures/b_jobs_check.sql',
    'docs/agent-b/rollback/b_github_profiles.sql',
    'docs/agent-b/rollback/b_job_catalog.sql',
    'docs/agent-b/rollback/b_job_search_defaults.sql',
    'backend/tests/fixtures/b_jobs_rollback_check.sql')
  foreach($script in $scripts){Invoke-CheckedDocker cp (Join-Path $repoRoot $script) "${containerName}:/tmp/check.sql"; Invoke-CheckedDocker exec $containerName psql -U postgres -v ON_ERROR_STOP=1 -f /tmp/check.sql}
  Write-Output 'Jobs/GitHub migrations, RLS, vector indexes, volume query and rollback PASS'
} finally { Invoke-CheckedDocker stop $containerName | Out-Null }
