[CmdletBinding()]
param(
    [switch]$Offline,
    [switch]$UpdateModuleLock,
    [switch]$ResetToolchain
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Reproducibility pins. Update these together and only from the official Go release page.
$GoVersion = '1.25.0'
$GoArchive = 'go1.25.0.windows-amd64.zip'
$GoArchiveSha256 = '89efb4f9b30812eee083cc1770fdd2913c14d301064f6454851428f9707d190b'
$GoUrl = "https://go.dev/dl/$GoArchive"
$ExpectedGoVersion = "go$GoVersion"

$ModuleDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ToolsRoot = Join-Path $ModuleDir '.dev-tools'
$CacheRoot = Join-Path $ModuleDir '.dev-cache'
$DownloadDir = Join-Path $ToolsRoot 'downloads'
$ArchivePath = Join-Path $DownloadDir $GoArchive
$PartialArchivePath = "$ArchivePath.partial"
$ToolchainRoot = Join-Path $ToolsRoot "go$GoVersion-windows-amd64"
$ExtractStage = "$ToolchainRoot.extracting"
$ToolchainMarker = Join-Path $ToolchainRoot '.toolchain-verified.txt'
$MarkerExpected = "$GoArchive|$GoArchiveSha256"
$GoRoot = Join-Path $ToolchainRoot 'go'
$GoExe = Join-Path $GoRoot 'bin\go.exe'
$GoFmtExe = Join-Path $GoRoot 'bin\gofmt.exe'
$GoModCache = Join-Path $CacheRoot 'gomod'
$GoBuildCache = Join-Path $CacheRoot 'gobuild'
$GoPath = Join-Path $CacheRoot 'gopath'
$OutputDir = Join-Path $ModuleDir '.dev-out'
$OutputStage = Join-Path $ModuleDir '.dev-out.building'

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ==="
}

