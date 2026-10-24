#Requires -Version 7
[CmdletBinding()]
param(
    [int]$Tail = 10
)

$ErrorActionPreference = 'Stop'

Write-Output '== Slots (supervisores) =='
docker ps -a --filter 'label=com.docker.compose.project=hyperius' --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
if ($LASTEXITCODE -ne 0) { throw "docker ps falhou (código $LASTEXITCODE)." }

Write-Output ''
Write-Output '== Containers de job (runners) =='
docker ps -a --filter 'label=hyperius.slot' --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'
if ($LASTEXITCODE -ne 0) { throw "docker ps falhou (código $LASTEXITCODE)." }

$slots = @(docker ps -a --filter 'label=com.docker.compose.project=hyperius' --format '{{.Names}}')
foreach ($slot in $slots | Sort-Object) {
    Write-Output ''
    Write-Output "== Log de $slot (últimas $Tail linhas) =="
    docker logs --tail $Tail $slot 2>&1
}
