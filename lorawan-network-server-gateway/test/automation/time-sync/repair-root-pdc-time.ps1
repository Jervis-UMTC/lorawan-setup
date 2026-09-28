[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$GpoName = "SmartAgri PDC Authoritative Time Source",
    [string[]]$Peers = @("time.windows.com,0x8"),
    [switch]$Apply,
    [string]$RollbackFrom,
    [switch]$SkipPeerProbe
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "=== $Message ==="
}

function Assert-Elevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This repair must run from an elevated PowerShell session using an account authorized to administer the PDC and Group Policy."
    }
}

function Get-Pdc {
    $cs = Get-CimInstance Win32_ComputerSystem
    if (-not $cs.PartOfDomain) { throw "This machine is not joined to an Active Directory domain." }
    $domain = [string]$cs.Domain
    $raw = (& nltest.exe "/dsgetdc:$domain" /PDC /FORCE 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "Unable to resolve the domain PDC emulator with nltest.`n$raw" }
    $m = [regex]::Match($raw, '(?im)^\s*DC:\s*\\\\([^\s]+)\s*$')
    if (-not $m.Success) { throw "Unable to parse the PDC emulator from nltest output.`n$raw" }
    [pscustomobject]@{ Domain = $domain; Host = $m.Groups[1].Value.TrimEnd('.') }
}

