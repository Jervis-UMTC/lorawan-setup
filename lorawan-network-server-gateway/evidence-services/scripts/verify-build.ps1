[CmdletBinding()]
param(
    [switch]$Offline,
    [switch]$ResetGoToolchain
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$EvidenceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$CloudBuild = Join-Path $EvidenceRoot 'cloud\scripts\dev-build.ps1'
$GatewayBuild = Join-Path $EvidenceRoot 'gateway\scripts\dev-build.ps1'

function Assert-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $CloudBuild)) {
    throw "Missing cloud build script: $CloudBuild"
}
if (-not (Test-Path -LiteralPath $GatewayBuild)) {
    throw "Missing gateway build script: $GatewayBuild"
}

Write-Host "`n=== CLOUD GO EVIDENCE SERVICES ==="
$cloudArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $CloudBuild)
if ($Offline) { $cloudArgs += '-Offline' }
if ($ResetGoToolchain) { $cloudArgs += '-ResetToolchain' }
& powershell.exe @cloudArgs
Assert-Exit 'cloud reproducible build'

Write-Host "`n=== GATEWAY RUST EVIDENCE CORE ==="
$gatewayArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $GatewayBuild)
if ($Offline) { $gatewayArgs += '-Offline' }
& powershell.exe @gatewayArgs
Assert-Exit 'gateway reproducible build'

Write-Host "`n=== FINAL RESULT ==="
Write-Host 'EVIDENCE_SERVICES_REPRODUCIBLE_BUILD=PASS'
