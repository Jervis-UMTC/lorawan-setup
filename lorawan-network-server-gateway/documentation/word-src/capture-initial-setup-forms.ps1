$ErrorActionPreference='Stop'
$d='lorawan-network-server-gateway/documentation'
$base='https://smartagri-chirpstack.duckdns.org/#/tenants/be278434-60cb-4432-8203-dcfdc30108f3'
$open=[scriptblock]::Create((Get-Content "$d/word-src/capture-new-firefox-window.ps1" -Raw))
$full=[scriptblock]::Create((Get-Content "$d/word-src/capture-firefox-fullpage.ps1" -Raw))
$rows=@(
 @{url="$base/gateways/create";title='^Add \| Gateways';name='13-add-gateway'},
 @{url="$base/device-profiles/create";title='^Add \| Device profiles';name='14-add-device-profile'},
 @{url="$base/device-profiles/bd4c5e8d-64f9-4db9-abc7-be0484d530a9/edit";title='EMU-01 RAK4631 AS923';name='15-existing-emu-profile'},
 @{url="$base/applications/create";title='^Add \| Applications';name='16-add-application'}
)
$out=New-Object System.Collections.Generic.List[string]
foreach($row in $rows){
 try{
  $asset="$d/assets/live-chirpstack-20260922/$($row.name)"
  & $open -Url $row.url -Output "$asset-viewport.png" -ExpectedTitle $row.title | Out-Null
  & $full -ExpectedTitle ($row.title.Replace('^','').Replace('\','')) -Filename "$($row.name)-manual.png" | Out-Null
  Start-Sleep -Milliseconds 400
  $download=Get-ChildItem "$env:USERPROFILE\Downloads" -Filter "$($row.name)-manual*fullpage.png" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if(-not $download){throw "Firefox fullpage image not downloaded: $($row.name)"}
  Copy-Item -LiteralPath $download.FullName -Destination "$asset-fullpage.png" -Force -ErrorAction Stop
  $out.Add("OK $($row.name) $($download.Length) bytes")
 }catch{$out.Add("ERROR $($row.name): $($_.Exception.Message)")}
}
$out | Set-Content "$d/word-src/setup-form-fullpage-results.txt" -Encoding utf8
