[CmdletBinding()]
param(
    [switch]$Offline
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$RustVersion = '1.82.0'
$RustCommit = 'f6e511eec7342f59a25f7c0534f1dbea00d01b14'
$GatewayDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$CargoHome = Join-Path $GatewayDir '.dev-cargo'
$TargetDir = Join-Path $GatewayDir '.dev-target'
$CargoLock = Join-Path $GatewayDir 'Cargo.lock'

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ==="
}

function Assert-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

$rustup = Get-Command 'rustup.exe' -ErrorAction SilentlyContinue
if ($null -eq $rustup) {
    $rustup = Get-Command 'rustup' -ErrorAction SilentlyContinue
}
if ($null -eq $rustup) {
    throw 'rustup is required. Install rustup from the official Rust installer, then rerun this script. The repository pins the compiler version and dependencies.'
}
if (-not (Test-Path -LiteralPath $CargoLock)) {
    throw "Cargo.lock is required: $CargoLock"
}

Write-Step 'ENSURE EXACT RUST TOOLCHAIN'
$toolchains = @(& $rustup.Source toolchain list)
Assert-Exit 'rustup toolchain list'
$haveExact = $false
foreach ($line in $toolchains) {
    if ($line -match '^1\.82\.0(?:-|\s|$)') {
        $haveExact = $true
        break
    }
}

if (-not $haveExact) {
    if ($Offline) {
        throw 'Offline mode requires Rust 1.82.0 to already be installed by rustup.'
    }
    & $rustup.Source toolchain install $RustVersion --profile minimal --component rustfmt --component clippy
    Assert-Exit 'rustup toolchain install 1.82.0'
}
elseif (-not $Offline) {
    # Idempotently ensure the exact toolchain has the required formatter/linter components.
    & $rustup.Source component add --toolchain $RustVersion rustfmt clippy
    Assert-Exit 'rustup component add rustfmt clippy'
}

$rustcInfo = @(& $rustup.Source run $RustVersion rustc -Vv)
Assert-Exit 'rustc -Vv'
$releaseLine = $rustcInfo | Where-Object { $_ -like 'release:*' } | Select-Object -First 1
$commitLine = $rustcInfo | Where-Object { $_ -like 'commit-hash:*' } | Select-Object -First 1
$release = if ($releaseLine) { ($releaseLine -split ':', 2)[1].Trim() } else { '' }
$commit = if ($commitLine) { ($commitLine -split ':', 2)[1].Trim() } else { '' }
if ($release -ne $RustVersion -or $commit -ne $RustCommit) {
    throw "Rust toolchain identity mismatch: release=$release commit=$commit"
}
Write-Host "RUST_VERSION_VALUE=$release"
Write-Host "RUST_COMMIT_VALUE=$commit"
Write-Host 'RUST_TOOLCHAIN_IDENTITY=PASS'

New-Item -ItemType Directory -Force -Path $CargoHome, $TargetDir | Out-Null
$env:CARGO_HOME = $CargoHome
$env:CARGO_TARGET_DIR = $TargetDir
$env:CARGO_TERM_COLOR = 'never'
$env:CARGO_NET_RETRY = '5'
$env:CARGO_HTTP_TIMEOUT = '60'

function Invoke-Cargo([string]$Operation, [string[]]$Arguments) {
    & $rustup.Source run $RustVersion cargo @Arguments
    Assert-Exit $Operation
}

Push-Location $GatewayDir
try {
    Write-Step 'LOCKED DEPENDENCY FETCH'
    if ($Offline) {
        Invoke-Cargo 'cargo fetch --locked --offline' @('fetch', '--locked', '--offline')
    }
    else {
        $fetched = $false
        for ($attempt = 1; $attempt -le 5; $attempt++) {
            & $rustup.Source run $RustVersion cargo fetch --locked
            if ($LASTEXITCODE -eq 0) {
                $fetched = $true
                break
            }
            if ($attempt -lt 5) {
                Write-Warning "cargo fetch attempt $attempt failed; retrying"
                Start-Sleep -Seconds ([Math]::Min(2 * $attempt, 10))
            }
        }
        if (-not $fetched) {
            throw 'cargo fetch --locked failed after five attempts. Partial Cargo cache is preserved; rerun the same command after connectivity returns.'
        }
    }
    Write-Host 'RUST_CARGO_FETCH=PASS'

    Write-Step 'FORMAT GATE'
    & $rustup.Source run $RustVersion cargo fmt --all -- --check
    Assert-Exit 'cargo fmt --all -- --check'
    Write-Host 'RUST_FMT=PASS'

    Write-Step 'TEST GATE'
    $testArgs = @('test', '--locked')
    if ($Offline) { $testArgs += '--offline' }
    Invoke-Cargo 'cargo test --locked' $testArgs
    Write-Host 'RUST_TEST=PASS'

    Write-Step 'CLIPPY GATE'
    $clippyArgs = @('clippy', '--locked', '--all-targets', '--all-features')
    if ($Offline) { $clippyArgs += '--offline' }
    $clippyArgs += @('--', '-D', 'warnings')
    Invoke-Cargo 'cargo clippy --locked --all-targets --all-features' $clippyArgs
    Write-Host 'RUST_CLIPPY=PASS'

    Write-Step 'BUILD GATE'
    $buildArgs = @('build', '--locked')
    if ($Offline) { $buildArgs += '--offline' }
    Invoke-Cargo 'cargo build --locked' $buildArgs
    Write-Host 'RUST_BUILD=PASS'

    Write-Step 'FINAL RESULT'
    Write-Host 'REPRODUCIBLE_GATEWAY_RUST_BUILD=PASS'
}
finally {
    Pop-Location
}
