$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
Push-Location $projectDir
try {
    & .venv/Scripts/python.exe tools/build.py
    if ($LASTEXITCODE) { throw 'Build failed; see test-output logs' }
} finally { Pop-Location }
