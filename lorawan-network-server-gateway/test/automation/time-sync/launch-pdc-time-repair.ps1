[CmdletBinding()]
param(
    [string]$Pdc = "svtgm-ad.ad.hijo.com",
    [string[]]$Peers = @("time.windows.com,0x8")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repair = Join-Path $PSScriptRoot "repair-root-pdc-time.ps1"
if (-not (Test-Path $repair -PathType Leaf)) {
    throw "Repair utility not found: $repair"
}

Write-Host ""
Write-Host "SmartAgri PDC time repair"
Write-Host "PDC: $Pdc"
Write-Host ""
Write-Host "A Windows credential prompt will appear once."
Write-Host "The system administrator must enter an AD account authorized to administer the PDC and Group Policy."
Write-Host "The password is kept only in the in-memory PSCredential object and is not written to disk."
Write-Host ""

$cred = Get-Credential -Message "SmartAgri PDC time repair - AD/PDC administrator"
if (-not $cred) { throw "Credential entry was cancelled." }

$session = $null
$remoteRepair = "C:\Windows\Temp\SmartAgri-PdcTimeRepair.ps1"

try {
    Write-Host ""
    Write-Host "=== CONNECTING TO PDC ==="
    $session = New-PSSession -ComputerName $Pdc -Authentication Kerberos -Credential $cred
    Write-Host "PDC_ADMIN_SESSION=PASS"

    Write-Host ""
    Write-Host "=== COPYING VERIFIED REPAIR UTILITY ==="
    Copy-Item -Path $repair -Destination $remoteRepair -ToSession $session -Force

    Write-Host ""
    Write-Host "=== PDC PLAN/PREFLIGHT ==="
    Invoke-Command -Session $session -ArgumentList (, $Peers) -ScriptBlock {
        param([string[]]$PeerList)
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Windows\Temp\SmartAgri-PdcTimeRepair.ps1" -Peers $PeerList
        if ($LASTEXITCODE -ne 0) { throw "PDC repair preflight exited with code $LASTEXITCODE" }
    }

    Write-Host ""
    Write-Host "=== APPLYING PDC TIME REPAIR ==="
    Invoke-Command -Session $session -ArgumentList (, $Peers) -ScriptBlock {
        param([string[]]$PeerList)
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Windows\Temp\SmartAgri-PdcTimeRepair.ps1" -Peers $PeerList -Apply
        if ($LASTEXITCODE -ne 0) { throw "PDC repair exited with code $LASTEXITCODE" }
    }

    Write-Host ""
    Write-Host "=== FINAL PDC TIME STATUS ==="
    Invoke-Command -Session $session -ScriptBlock {
        Write-Host "Source:"
        w32tm.exe /query /source
        Write-Host ""
        Write-Host "Status:"
        w32tm.exe /query /status
    }
}
finally {
    if ($session) {
        Invoke-Command -Session $session -ScriptBlock {
            Remove-Item "C:\Windows\Temp\SmartAgri-PdcTimeRepair.ps1" -Force -ErrorAction SilentlyContinue
        } -ErrorAction SilentlyContinue
        Remove-PSSession $session
    }
    Remove-Variable cred -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=== WORKSTATION VIEW OF PDC TIME ==="
w32tm.exe /stripchart /computer:$Pdc /samples:5 /dataonly
Write-Host ""
Write-Host "PDC_REMOTE_REPAIR_FINISHED=YES"
