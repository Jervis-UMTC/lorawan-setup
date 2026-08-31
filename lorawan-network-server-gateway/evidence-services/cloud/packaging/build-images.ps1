[CmdletBinding()]
param(
    [switch]$Offline,
    [switch]$ResetToolchain,
    [switch]$ValidateOnly,
    [switch]$VerifyTwice,
    [string]$ImagePrefix = 'lorawan-evidence'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$SourceDateEpoch = 1788048000
$SourceDateUtc = [DateTimeOffset]::FromUnixTimeSeconds($SourceDateEpoch).UtcDateTime
$CloudDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $CloudDir '..\..')).Path
$GoBuildScript = Join-Path $CloudDir 'scripts\dev-build.ps1'
$BinaryDir = Join-Path $CloudDir '.dev-out'
$Dockerfile = Join-Path $PSScriptRoot 'Dockerfile'
$LockFile = Join-Path $PSScriptRoot 'binaries.lock'
$StageRoot = Join-Path $CloudDir '.dev-image-context'

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ==="
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Remove-PathIfPresent([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Assert-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

function Read-BinaryLock {
    $result = @()
    foreach ($line in Get-Content -LiteralPath $LockFile) {
        $line = $line.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) {
            continue
        }
        $parts = $line.Split('|')
        if ($parts.Count -ne 3) {
            throw "Invalid binaries.lock line: $line"
        }
        $name = $parts[0].Trim()
        $size = 0L
        if (-not [Int64]::TryParse($parts[1].Trim(), [ref]$size) -or $size -le 0) {
            throw "Invalid locked size for $name"
        }
        $sha = $parts[2].Trim().ToLowerInvariant()
        if ($sha -notmatch '^[0-9a-f]{64}$') {
            throw "Invalid locked SHA-256 for $name"
        }
        if ($name -notmatch '^gateway-[a-z0-9-]+$') {
            throw "Invalid locked service name: $name"
        }
        $result += [PSCustomObject]@{ Name = $name; Size = $size; Sha256 = $sha }
    }
    if ($result.Count -ne 4) {
        throw "Expected exactly four locked evidence-service binaries, got $($result.Count)"
    }
    if (($result.Name | Sort-Object -Unique).Count -ne $result.Count) {
        throw 'Duplicate service name in binaries.lock'
    }
    return $result
}

if (-not (Test-Path -LiteralPath $GoBuildScript)) {
    throw "Missing reproducible Go build script: $GoBuildScript"
}
if (-not (Test-Path -LiteralPath $Dockerfile)) {
    throw "Missing packaging Dockerfile: $Dockerfile"
}
if (-not (Test-Path -LiteralPath $LockFile)) {
    throw "Missing packaging binary lock: $LockFile"
}

Write-Step 'BUILD CHECKSUM-LOCKED LINUX BINARIES'
$goArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $GoBuildScript)
if ($Offline) { $goArgs += '-Offline' }
if ($ResetToolchain) { $goArgs += '-ResetToolchain' }
& powershell.exe @goArgs
Assert-Exit 'reproducible Go build'

$locked = @(Read-BinaryLock)

Write-Step 'VERIFY BINARY LOCK'
foreach ($item in $locked) {
    $path = Join-Path $BinaryDir $item.Name
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing built binary $path"
    }
    $actualSize = (Get-Item -LiteralPath $path).Length
    $actualSha = Get-Sha256 $path
    if ($actualSize -ne $item.Size) {
        throw "Binary size mismatch for $($item.Name): expected $($item.Size), got $actualSize"
    }
    if ($actualSha -ne $item.Sha256) {
        throw "Binary SHA-256 mismatch for $($item.Name): expected $($item.Sha256), got $actualSha"
    }
    Write-Host "BINARY_LOCK|$($item.Name)|$actualSize|sha256:$actualSha|PASS"
}
Write-Host 'OCI_BINARY_LOCK=PASS'

Write-Step 'VERIFY MINIMAL RUNTIME DOCKERFILE'
$dockerText = Get-Content -LiteralPath $Dockerfile -Raw
$requiredFragments = @(
    'FROM scratch',
    'COPY --chmod=0555 service /service',
    'USER 65532:65532',
    'STOPSIGNAL SIGTERM',
    'ENTRYPOINT ["/service"]'
)
foreach ($fragment in $requiredFragments) {
    if (-not $dockerText.Contains($fragment)) {
        throw "Dockerfile invariant missing: $fragment"
    }
}
$forbiddenFragments = @('apt-get', 'apk add', 'yum ', 'dnf ', 'COPY . ', 'ADD http', 'ENV EVIDENCE_DATABASE_DSN', 'ENV EVIDENCE_MQTT_')
foreach ($fragment in $forbiddenFragments) {
    if ($dockerText.Contains($fragment)) {
        throw "Dockerfile forbidden fragment present: $fragment"
    }
}
Write-Host 'OCI_DOCKERFILE_STATIC=PASS'

