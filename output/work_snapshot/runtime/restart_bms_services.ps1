$ErrorActionPreference='Stop'
$Project=Split-Path -Parent $PSScriptRoot
. (Join-Path $Project 'scripts/common.ps1')
$StatePath=Join-Path $PSScriptRoot 'processes.json'
$Loaded=Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
if($Loaded.PSObject.Properties.Name -contains 'value') { $Records=$Loaded.value } else { $Records=$Loaded }
$ConfigPath=Join-Path $PSScriptRoot 'mqtt/mosquitto.conf'
$Config=Get-Content -LiteralPath $ConfigPath -Raw
$Config=$Config.Replace('message_size_limit 8192','message_size_limit 12288')
Set-Content -LiteralPath $ConfigPath -Value $Config -NoNewline
foreach($Name in @('backend','mqtt')) {
    $Record=$Records | Where-Object name -eq $Name
    $Existing=Get-CimInstance Win32_Process -Filter "ProcessId=$($Record.pid)"
    if(-not (Test-NavSphereProcessIdentity $Existing ([string]$Record.created) ([string]$Record.script))) {
        throw "Process identity changed for $Name; nothing further stopped."
    }
    & taskkill.exe /PID $Record.pid /T /F
    if($LASTEXITCODE -ne 0) { throw "Could not stop $Name" }
}
foreach($Name in @('mqtt','backend')) {
    $Record=$Records | Where-Object name -eq $Name
    $ScriptPath=Join-Path $Project ("scripts/start_"+$Name+".ps1")
    $Process=Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$ScriptPath+'"')) -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot ($Name+'.out.log')) -RedirectStandardError (Join-Path $PSScriptRoot ($Name+'.err.log')) -PassThru
    $Details=Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    if(-not $Details) { throw "$Name exited; inspect logs." }
    $Record.pid=$Process.Id
    $Record.created=$Details.CreationDate.ToUniversalTime().ToString('o')
    $Record.script=$ScriptPath
}
ConvertTo-Json -InputObject @($Records) | Set-Content -LiteralPath $StatePath
Write-Output 'Broker and backend relaunched; frontend remains running.'
