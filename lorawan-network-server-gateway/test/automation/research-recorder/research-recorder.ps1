param(
    [Parameter(Mandatory=$true)][ValidateSet('Preflight','Start','Mark','Trial','Status','Stop')][string]$Action,
    [string]$Group,
    [string]$RunId,
    [string]$Condition = '',
    [string]$ExpectedResult = '',
    [ValidateSet('lorawan','full')][string]$Scope = 'lorawan',
    [int]$IntervalSeconds = 5,
    [string]$DevEui = 'ac1f09fffe296d29',
    [string]$GatewayEui = '0016c001f139a1cb',
    [switch]$CaptureSec,
    [switch]$SkipSerial,
    [string]$Message = '',
    [string]$TrialId = '',
    [string]$ActualResult = '',
    [ValidateSet('PASS','FAIL','INVALID','BLOCKED','UNCLASSIFIED')][string]$TrialStatus = 'UNCLASSIFIED',
    [string]$Notes = ''
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot '..\..\..')).Path
$ResultsRoot = Join-Path $ProjectRoot 'chapter4-results'
$StatePath = Join-Path $ResultsRoot '_recorder-active.json'
$SerialScript = Join-Path $ScriptRoot 'serial-capture.ps1'
$SummaryScript = Join-Path $ScriptRoot 'summarize-run.py'
$SshExe = Join-Path $env:WINDIR 'System32\OpenSSH\ssh.exe'
$RecorderKey = Join-Path $HOME '.ssh\id_ed25519_research_recorder'
$PythonExe = (Get-Command python.exe -ErrorAction Stop).Source

$Targets = [ordered]@{
    ulc01 = 'opsadmin@143.198.205.54'
    ulc02 = 'opsadmin@165.22.253.127'
    ulc03 = 'opsadmin@159.223.50.57'
    gateway = 'root@192.168.20.11'
}

