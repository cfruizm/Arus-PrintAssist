[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [string]$RepoPath = ""
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    param([string]$Requested)
    if ($Requested) {
        $candidate = (Resolve-Path -LiteralPath $Requested).Path
        if (-not (Test-Path (Join-Path $candidate ".git"))) {
            throw "La ruta indicada no parece ser la raiz del repositorio: $candidate"
        }
        return $candidate
    }

    try {
        $gitRoot = (& git -C $PSScriptRoot rev-parse --show-toplevel 2>$null).Trim()
        if ($gitRoot) { return $gitRoot }
    } catch {}

    $current = (Get-Location).Path
    if (Test-Path (Join-Path $current ".git")) { return $current }
    throw "No pude identificar la raiz del repositorio. Ejecuta este script desde el repositorio o usa -RepoPath 'C:\\ruta\\Arus-PrintAssist'."
}

$repo = Resolve-RepoRoot -Requested $RepoPath
$sourceApp = Join-Path $PSScriptRoot "app\agent_core_v2_clean"
$sourceTools = Join-Path $PSScriptRoot "tools\agent_core_v2_clean"
$targetApp = Join-Path $repo "app\agent_core_v2_clean"
$targetTools = Join-Path $repo "tools\agent_core_v2_clean"

foreach ($required in @($sourceApp,$sourceTools)) {
    if (-not (Test-Path $required)) { throw "Falta contenido del paquete: $required" }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $repo ".backups\v2_clean_$stamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Write-Host "Repositorio: $repo" -ForegroundColor Cyan
Write-Host "Backup:      $backupRoot" -ForegroundColor Cyan
Write-Host "Produccion:  NO se modificara streamlit_app.py ni app/backend.py" -ForegroundColor Green

if (Test-Path $targetApp) {
    Copy-Item $targetApp (Join-Path $backupRoot "agent_core_v2_clean") -Recurse -Force
}
if (Test-Path $targetTools) {
    Copy-Item $targetTools (Join-Path $backupRoot "agent_core_v2_clean_tools") -Recurse -Force
}

if ($PSCmdlet.ShouldProcess($targetApp, "Reemplazar Agent Core v2 clean por el núcleo mínimo")) {
    if (Test-Path $targetApp) { Remove-Item $targetApp -Recurse -Force }
    New-Item -ItemType Directory -Path (Split-Path $targetApp) -Force | Out-Null
    Copy-Item $sourceApp $targetApp -Recurse -Force
}
if ($PSCmdlet.ShouldProcess($targetTools, "Reemplazar herramientas y pruebas de Agent Core v2 clean")) {
    if (Test-Path $targetTools) { Remove-Item $targetTools -Recurse -Force }
    New-Item -ItemType Directory -Path (Split-Path $targetTools) -Force | Out-Null
    Copy-Item $sourceTools $targetTools -Recurse -Force
}

Push-Location $repo
try {
    Write-Host "`n[1/3] Compilando núcleo y páginas..." -ForegroundColor Yellow
    python -m compileall -q app\agent_core_v2_clean pages\Agent_Core_V2_Clean_Lab.py pages\Agent_Core_V2_Robustness_Gate.py

    Write-Host "[2/3] Ejecutando checkpoint estructural..." -ForegroundColor Yellow
    python tools\agent_core_v2_clean\checkpoint.py
    if ($LASTEXITCODE -ne 0) { throw "El checkpoint estructural fallo." }

    Write-Host "[3/3] Ejecutando pruebas de comportamiento sin LLM..." -ForegroundColor Yellow
    python tools\agent_core_v2_clean\behavior_check.py
    if ($LASTEXITCODE -ne 0) { throw "Las pruebas de comportamiento fallaron." }

    Write-Host "`nINSTALACION COMPLETADA." -ForegroundColor Green
    Write-Host "Backup guardado en: $backupRoot" -ForegroundColor Green
    Write-Host "No se modificaron app\backend.py ni streamlit_app.py." -ForegroundColor Green
    Write-Host "Siguiente paso: validar el laboratorio V2 Clean antes de tocar produccion." -ForegroundColor Cyan
}
finally {
    Pop-Location
}
