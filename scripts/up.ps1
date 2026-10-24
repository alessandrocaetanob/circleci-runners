#Requires -Version 7
[CmdletBinding()]
param(
    [string]$Image = 'hyperius-runner:latest'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot

foreach ($tool in 'docker', 'op') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "'$tool' não está no PATH."
    }
}

docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) { throw "A imagem $Image não existe. Rode scripts/build.ps1 antes." }

$env:RUNNER_IMAGE = $Image
op run --env-file (Join-Path $root 'runner.env') -- docker compose --project-directory $root -f (Join-Path $root 'compose.yaml') up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up falhou (código $LASTEXITCODE)." }
