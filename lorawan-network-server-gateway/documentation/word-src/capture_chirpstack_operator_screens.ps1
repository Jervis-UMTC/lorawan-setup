$ErrorActionPreference='Stop'
$d='lorawan-network-server-gateway/documentation'
$sb=[scriptblock]::Create((Get-Content "$d/word-src/capture_live_cloud_page.ps1" -Raw))
$tenant='https://smartagri-chirpstack.duckdns.org/#/tenants/be278434-60cb-4432-8203-dcfdc30108f3'
$app="$tenant/applications/cbe059b6-fbaf-4397-9bca-3369fa141cc9"
$dev="$app/devices/ac1f09fffe296d29"
$routes=@(
 @{Name='06-gateway-frames-clean';Url="$tenant/gateways/0016c001f139a1cb/frames";Title='frames'},
 @{Name='07-device-profiles-clean';Url="$tenant/device-profiles";Title='Device Profiles'},
 @{Name='08-applications-clean';Url="$tenant/applications";Title='^Applications'},
 @{Name='09-application-devices-clean';Url="$app";Title='dissertation-sensors'},
 @{Name='10-emu-overview-clean';Url="$dev";Title='dissertation-emu-01'},
 @{Name='11-emu-events-clean';Url="$dev/events";Title='Events'}
)
$out=New-Object System.Collections.Generic.List[string]
foreach($v in $routes){
 try {
  $p="$d/assets/live-chirpstack-20260922/$($v.Name).png"
  $lines=& $sb -Url $v.Url -Output $p -ExpectedTitle $v.Title 2>&1
  $out.Add("OK $($v.Name) $lines")
 }catch{
  $out.Add("FAILED $($v.Name): $($_.Exception.Message)")
 }
}
$out | Set-Content "$d/word-src/cloud-screen-capture-results.txt" -Encoding utf8
if($out | Where-Object {$_ -like 'FAILED*'}){exit 2}
