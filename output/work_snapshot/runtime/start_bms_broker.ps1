$ErrorActionPreference='Stop'
$Project=Split-Path -Parent $PSScriptRoot
$StatePath=Join-Path $PSScriptRoot 'processes.json'
$Records=Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
$Record=$Records | Where-Object name -eq 'mqtt'
if(Get-CimInstance Win32_Process -Filter "ProcessId=$($Record.pid)") { throw 'Recorded broker wrapper still exists; inspect it before relaunch.' }
$ConfigPath=Join-Path $PSScriptRoot 'mqtt/mosquitto.conf'
$Config=Get-Content -LiteralPath $ConfigPath -Raw
# The Ethernet address is absent today. Keep the authenticated local/Wi-Fi listeners.
$Config=$Config.Replace("listener 1883 192.168.9.253","")
Set-Content -LiteralPath $ConfigPath -Value $Config -NoNewline
$ScriptPath=Join-Path $Project 'scripts/start_mqtt.ps1'
$Process=Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$ScriptPath+'"')) -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'mqtt.out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'mqtt.err.log') -PassThru
$Details=Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
$Record.pid=$Process.Id
$Record.created=$Details.CreationDate.ToUniversalTime().ToString('o')
ConvertTo-Json -InputObject @($Records) | Set-Content -LiteralPath $StatePath
'Broker relaunched on loopback and Wi-Fi.'