function UtcNow { [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ') }
function Assert-SafeId([string]$Value, [string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$') { throw "Invalid ${Name}: $Value" }
}
function SshArgs([string]$Target, [string]$RemoteCommand) {
    @('-o','BatchMode=yes','-o',"IdentityFile=$RecorderKey",'-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',$Target,$RemoteCommand)
}
function Invoke-Remote([string]$Node, [string]$RemoteCommand) {
    $target = $Targets[$Node]
    $out = & $SshExe @(SshArgs $target $RemoteCommand)
    if ($LASTEXITCODE -ne 0) { throw "Remote command failed on ${Node}: $RemoteCommand" }
    return $out
}
function Invoke-RemoteToFile([string]$Node, [string]$RemoteCommand, [string]$OutPath) {
    $errPath = "$OutPath.stderr"
    $p = Start-Process -FilePath $SshExe -ArgumentList (SshArgs $Targets[$Node] $RemoteCommand) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $OutPath -RedirectStandardError $errPath
    if ($p.ExitCode -ne 0) { throw "Remote export failed on ${Node}: $RemoteCommand (see $errPath)" }
}
function Start-RemoteCapture([string]$Node, [string]$RemoteCommand, [string]$OutPath, [string]$Label) {
    $errPath = "$OutPath.stderr"
    $p = Start-Process -FilePath $SshExe -ArgumentList (SshArgs $Targets[$Node] $RemoteCommand) -PassThru -NoNewWindow -RedirectStandardOutput $OutPath -RedirectStandardError $errPath
    [pscustomobject]@{ label=$Label; pid=$p.Id; stdout=$OutPath; stderr=$errPath }
}
function Get-State {
    if (-not (Test-Path $StatePath)) { throw 'No active research-recorder run.' }
    Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
}
function Save-State($State) {
    New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}
function Stop-Tree([int]$Pid) {
    try { & taskkill.exe /PID $Pid /F 2>$null | Out-Null } catch {}
}
function Record-Usb([string]$Path) {
    Get-CimInstance Win32_SerialPort -ErrorAction SilentlyContinue |
        Select-Object DeviceID,Name,PNPDeviceID |
        Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding UTF8
}
function FileSha([string]$Path) {
    if (Test-Path $Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash } else { '' }
}

if (-not (Test-Path $SshExe)) { throw "OpenSSH client missing: $SshExe" }
if (-not (Test-Path $RecorderKey)) { throw "Recorder key missing: $RecorderKey" }
if ($IntervalSeconds -lt 1 -or $IntervalSeconds -gt 60) { throw 'IntervalSeconds must be 1..60.' }
if ($DevEui -notmatch '^[0-9A-Fa-f]{16}$') { throw 'DevEui must be 16 hex characters.' }

switch ($Action) {
    'Preflight' {
        $rows = @()
        foreach ($n in $Targets.Keys) {
            try {
                $snap = Invoke-Remote $n 'snapshot'
                $rows += [pscustomobject]@{ node=$n; reachable=$true; first_line=($snap | Select-Object -First 1) }
            } catch {
                $rows += [pscustomobject]@{ node=$n; reachable=$false; first_line=$_.Exception.Message }
            }
        }
        $leaderRows = @()
        foreach ($n in @('ulc01','ulc02','ulc03')) {
            try { $leaderRows += [pscustomobject]@{node=$n; role=((Invoke-Remote $n 'db-role') | Select-Object -First 1)} } catch { $leaderRows += [pscustomobject]@{node=$n; role='ERROR'} }
        }
        $usb = Get-CimInstance Win32_SerialPort -ErrorAction SilentlyContinue | Select-Object DeviceID,PNPDeviceID
        $rows | Format-Table -AutoSize
        $leaderRows | Format-Table -AutoSize
        $usb | Format-Table -AutoSize
        if (($rows | Where-Object { -not $_.reachable }).Count -gt 0) { exit 2 }
        if (($leaderRows | Where-Object role -eq 'leader').Count -ne 1) { exit 3 }
        exit 0
    }

    'Start' {
        Assert-SafeId $Group 'Group'; Assert-SafeId $RunId 'RunId'
        if (Test-Path $StatePath) { throw 'A recorder run is already active. Stop it before starting another.' }
        $runDir = Join-Path (Join-Path $ResultsRoot $Group) $RunId
        if (Test-Path $runDir) { throw "Run directory already exists; never overwrite research evidence: $runDir" }
        $raw = Join-Path $runDir 'raw'; $derived = Join-Path $runDir 'derived'; $meta = Join-Path $runDir 'metadata'
        New-Item -ItemType Directory -Force -Path $raw,$derived,$meta | Out-Null
        $startUtc = UtcNow

        $buildDir = Join-Path $ResultsRoot '_configuration\emu01-counted-test-15s'
        $sourcePath = Join-Path $ProjectRoot 'firmware\EMU01_Agriculture_Node\EMU01_Agriculture_Node.ino'
        $hexPath = Join-Path $buildDir 'EMU01_Agriculture_Node.ino.hex'
        $runMeta = [ordered]@{
            run_id=$RunId; group=$Group; scope=$Scope; condition=$Condition; expected_result=$ExpectedResult
            start_utc=$startUtc; dev_eui=$DevEui.ToLowerInvariant(); gateway_eui=$GatewayEui.ToLowerInvariant()
            payload_version=2; payload_bytes=46; emu_profile='COUNTED_TEST_15S'; sample_interval_seconds=15; normal_tx_interval_seconds=15; jitter_seconds=0
            source_sha256=(FileSha $sourcePath); counted_hex_sha256=(FileSha $hexPath)
            recorder_key_fingerprint='SHA256:LcXNMbqJN63QmQwQmjDe0RcjQ+r+hXOy69LZTawDjbs'
        }
        $runMeta | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $meta 'run-meta.json') -Encoding UTF8
        $startUtc | Set-Content -LiteralPath (Join-Path $meta 'start-utc.txt') -Encoding ASCII
        Record-Usb (Join-Path $meta 'usb-start.csv')

        foreach ($n in $Targets.Keys) { Invoke-RemoteToFile $n 'snapshot' (Join-Path $meta "$n-snapshot-start.txt") }

        $children = @()
        if (-not $SkipSerial) {
            $emuLog = Join-Path $raw 'emu-01-source.log'
            $p = Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$SerialScript,'-Label','EMU01','-VidPidRegex','VID_239A&PID_8029','-OutputPath',$emuLog) -PassThru -NoNewWindow
            $children += [pscustomobject]@{label='emu-serial';pid=$p.Id;stdout=$emuLog;stderr=''}
            if ($CaptureSec) {
                $secLog = Join-Path $raw 'sec-source.log'
                $p2 = Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$SerialScript,'-Label','SEC','-VidPidRegex','VID_1915&PID_521F','-OutputPath',$secLog) -PassThru -NoNewWindow
                $children += [pscustomobject]@{label='sec-serial';pid=$p2.Id;stdout=$secLog;stderr=''}
            }
        }

        $children += Start-RemoteCapture 'gateway' "resource $IntervalSeconds" (Join-Path $raw 'gateway-resource.csv') 'gateway-resource'
        $children += Start-RemoteCapture 'gateway' 'logstream' (Join-Path $raw 'gateway.log') 'gateway-log'
        foreach ($n in @('ulc01','ulc02','ulc03')) {
            $children += Start-RemoteCapture $n "resource-host $IntervalSeconds" (Join-Path $raw "$n-host-resource.csv") "$n-host-resource"
            $children += Start-RemoteCapture $n "resource-docker $IntervalSeconds" (Join-Path $raw "$n-docker-resource.csv") "$n-docker-resource"
        }

        'timestamp_utc,type,message' | Set-Content -LiteralPath (Join-Path $raw 'markers.csv') -Encoding UTF8
        'trial_id,test_condition,expected_result,actual_result,status,recorded_utc,notes' | Set-Content -LiteralPath (Join-Path $derived 'trial-results.csv') -Encoding UTF8

        $state = [ordered]@{ run_id=$RunId; group=$Group; scope=$Scope; run_dir=$runDir; start_utc=$startUtc; dev_eui=$DevEui; gateway_eui=$GatewayEui; children=$children }
        Save-State $state
        Write-Output "RECORDER_STARTED=$RunId"
        Write-Output "RUN_DIR=$runDir"
        Write-Output "START_UTC=$startUtc"
    }

    'Mark' {
        $state = Get-State
        if ([string]::IsNullOrWhiteSpace($Message)) { throw 'Mark requires -Message.' }
        $escaped = $Message -replace '"','""'
        Add-Content -LiteralPath (Join-Path $state.run_dir 'raw\markers.csv') -Encoding UTF8 -Value ('"{0}","MARK","{1}"' -f (UtcNow),$escaped)
        Write-Output "MARK_RECORDED=$Message"
    }

    'Trial' {
        $state = Get-State
        Assert-SafeId $TrialId 'TrialId'
        $vals = @($TrialId,$Condition,$ExpectedResult,$ActualResult,$TrialStatus,(UtcNow),$Notes) | ForEach-Object { '"' + ([string]$_ -replace '"','""') + '"' }
        Add-Content -LiteralPath (Join-Path $state.run_dir 'derived\trial-results.csv') -Encoding UTF8 -Value ($vals -join ',')
        Write-Output "TRIAL_RECORDED=$TrialId|$TrialStatus"
    }

    'Status' {
        $state = Get-State
        $state | ConvertTo-Json -Depth 8
        foreach ($c in $state.children) {
            $alive = $null -ne (Get-Process -Id ([int]$c.pid) -ErrorAction SilentlyContinue)
            Write-Output ("{0}|pid={1}|alive={2}" -f $c.label,$c.pid,$alive)
        }
    }

    'Stop' {
        $state = Get-State
        $endUtc = UtcNow
        foreach ($c in $state.children) { Stop-Tree ([int]$c.pid) }
        Start-Sleep -Milliseconds 500
        $runDir = [string]$state.run_dir; $raw = Join-Path $runDir 'raw'; $meta = Join-Path $runDir 'metadata'; $derived = Join-Path $runDir 'derived'
        $endUtc | Set-Content -LiteralPath (Join-Path $meta 'end-utc.txt') -Encoding ASCII
        Record-Usb (Join-Path $meta 'usb-end.csv')
        foreach ($n in $Targets.Keys) { Invoke-RemoteToFile $n 'snapshot' (Join-Path $meta "$n-snapshot-end.txt") }

        $roles = @{}
        foreach ($n in @('ulc01','ulc02','ulc03')) { $roles[$n] = ((Invoke-Remote $n 'db-role') | Select-Object -First 1).Trim() }
        $leaders = @($roles.Keys | Where-Object { $roles[$_] -eq 'leader' })
        if ($leaders.Count -ne 1) { throw "Expected exactly one database leader, got: $($roles | ConvertTo-Json -Compress)" }
        $leader = $leaders[0]
        ($roles | ConvertTo-Json) | Set-Content -LiteralPath (Join-Path $meta 'database-roles-end.json') -Encoding UTF8

        $start = [string]$state.start_utc; $dev = [string]$state.dev_eui
        Invoke-RemoteToFile $leader "db-export uplinks $start $endUtc $dev" (Join-Path $raw 'uplinks.csv')
        Invoke-RemoteToFile $leader "db-export measurements $start $endUtc $dev" (Join-Path $raw 'measurements.csv')
        Invoke-RemoteToFile $leader "db-export outbox $start $endUtc $dev" (Join-Path $raw 'fabric-outbox.csv')

        Invoke-RemoteToFile 'ulc01' "docker-log chirpstack $start $endUtc" (Join-Path $raw 'ulc01-chirpstack.log')
        Invoke-RemoteToFile 'ulc02' "docker-log chirpstack $start $endUtc" (Join-Path $raw 'ulc02-chirpstack.log')
        Invoke-RemoteToFile 'ulc03' "docker-log node-red-node-red-1 $start $endUtc" (Join-Path $raw 'ulc03-node-red.log')
        Invoke-RemoteToFile 'ulc01' "unit-log mosquitto $start $endUtc" (Join-Path $raw 'ulc01-mosquitto.log')
        Invoke-RemoteToFile 'ulc02' "unit-log mosquitto $start $endUtc" (Join-Path $raw 'ulc02-mosquitto.log')
        foreach ($n in @('ulc01','ulc02','ulc03')) { Invoke-RemoteToFile $n "kernel-log $start $endUtc" (Join-Path $raw "$n-kernel.log") }
        if ($state.scope -eq 'full') {
            Invoke-RemoteToFile 'ulc01' "docker-log lorawan-gateway-evidence-fabric-adapter-1 $start $endUtc" (Join-Path $raw 'ulc01-fabric-adapter.log')
            Invoke-RemoteToFile 'ulc02' "docker-log lorawan-gateway-evidence-fabric-adapter-1 $start $endUtc" (Join-Path $raw 'ulc02-fabric-adapter.log')
        }

        & $PythonExe $SummaryScript $runDir
        if ($LASTEXITCODE -ne 0) { throw 'Run summarizer failed.' }
        'RECORDED_UNCLASSIFIED' | Set-Content -LiteralPath (Join-Path $derived 'run-status.txt') -Encoding ASCII

        $hashPath = Join-Path $meta 'SHA256SUMS.csv'
        $files = Get-ChildItem -LiteralPath $runDir -Recurse -File | Where-Object { $_.FullName -ne $hashPath } | Sort-Object FullName
        'relative_path,sha256,bytes' | Set-Content -LiteralPath $hashPath -Encoding UTF8
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($runDir.Length + 1).Replace('\','/')
            $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $f.FullName).Hash
            Add-Content -LiteralPath $hashPath -Encoding UTF8 -Value ('"{0}",{1},{2}' -f $rel,$h,$f.Length)
        }
        Get-ChildItem -LiteralPath $raw -File | ForEach-Object { $_.IsReadOnly = $true }
        Remove-Item -LiteralPath $StatePath -Force
        Write-Output "RECORDER_STOPPED=$($state.run_id)"
        Write-Output "END_UTC=$endUtc"
        Write-Output "SUMMARY=$(Join-Path $derived 'run-summary.json')"
        Write-Output "HASH_MANIFEST=$hashPath"
    }
}