function Assert-LastExitCode([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Get-TrustedDecoderSourceDigest {
    $decoderDir = Join-Path $ModuleDir 'internal\trusteddecoder'
    $decoderFiles = @(Get-ChildItem -LiteralPath $decoderDir -File -Filter '*.go' |
        Where-Object { $_.Name -notlike '*_test.go' } |
        Sort-Object Name)
    if ($decoderFiles.Count -eq 0) {
        throw 'Trusted-decoder production source files are missing.'
    }

    $manifestLines = @($decoderFiles | ForEach-Object {
        "$($_.Name)|$(Get-Sha256 $_.FullName)"
    })
    $manifest = ($manifestLines -join "`n") + "`n"
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digestBytes = $sha.ComputeHash($utf8.GetBytes($manifest))
        return ([System.BitConverter]::ToString($digestBytes) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Remove-PathIfPresent([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Invoke-Go([string]$Operation, [string[]]$Arguments) {
    & $GoExe @Arguments
    Assert-LastExitCode $Operation
}

$isWindowsHost = ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT)
if (-not $isWindowsHost) {
    throw 'This bootstrap pins the Windows/amd64 Go archive and must run on Windows. Linux deployment binaries are cross-built below.'
}
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw "Unsupported Windows architecture: $($env:PROCESSOR_ARCHITECTURE). This script pins windows-amd64."
}

Write-Step 'RECOVER STALE GENERATED STATE'
New-Item -ItemType Directory -Force -Path $ToolsRoot, $CacheRoot, $DownloadDir, $GoModCache, $GoBuildCache, $GoPath | Out-Null
# Preserve a partial Go archive across interrupted runs so the next invocation can resume it.
# Extraction/output staging directories are disposable and are always rebuilt from verified inputs.
Remove-PathIfPresent $ExtractStage
Remove-PathIfPresent $OutputStage
Remove-PathIfPresent $OutputDir
if ($ResetToolchain) {
    Remove-PathIfPresent $ToolchainRoot
    Write-Host 'GO_TOOLCHAIN_RESET=PASS'
}

Write-Step 'VERIFY OR ACQUIRE PINNED GO ARCHIVE'
$ArchiveState = 'CACHED'
if (Test-Path -LiteralPath $ArchivePath) {
    $cachedHash = Get-Sha256 $ArchivePath
    if ($cachedHash -ne $GoArchiveSha256) {
        Write-Warning "Cached Go archive checksum mismatch; deleting untrusted cache: $cachedHash"
        Remove-Item -LiteralPath $ArchivePath -Force
    }
}

if (-not (Test-Path -LiteralPath $ArchivePath)) {
    # A previous run can be interrupted after the download completes but before promotion.
    # Promote that file without touching the network when its pinned checksum already matches.
    if (Test-Path -LiteralPath $PartialArchivePath) {
        $partialHash = Get-Sha256 $PartialArchivePath
        if ($partialHash -eq $GoArchiveSha256) {
            Move-Item -LiteralPath $PartialArchivePath -Destination $ArchivePath -Force
            $ArchiveState = 'RECOVERED_COMPLETE_PARTIAL'
        }
    }
}

if (-not (Test-Path -LiteralPath $ArchivePath)) {
    if ($Offline) {
        throw "Offline mode requires verified cached archive $ArchivePath"
    }

    $curl = Get-Command 'curl.exe' -ErrorAction SilentlyContinue
    if ($null -eq $curl) {
        throw 'curl.exe is required for resumable pinned-toolchain downloads on Windows.'
    }

    $hadPartial = Test-Path -LiteralPath $PartialArchivePath
    if ($hadPartial) {
        Write-Host "GO_TOOLCHAIN_PARTIAL_RESUME_BYTES=$((Get-Item -LiteralPath $PartialArchivePath).Length)"
    }

    # -C - resumes an existing partial file and starts at byte zero when it is absent.
    # Keep the partial on failure: rerunning this same script continues from the saved bytes.
    & $curl.Source `
        --fail `
        --location `
        --retry 5 `
        --retry-delay 2 `
        --retry-all-errors `
        --continue-at - `
        --output $PartialArchivePath `
        $GoUrl
    if ($LASTEXITCODE -ne 0) {
        $savedBytes = if (Test-Path -LiteralPath $PartialArchivePath) { (Get-Item -LiteralPath $PartialArchivePath).Length } else { 0 }
        throw "Pinned Go download interrupted (curl exit $LASTEXITCODE). Partial bytes preserved=$savedBytes. Rerun the same command to resume."
    }

    $downloadHash = Get-Sha256 $PartialArchivePath
    if ($downloadHash -ne $GoArchiveSha256) {
        Remove-Item -LiteralPath $PartialArchivePath -Force
        throw "Completed Go archive checksum mismatch: expected $GoArchiveSha256, got $downloadHash. Untrusted partial removed."
    }

    Move-Item -LiteralPath $PartialArchivePath -Destination $ArchivePath -Force
    $ArchiveState = if ($hadPartial) { 'RESUMED_AND_VERIFIED' } else { 'DOWNLOADED_AND_VERIFIED' }
}

$archiveHash = Get-Sha256 $ArchivePath
if ($archiveHash -ne $GoArchiveSha256) {
    throw "Go archive checksum gate failed: expected $GoArchiveSha256, got $archiveHash"
}
Write-Host "GO_TOOLCHAIN_ARCHIVE=$ArchiveState"
Write-Host 'GO_TOOLCHAIN_CHECKSUM=PASS'

Write-Step 'VERIFY OR REBUILD EXTRACTED TOOLCHAIN'
$markerValid = $false
if ((Test-Path -LiteralPath $ToolchainMarker) -and (Test-Path -LiteralPath $GoExe) -and (Test-Path -LiteralPath $GoFmtExe)) {
    $markerValid = ((Get-Content -LiteralPath $ToolchainMarker -Raw).Trim() -eq $MarkerExpected)
}

if (-not $markerValid) {
    Remove-PathIfPresent $ToolchainRoot
    Remove-PathIfPresent $ExtractStage
    New-Item -ItemType Directory -Force -Path $ExtractStage | Out-Null
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractStage -Force
    $stagedGo = Join-Path $ExtractStage 'go\bin\go.exe'
    $stagedGoFmt = Join-Path $ExtractStage 'go\bin\gofmt.exe'
    if (-not (Test-Path -LiteralPath $stagedGo) -or -not (Test-Path -LiteralPath $stagedGoFmt)) {
        throw 'Verified archive extraction did not produce the expected Go executables.'
    }
    Set-Content -LiteralPath (Join-Path $ExtractStage '.toolchain-verified.txt') -Value $MarkerExpected -NoNewline -Encoding ASCII
    Move-Item -LiteralPath $ExtractStage -Destination $ToolchainRoot
    $ToolchainState = 'REBUILT'
}
else {
    $ToolchainState = 'CACHED'
}
Write-Host "GO_TOOLCHAIN_EXTRACTION=$ToolchainState"

# Process-local only. Do not read or write the user's global Go env/profile.
$env:GOROOT = $GoRoot
$env:PATH = "$GoRoot\bin;$env:PATH"
$env:GOTOOLCHAIN = 'local'
$env:GOENV = 'off'
$env:GOMODCACHE = $GoModCache
$env:GOCACHE = $GoBuildCache
$env:GOPATH = $GoPath
$env:GOPRIVATE = ''
$env:GONOPROXY = ''
$env:GONOSUMDB = ''
if ($Offline) {
    $env:GOPROXY = 'off'
    $env:GOSUMDB = 'off'
}
else {
    $env:GOPROXY = 'https://proxy.golang.org,direct'
    $env:GOSUMDB = 'sum.golang.org'
}

$actualGoVersion = (& $GoExe env GOVERSION).Trim()
Assert-LastExitCode 'go env GOVERSION'
if ($actualGoVersion -ne $ExpectedGoVersion) {
    throw "Go version mismatch: expected $ExpectedGoVersion, got $actualGoVersion"
}
Write-Host "GO_VERSION_VALUE=$actualGoVersion"
Write-Host 'GO_VERSION=PASS'

Push-Location $ModuleDir
try {
    Write-Step 'MODULE LOCK'
    if ($UpdateModuleLock) {
        $goModPath = Join-Path $ModuleDir 'go.mod'
        $goSumPath = Join-Path $ModuleDir 'go.sum'
        $originalGoMod = [System.IO.File]::ReadAllBytes($goModPath)
        $hadGoSum = Test-Path -LiteralPath $goSumPath
        if ($hadGoSum) {
            $originalGoSum = [System.IO.File]::ReadAllBytes($goSumPath)
        }
        try {
            $env:GOFLAGS = ''
            Invoke-Go 'go mod tidy' @('mod', 'tidy')
            Write-Host 'GO_MOD_LOCK=UPDATED'
        }
        catch {
            [System.IO.File]::WriteAllBytes($goModPath, $originalGoMod)
            if ($hadGoSum) {
                [System.IO.File]::WriteAllBytes($goSumPath, $originalGoSum)
            }
            elseif (Test-Path -LiteralPath $goSumPath) {
                Remove-Item -LiteralPath $goSumPath -Force
            }
            throw
        }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $ModuleDir 'go.sum'))) {
        throw 'go.sum is missing. Run once with -UpdateModuleLock while dependencies are reachable, review the module diff, and commit go.sum.'
    }

    $env:GOFLAGS = '-mod=readonly'

    Write-Step 'DEPENDENCY VERIFICATION'
    Invoke-Go 'go mod download' @('mod', 'download')
    Write-Host 'GO_MOD_DOWNLOAD=PASS'
    Invoke-Go 'go mod verify' @('mod', 'verify')
    Write-Host 'GO_MOD_VERIFY=PASS'

    Write-Step 'GO FORMAT GATE'
    $goFiles = Get-ChildItem -LiteralPath $ModuleDir -Recurse -File -Filter '*.go' | Where-Object {
        $_.FullName -notlike "$ToolsRoot*" -and
        $_.FullName -notlike "$CacheRoot*" -and
        $_.FullName -notlike "$OutputDir*" -and
        $_.FullName -notlike "$OutputStage*"
    }
    if (-not $goFiles) {
        throw 'No Go source files found under the cloud module.'
    }
    $unformatted = @(& $GoFmtExe -l @($goFiles.FullName))
    Assert-LastExitCode 'gofmt -l'
    if ($unformatted.Count -gt 0) {
        Write-Host 'UNFORMATTED_GO_FILES:'
        $unformatted | ForEach-Object { Write-Host $_ }
        throw 'GOFMT gate failed. Format tracked source deliberately, review the diff, then rerun.'
    }
    Write-Host 'GOFMT=PASS'

    Write-Step 'TRUSTED DECODER BUILD IDENTITY'
    $trustedDecoderDigest = Get-TrustedDecoderSourceDigest
    if ($trustedDecoderDigest -notmatch '^[0-9a-f]{64}$') {
        throw "Trusted-decoder source digest is invalid: $trustedDecoderDigest"
    }
    $trustedDecoderLdFlag = "-X=lorawan/evidence-services/cloud/internal/trusteddecoder.PackageDigest=$trustedDecoderDigest"
    Write-Host "TRUSTED_DECODER_SOURCE_DIGEST=$trustedDecoderDigest"
    Write-Host 'TRUSTED_DECODER_BUILD_IDENTITY=PASS'

    Write-Step 'HOST TEST AND COMPILE GATE'
    Invoke-Go 'go test ./...' @('test', '-trimpath', '-buildvcs=false', './...')
    Write-Host 'GO_TEST=PASS'
    Invoke-Go 'go build ./...' @('build', '-trimpath', '-buildvcs=false', './...')
    Write-Host 'GO_BUILD=PASS'

    Write-Step 'LINUX AMD64 DEPLOYMENT BINARY BUILD'
    Remove-PathIfPresent $OutputStage
    New-Item -ItemType Directory -Force -Path $OutputStage | Out-Null
    $env:GOOS = 'linux'
    $env:GOARCH = 'amd64'
    $env:CGO_ENABLED = '0'

    $targets = @(
        @{ Name = 'gateway-evidence-ingest'; Package = './cmd/evidence-ingest' },
        @{ Name = 'gateway-mqtt-evidence-collector'; Package = './cmd/evidence-mqtt-collector' },
        @{ Name = 'gateway-evidence-verifier'; Package = './cmd/evidence-verifier' },
        @{ Name = 'gateway-fabric-adapter'; Package = './cmd/fabric-adapter' }
    )

    foreach ($target in $targets) {
        $outPath = Join-Path $OutputStage $target.Name
        $buildArgs = @('build', '-trimpath', '-buildvcs=false')
        if ($target.Name -eq 'gateway-evidence-verifier') {
            $buildArgs += @('-ldflags', $trustedDecoderLdFlag)
        }
        $buildArgs += @('-o', $outPath, $target.Package)
        Invoke-Go "go build $($target.Package)" $buildArgs
    }

    Remove-PathIfPresent $OutputDir
    Move-Item -LiteralPath $OutputStage -Destination $OutputDir
    Write-Host 'GO_LINUX_AMD64_BINARIES=PASS'
    foreach ($target in $targets) {
        $artifactPath = Join-Path $OutputDir $target.Name
        $artifactHash = Get-Sha256 $artifactPath
        $artifactSize = (Get-Item -LiteralPath $artifactPath).Length
        Write-Host "ARTIFACT|$($target.Name)|linux/amd64|$artifactSize|sha256:$artifactHash"
    }

    Write-Step 'FINAL RESULT'
    Write-Host 'REPRODUCIBLE_GO_BUILD=PASS'
}
finally {
    Pop-Location
}
