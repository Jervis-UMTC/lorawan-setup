Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class NativeWindowCapture {
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rectangle);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int nCmdShow);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd, IntPtr insertAfter, int x, int y, int cx, int cy, uint flags);
}
'@
$dest='lorawan-network-server-gateway/documentation/assets/live-chirpstack-20260922'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$browser=Get-Process firefox -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne '' } | Select-Object -First 1
if(-not $browser){throw 'Dedicated ChirpStack window missing'}
[NativeWindowCapture]::ShowWindow($browser.MainWindowHandle, 9)|Out-Null
[NativeWindowCapture]::SetWindowPos($browser.MainWindowHandle,[IntPtr](-1),0,0,1440,900,0x0040)|Out-Null
[NativeWindowCapture]::SetForegroundWindow($browser.MainWindowHandle)|Out-Null
Start-Sleep -Seconds 4
$rect=New-Object NativeWindowCapture+RECT
if(-not [NativeWindowCapture]::GetWindowRect($browser.MainWindowHandle,[ref]$rect)){throw 'Cannot inspect browser window bounds'}
$width=$rect.Right-$rect.Left;$height=$rect.Bottom-$rect.Top
if($width -lt 600 -or $height -lt 450){throw "Small/hidden window $width x $height"}
$bmp=New-Object System.Drawing.Bitmap($width,$height)
$gfx=[System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($rect.Left,$rect.Top,0,0,$bmp.Size)
$gfx.Dispose()
$bmp.Save("$dest/03-firefox-operator-review.png",[System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"$($browser.Id) $($browser.MainWindowTitle) $width x $height" | Set-Content "$dest/03-firefox-window-info.txt"

