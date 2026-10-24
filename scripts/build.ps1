#Requires -Version 7
[CmdletBinding()]
param(
    [string]$Image = 'hyperius-runner'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$stamp = (Get-Date).ToString('yyyyMMdd', [cultureinfo]::InvariantCulture)

docker build --pull -t "${Image}:latest" -t "${Image}:${stamp}" (Join-Path $root 'image')
if ($LASTEXITCODE -ne 0) { throw "docker build falhou (código $LASTEXITCODE)." }

$smoke = Join-Path $root 'tests/smoke.sh'
docker run --rm -v "${smoke}:/tmp/smoke.sh:ro" --entrypoint bash "${Image}:latest" -lc 'bash /tmp/smoke.sh'
if ($LASTEXITCODE -ne 0) { throw "O smoke test falhou (código $LASTEXITCODE)." }

Write-Output "Imagem pronta: ${Image}:latest e ${Image}:${stamp}"
