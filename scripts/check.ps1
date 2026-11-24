param([switch]$Acceptance)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install requirements-lock.txt first. See README.' }
    & $pythonExe scripts/check_baseline.py
    if ($LASTEXITCODE -ne 0) { throw 'Baseline check failed.' }
    & $pythonExe -m pytest backend/tests tests/integration
    if ($LASTEXITCODE -ne 0) { throw 'Backend or integration tests failed.' }
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    if ($Acceptance) {
        & $pythonExe -m pytest tests/acceptance -m acceptance
        if ($LASTEXITCODE -ne 0) { throw 'Business acceptance failed or has no tests.' }
        & $pythonExe scripts/check_acceptance.py
        if ($LASTEXITCODE -ne 0) { throw 'Final acceptance evidence is incomplete.' }
    } else {
        Write-Output 'Baseline checks passed. P0 business acceptance was NOT run.'
    }
} finally { Pop-Location }
