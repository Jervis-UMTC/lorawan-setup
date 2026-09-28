param([string]$ExpectedTitle,[string]$Filename)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;using System.Text;using System.Collections.Generic;using System.Runtime.InteropServices;
public class FirefoxSnap {
 public delegate bool Callback(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback f,IntPtr p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)]public static extern int GetWindowText(IntPtr h,StringBuilder b,int n);
 [DllImport("user32.dll")]public static extern int GetWindowTextLength(IntPtr h);
 [DllImport("user32.dll")]public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
 [DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);
 public static IntPtr Find(string part){
 IntPtr result=IntPtr.Zero;
 EnumWindows((h,p)=>{if(result!=IntPtr.Zero||!IsWindowVisible(h)||GetWindowTextLength(h)==0)return true;
 uint pid;GetWindowThreadProcessId(h,out pid);
 try{if(System.Diagnostics.Process.GetProcessById((int)pid).ProcessName.ToLowerInvariant()!="firefox")return true;}catch{return true;}
 var b=new StringBuilder(600);GetWindowText(h,b,b.Capacity);
 if(b.ToString().Contains(part)){result=h;}return true;},IntPtr.Zero);return result;
 }
}
'@
$w=[FirefoxSnap]::Find($ExpectedTitle)
if($w -eq [IntPtr]::Zero){throw "No dedicated Firefox page: $ExpectedTitle"}
[FirefoxSnap]::SetForegroundWindow($w)|Out-Null
Start-Sleep -Milliseconds 700
[System.Windows.Forms.SendKeys]::SendWait('^+k')
Start-Sleep -Seconds 2
[System.Windows.Forms.SendKeys]::SendWait(':screenshot --fullpage --filename ' + $Filename)
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
Start-Sleep -Seconds 5
[System.Windows.Forms.SendKeys]::SendWait('^+k')
Write-Output 'Requested Firefox full-page screenshot; check downloads'
