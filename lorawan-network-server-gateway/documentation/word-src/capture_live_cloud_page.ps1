param(
 [Parameter(Mandatory=$true)][string]$Url,
 [Parameter(Mandatory=$true)][string]$Output,
 [Parameter(Mandatory=$true)][string]$ExpectedTitle
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class SingleWindowCapture {
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rectangle);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd,int nCmdShow);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd, IntPtr insertAfter, int x, int y, int cx, int cy, uint flags);
}
'@
$browser=Get-Process firefox | Where-Object {$_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match 'ChirpStack'} | Select-Object -First 1
if(-not $browser){throw 'Dedicated single-tab Firefox window not found'}
[SingleWindowCapture]::ShowWindow($browser.MainWindowHandle,9) | Out-Null
[SingleWindowCapture]::SetWindowPos($browser.MainWindowHandle,[IntPtr](-1),0,0,1440,900,0x0040) | Out-Null
[SingleWindowCapture]::SetForegroundWindow($browser.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('^l')
Start-Sleep -Milliseconds 250
[System.Windows.Forms.SendKeys]::SendWait($Url)
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
$ready=$false
for($i=0;$i -lt 28;$i++){
 Start-Sleep -Milliseconds 650
 $browser.Refresh()
 if($browser.MainWindowTitle -match $ExpectedTitle){$ready=$true;break}
}
if(-not $ready){throw "Page did not render expected title '$ExpectedTitle'. Current title '$($browser.MainWindowTitle)'"}
Start-Sleep -Seconds 4
$rect=New-Object SingleWindowCapture+RECT
if(-not [SingleWindowCapture]::GetWindowRect($browser.MainWindowHandle,[ref]$rect)){throw 'Missing browser rectangle'}
$width=$rect.Right-$rect.Left;$height=$rect.Bottom-$rect.Top
if($width -lt 900 -or $height -lt 700){throw "Window not ready: $width x $height"}
$bmp=New-Object System.Drawing.Bitmap($width,$height)
$gfx=[System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($rect.Left,$rect.Top,0,0,$bmp.Size)
$gfx.Dispose()
$bmp.Save($Output,[System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
[SingleWindowCapture]::SetWindowPos($browser.MainWindowHandle,[IntPtr](-2),0,0,0,0,0x0013) | Out-Null
"CAPTURE_OK $Output / $($browser.MainWindowTitle) / $width x $height" | Write-Output