function Assert-RunningOnPdc {
    $pdc = Get-Pdc
    $pdcShort = ($pdc.Host -split '\.')[0]
    if (-not $env:COMPUTERNAME.Equals($pdcShort, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to continue: run this script ON the PDC emulator. PDC=$($pdc.Host), local=$env:COMPUTERNAME."
    }
    $pdc
}

function Invoke-Checked([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code ${LASTEXITCODE}: $Command" }
}

function Save-Baseline([string]$Dir, [bool]$GpoExisted) {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    $(if ($GpoExisted) { "present" } else { "absent" }) | Set-Content -Encoding ASCII (Join-Path $Dir "gpo-before.state")
    (& w32tm.exe /query /status /verbose 2>&1 | Out-String) | Set-Content -Encoding UTF8 (Join-Path $Dir "w32tm-status-before.txt")
    (& w32tm.exe /query /source 2>&1 | Out-String) | Set-Content -Encoding UTF8 (Join-Path $Dir "w32tm-source-before.txt")
    (& w32tm.exe /query /configuration 2>&1 | Out-String) | Set-Content -Encoding UTF8 (Join-Path $Dir "w32tm-configuration-before.txt")
    & reg.exe export "HKLM\SYSTEM\CurrentControlSet\Services\W32Time" (Join-Path $Dir "w32time-service-before.reg") /y | Out-Null
    if (Test-Path "HKLM:\SOFTWARE\Policies\Microsoft\W32Time") {
        & reg.exe export "HKLM\SOFTWARE\Policies\Microsoft\W32Time" (Join-Path $Dir "w32time-policy-before.reg") /y | Out-Null
        "present" | Set-Content -Encoding ASCII (Join-Path $Dir "w32time-policy-before.state")
    } else {
        "absent" | Set-Content -Encoding ASCII (Join-Path $Dir "w32time-policy-before.state")
    }
}

function Test-NtpPeers([string[]]$PeerList) {
    $ok = 0
    foreach ($peer in $PeerList) {
        $hostName = ($peer -split ',')[0].Trim()
        if (-not $hostName) { continue }
        Write-Host "Probing NTP peer $hostName ..."
        $probe = (& w32tm.exe /stripchart "/computer:$hostName" /samples:2 /dataonly 2>&1 | Out-String)
        Write-Host $probe.TrimEnd()
        if ($LASTEXITCODE -eq 0 -and $probe -notmatch '(?i)error|timed out|no such host') { $ok++ }
    }
    $ok
}

function Get-DomainControllersOuDn {
    $root = [ADSI]"LDAP://RootDSE"
    $base = [string]$root.defaultNamingContext
    if (-not $base) { throw "Unable to read the domain naming context." }
    "OU=Domain Controllers,$base"
}

function Remove-RepairGpo([string]$Name, [string]$TargetDn) {
    Import-Module GroupPolicy -ErrorAction Stop
    $gpo = Get-GPO -Name $Name -ErrorAction SilentlyContinue
    if ($gpo) {
        $inheritance = Get-GPInheritance -Target $TargetDn
        if (@($inheritance.GpoLinks | Where-Object { $_.DisplayName -eq $Name }).Count -gt 0) {
            Remove-GPLink -Name $Name -Target $TargetDn -Confirm:$false | Out-Null
        }
        Remove-GPO -Guid $gpo.Id -Confirm:$false
    }
}

function Restore-Baseline([string]$BackupDir) {
    Assert-Elevated
    $null = Assert-RunningOnPdc
    $targetDn = Get-DomainControllersOuDn
    if (-not (Test-Path $BackupDir -PathType Container)) { throw "Rollback directory does not exist: $BackupDir" }
    $serviceReg = Join-Path $BackupDir "w32time-service-before.reg"
    if (-not (Test-Path $serviceReg)) { throw "Rollback directory is missing w32time-service-before.reg." }

    Write-Step "ROLLBACK GPO"
    $gpoState = Join-Path $BackupDir "gpo-before.state"
    if ((Test-Path $gpoState) -and ((Get-Content $gpoState -Raw).Trim() -eq "present")) {
        Write-Host "The dedicated GPO existed before this repair; leaving it in place."
    } else {
        Remove-RepairGpo -Name $GpoName -TargetDn $targetDn
    }

    Write-Step "RESTORE W32TIME REGISTRY"
    Invoke-Checked { & reg.exe import $serviceReg }
    $policyState = Join-Path $BackupDir "w32time-policy-before.state"
    $policyReg = Join-Path $BackupDir "w32time-policy-before.reg"
    if ((Test-Path $policyState) -and ((Get-Content $policyState -Raw).Trim() -eq "present") -and (Test-Path $policyReg)) {
        Invoke-Checked { & reg.exe import $policyReg }
    }

    Write-Step "REFRESH POLICY AND SERVICE"
    & gpupdate.exe /target:computer /force
    Restart-Service w32time -Force
    & w32tm.exe /config /update
    & w32tm.exe /resync /rediscover
    Write-Host "Rollback completed from $BackupDir."
}

if ($RollbackFrom) {
    Restore-Baseline -BackupDir $RollbackFrom
    exit 0
}

$pdc = Assert-RunningOnPdc
$targetDn = Get-DomainControllersOuDn
$peerString = ($Peers -join ' ').Trim()
if (-not $peerString) { throw "At least one NTP peer is required." }

Write-Step "PREFLIGHT"
Write-Host "Domain=$($pdc.Domain)"
Write-Host "PDC=$($pdc.Host)"
Write-Host "TargetOU=$targetDn"
Write-Host "GPO=$GpoName"
Write-Host "Peers=$peerString"
& w32tm.exe /query /source
& w32tm.exe /query /status
& w32tm.exe /query /configuration

if (-not $SkipPeerProbe) {
    Write-Step "EXTERNAL NTP REACHABILITY"
    $reachable = Test-NtpPeers -PeerList $Peers
    if ($reachable -lt 1) { throw "None of the configured NTP peers responded. No changes were made." }
}

if (-not $Apply) {
    Write-Step "PLAN ONLY"
    Write-Host "No changes were made."
    Write-Host "Re-run from an elevated, authorized PDC session with -Apply."
    exit 0
}

Assert-Elevated
Import-Module GroupPolicy -ErrorAction Stop

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $env:ProgramData "SmartAgri\PdcTimeRepair\$stamp"
$existing = Get-GPO -Name $GpoName -ErrorAction SilentlyContinue
Write-Step "SAVE BASELINE"
Save-Baseline -Dir $backupDir -GpoExisted ([bool]$existing)
Write-Host "Backup=$backupDir"

if ($existing) {
    Write-Step "REFRESH EXISTING PDC-ONLY AUTHORITATIVE TIME GPO"
    $gpo = $existing
} else {
    Write-Step "CREATE PDC-ONLY AUTHORITATIVE TIME GPO"
    $gpo = New-GPO -Name $GpoName -Comment "SmartAgri root PDC external NTP policy; created by repair-root-pdc-time.ps1 on $stamp."
}

$inheritance = Get-GPInheritance -Target $targetDn
$link = @($inheritance.GpoLinks | Where-Object { $_.DisplayName -eq $GpoName })
if ($link.Count -eq 0) {
    New-GPLink -Name $GpoName -Target $targetDn -LinkEnabled Yes -Order 1 | Out-Null
} else {
    Set-GPLink -Name $GpoName -Target $targetDn -LinkEnabled Yes -Order 1 | Out-Null
}
Set-GPPermission -Guid $gpo.Id -TargetName "Authenticated Users" -TargetType Group -PermissionLevel GpoRead -Replace | Out-Null
Set-GPPermission -Guid $gpo.Id -TargetName $env:COMPUTERNAME -TargetType Computer -PermissionLevel GpoApply | Out-Null
Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\SOFTWARE\Policies\Microsoft\W32Time\Parameters" -ValueName "Type" -Type String -Value "NTP"
Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\SOFTWARE\Policies\Microsoft\W32Time\Parameters" -ValueName "NtpServer" -Type String -Value $peerString
Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\SOFTWARE\Policies\Microsoft\W32Time\TimeProviders\NtpClient" -ValueName "Enabled" -Type DWord -Value 1
Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\SOFTWARE\Policies\Microsoft\W32Time\TimeProviders\NtpServer" -ValueName "Enabled" -Type DWord -Value 1
Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\SOFTWARE\Policies\Microsoft\W32Time\Config" -ValueName "AnnounceFlags" -Type DWord -Value 5

Write-Step "APPLY POLICY AND W32TIME CONFIGURATION"
Invoke-Checked { & gpupdate.exe /target:computer /force }
Invoke-Checked { & w32tm.exe /config "/manualpeerlist:$peerString" /syncfromflags:manual /reliable:yes /update }
Restart-Service w32time -Force
Start-Sleep -Seconds 3
& w32tm.exe /resync /rediscover
Start-Sleep -Seconds 8

Write-Step "VERIFY"
$source = (& w32tm.exe /query /source 2>&1 | Out-String).Trim()
$status = (& w32tm.exe /query /status /verbose 2>&1 | Out-String).Trim()
$config = (& w32tm.exe /query /configuration 2>&1 | Out-String).Trim()
$source | Set-Content -Encoding UTF8 (Join-Path $backupDir "w32tm-source-after.txt")
$status | Set-Content -Encoding UTF8 (Join-Path $backupDir "w32tm-status-after.txt")
$config | Set-Content -Encoding UTF8 (Join-Path $backupDir "w32tm-configuration-after.txt")
Write-Host "Source=$source"
Write-Host $status

if ($source -match '(?i)Local CMOS Clock|VM IC Time Synchronization Provider|Free-running System Clock') {
    throw "PDC still reports a local/virtual clock source. The GPO was left in place for inspection. Use -RollbackFrom '$backupDir' if rollback is required."
}
if ((Test-NtpPeers -PeerList $Peers) -lt 1) {
    throw "PDC source changed, but post-change NTP peer verification failed. Inspect $backupDir before proceeding."
}

Write-Host ""
Write-Host "PDC_TIME_REPAIR=PASS"
Write-Host "PDC_SOURCE=$source"
Write-Host "BACKUP_DIR=$backupDir"
Write-Host "Next: allow domain members to resync, then rerun the LoRaWAN research-recorder preflight."
