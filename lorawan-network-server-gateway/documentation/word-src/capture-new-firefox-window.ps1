param([string]$Url,[string]$Output,[string]$ExpectedTitle,[string]$BottomOutput)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class FirefoxWindows {
 public delegate bool EnumWin(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWin cb,IntPtr p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder t,int n);
 [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [StructLayout(LayoutKind.Sequential)] public struct RECT {public int Left,Top,Right,Bottom;}
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out RECT r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h,IntPtr a,int x,int y,int w,int z,uint flags);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 public static List<IntPtr> List(){
  var result=new List<IntPtr>();
  EnumWindows((h,p)=>{if(!IsWindowVisible(h))return true;
   uint pid;GetWindowThreadProcessId(h,out pid);
   try{if(System.Diagnostics.Process.GetProcessById((int)pid).ProcessName.ToLowerInvariant()!="firefox")return true;}catch{return true;}
   if(GetWindowTextLength(h)>0)result.Add(h);return true;
  },IntPtr.Zero);return result;
 }
 public static string Title(IntPtr h){var b=new StringBuilder(700);GetWindowText(h,b,b.Capacity);return b.ToString();}
}
'@
$previous=[FirefoxWindows]::GetForegroundWindow()
Start-Process 'C:\Program Files\Mozilla Firefox\firefox.exe' -ArgumentList @('-new-window',$Url)
$hwnd=[IntPtr]::Zero
for($i=0;$i -lt 60;$i++){Start-Sleep -Milliseconds 350
 foreach($w in [FirefoxWindows]::List()){
  if([FirefoxWindows]::Title($w) -match $ExpectedTitle -and [FirefoxWindows]::Title($w) -like '*Firefox*'){$hwnd=$w;break}
 }
 if($hwnd -ne [IntPtr]::Zero){break}
}
if($hwnd -eq [IntPtr]::Zero){throw "Real Firefox page not loaded: $ExpectedTitle"}
[FirefoxWindows]::ShowWindow($hwnd,9)|Out-Null
[FirefoxWindows]::SetWindowPos($hwnd,[IntPtr](-1),0,0,1440,900,0x0040)|Out-Null
[FirefoxWindows]::SetForegroundWindow($hwnd)|Out-Null
Start-Sleep -Seconds 3
$r=New-Object FirefoxWindows+RECT
[FirefoxWindows]::GetWindowRect($hwnd,[ref]$r)|Out-Null
$ww=$r.Right-$r.Left;$hh=$r.Bottom-$r.Top
if($ww -lt 900 -or $hh -lt 700){throw 'Window too small'}
$im=New-Object System.Drawing.Bitmap($ww,$hh)
$g=[System.Drawing.Graphics]::FromImage($im)
$g.CopyFromScreen($r.Left,$r.Top,0,0,$im.Size)
$g.Dispose();$im.Save($Output,[System.Drawing.Imaging.ImageFormat]::Png);$im.Dispose()
if($BottomOutput){
 Add-Type -AssemblyName System.Windows.Forms
 [FirefoxWindows]::SetForegroundWindow($hwnd)|Out-Null
 [System.Windows.Forms.SendKeys]::SendWait('{END}')
 Start-Sleep -Seconds 2
 $im=New-Object System.Drawing.Bitmap($ww,$hh)
 $g=[System.Drawing.Graphics]::FromImage($im)
 $g.CopyFromScreen($r.Left,$r.Top,0,0,$im.Size)
 $g.Dispose();$im.Save($BottomOutput,[System.Drawing.Imaging.ImageFormat]::Png);$im.Dispose()
}
[FirefoxWindows]::SetWindowPos($hwnd,[IntPtr](-2),0,0,0,0,0x0013)|Out-Null
if($previous -ne [IntPtr]::Zero){[FirefoxWindows]::SetForegroundWindow($previous)|Out-Null}
Write-Output "CAPTURED $Output; $ww x $hh"
