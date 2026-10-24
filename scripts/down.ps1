#Requires -Version 7
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot

docker compose --project-directory $root -f (Join-Path $root 'compose.yaml') down
if ($LASTEXITCODE -ne 0) { throw "docker compose down falhou (código $LASTEXITCODE)." }

$jobs = @(docker ps -aq --filter 'label=hyperius.slot')
if ($LASTEXITCODE -ne 0) { throw "docker ps falhou (código $LASTEXITCODE)." }
if ($jobs.Count -gt 0) {
    docker rm -f $jobs
    if ($LASTEXITCODE -ne 0) { throw "docker rm falhou (código $LASTEXITCODE)." }
}