if ($ValidateOnly) {
    Write-Host 'OCI_PACKAGING_VALIDATE_ONLY=PASS'
    exit 0
}

Write-Step 'VERIFY OCI BUILDER'
$docker = Get-Command 'docker.exe' -ErrorAction SilentlyContinue
if ($null -eq $docker) {
    $docker = Get-Command 'docker' -ErrorAction SilentlyContinue
}
if ($null -eq $docker) {
    throw 'Docker is unavailable. Packaging source and binary lock are valid; rerun with -ValidateOnly here or run the full command on a Docker Buildx host.'
}
& $docker.Source buildx version
Assert-Exit 'docker buildx version'
Write-Host 'OCI_BUILDER=PASS'

Remove-PathIfPresent $StageRoot
New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null

try {
    foreach ($item in $locked) {
        Write-Step "BUILD OCI IMAGE $($item.Name)"
        $stage = Join-Path $StageRoot $item.Name
        New-Item -ItemType Directory -Force -Path $stage | Out-Null
        Copy-Item -LiteralPath $Dockerfile -Destination (Join-Path $stage 'Dockerfile')
        Copy-Item -LiteralPath (Join-Path $BinaryDir $item.Name) -Destination (Join-Path $stage 'service')
        (Get-Item -LiteralPath (Join-Path $stage 'Dockerfile')).LastWriteTimeUtc = $SourceDateUtc
        (Get-Item -LiteralPath (Join-Path $stage 'service')).LastWriteTimeUtc = $SourceDateUtc

        $tagSuffix = $item.Sha256.Substring(0, 16)
        $image = "$ImagePrefix/$($item.Name):bin-$tagSuffix"
        $commonArgs = @(
            'buildx', 'build',
            '--platform', 'linux/amd64',
            '--load',
            '--provenance=false',
            '--sbom=false',
            '--build-arg', "SERVICE_NAME=$($item.Name)",
            '--build-arg', "BINARY_SHA256=$($item.Sha256)",
            '--build-arg', "SOURCE_DATE_EPOCH=$SourceDateEpoch",
            '--tag', $image,
            $stage
        )
        & $docker.Source @commonArgs
        Assert-Exit "docker buildx build $($item.Name)"

        $imageID1 = (& $docker.Source image inspect --format '{{.Id}}' $image).Trim()
        Assert-Exit "docker image inspect $image"
        $imageUser = (& $docker.Source image inspect --format '{{.Config.User}}' $image).Trim()
        Assert-Exit "docker image inspect user $image"
        $entrypoint = (& $docker.Source image inspect --format '{{json .Config.Entrypoint}}' $image).Trim()
        Assert-Exit "docker image inspect entrypoint $image"
        $imagePlatform = (& $docker.Source image inspect --format '{{.Os}}/{{.Architecture}}' $image).Trim()
        Assert-Exit "docker image inspect platform $image"
        if ($imagePlatform -ne 'linux/amd64') {
            throw "Unexpected image platform for ${image}: $imagePlatform"
        }
        if ($imageUser -ne '65532:65532') {
            throw "Unexpected image user for ${image}: $imageUser"
        }
        if ($entrypoint -ne '["/service"]') {
            throw "Unexpected image entrypoint for ${image}: $entrypoint"
        }

        if ($VerifyTwice) {
            $secondArgs = @($commonArgs[0..($commonArgs.Count - 2)]) + @('--no-cache', $stage)
            & $docker.Source @secondArgs
            Assert-Exit "second docker buildx build $($item.Name)"
            $imageID2 = (& $docker.Source image inspect --format '{{.Id}}' $image).Trim()
            Assert-Exit "second docker image inspect $image"
            if ($imageID2 -ne $imageID1) {
                throw "OCI image reproducibility mismatch for $($item.Name): first=$imageID1 second=$imageID2"
            }
            Write-Host "OCI_REBUILD|$($item.Name)|$imageID2|PASS"
        }

        Write-Host "OCI_IMAGE|$($item.Name)|$image|$imageID1|binary_sha256:$($item.Sha256)|PASS"
    }
}
finally {
    Remove-PathIfPresent $StageRoot
}

if ($VerifyTwice) {
    Write-Host 'OCI_IMAGE_REPRODUCIBILITY=PASS'
}
Write-Host 'OCI_IMAGE_BUILD=PASS'
