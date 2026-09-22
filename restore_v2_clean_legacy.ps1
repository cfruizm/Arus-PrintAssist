[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BackupPath,
    [string]$RepoPath = ""
)

$ErrorActionPreference = "Stop"
if ($RepoPath) { $repo=(Resolve-Path $RepoPath).Path } else { $repo=(Get-Location).Path }
if (-not (Test-Path (Join-Path $BackupPath "agent_core_v2_clean"))) { throw "No existe el backup de app\agent_core_v2_clean en $BackupPath" }
if (-not (Test-Path (Join-Path $BackupPath "agent_core_v2_clean_tools"))) { throw "No existe el backup de tools\agent_core_v2_clean en $BackupPath" }
$targetApp=Join-Path $repo "app\agent_core_v2_clean"
$targetTools=Join-Path $repo "tools\agent_core_v2_clean"
if (Test-Path $targetApp) { Remove-Item $targetApp -Recurse -Force }
if (Test-Path $targetTools) { Remove-Item $targetTools -Recurse -Force }
Copy-Item (Join-Path $BackupPath "agent_core_v2_clean") $targetApp -Recurse -Force
Copy-Item (Join-Path $BackupPath "agent_core_v2_clean_tools") $targetTools -Recurse -Force
Write-Host "Restauracion completada desde $BackupPath" -ForegroundColor Green
