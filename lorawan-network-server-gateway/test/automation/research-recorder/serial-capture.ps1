param(
    [Parameter(Mandatory=$true)][string]$Label,
    [Parameter(Mandatory=$true)][string]$VidPidRegex,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [int]$BaudRate = 115200
)

$ErrorActionPreference = 'Stop'
$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null

function Write-CaptureLine([string]$Port, [string]$Text) {
    $ts = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $safe = $Text -replace "`r|`n", ''
    Add-Content -LiteralPath $OutputPath -Encoding UTF8 -Value "$ts|$Label|$Port|$safe"
}

$lastPort = $null
while ($true) {
    $portInfo = Get-CimInstance Win32_SerialPort -ErrorAction SilentlyContinue |
        Where-Object { $_.PNPDeviceID -match $VidPidRegex } |
        Select-Object -First 1

    if (-not $portInfo) {
        if ($lastPort -ne '<absent>') {
            Write-CaptureLine 'NONE' 'RECORDER_DEVICE_ABSENT'
            $lastPort = '<absent>'
        }
        Start-Sleep -Milliseconds 750
        continue
    }

    $port = [string]$portInfo.DeviceID
    if ($lastPort -ne $port) {
        Write-CaptureLine $port ("RECORDER_DEVICE_PRESENT,pnp=" + $portInfo.PNPDeviceID)
        $lastPort = $port
    }

    $serial = $null
    try {
        $serial = New-Object System.IO.Ports.SerialPort $port,$BaudRate,'None',8,'One'
        $serial.ReadTimeout = 1000
        $serial.WriteTimeout = 1000
        $serial.DtrEnable = $true
        $serial.RtsEnable = $false
        $serial.NewLine = "`n"
        $serial.Open()
        Write-CaptureLine $port 'RECORDER_SERIAL_OPEN'

        while ($serial.IsOpen) {
            try {
                $line = $serial.ReadLine()
                Write-CaptureLine $port $line.TrimEnd("`r","`n")
            } catch [System.TimeoutException] {
                # Expected while the device is quiet.
            }
        }
    } catch {
        Write-CaptureLine $port ("RECORDER_SERIAL_ERROR," + ($_.Exception.Message -replace '[\r\n]+',' '))
        Start-Sleep -Milliseconds 750
    } finally {
        if ($serial) {
            try { if ($serial.IsOpen) { $serial.Close() } } catch {}
            try { $serial.Dispose() } catch {}
        }
    }
}
