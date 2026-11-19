$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $PSScriptRoot
. (Join-Path $Project 'scripts/common.ps1')
$StatePath = Join-Path $PSScriptRoot 'processes.json'
$Records = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
if ($Records.PSObject.Properties.Name -contains 'value') { $Records = $Records.value }
foreach ($Name in @('mqtt', 'backend')) {
    $Record = $Records | Where-Object name -eq $Name
    $Existing = Get-CimInstance Win32_Process -Filter "ProcessId = $($Record.pid)"
    if (-not (Test-NavSphereProcessIdentity $Existing ([string]$Record.created) ([string]$Record.script))) {
        throw "Process identity changed for $Name; no process was stopped."
    }
    Stop-NavSphereProcessTree $Existing
    $ScriptPath = Join-Path $Project "scripts/start_$Name.ps1"
    $Process = Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $ScriptPath + '"')) -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot "$Name.out.log") -RedirectStandardError (Join-Path $PSScriptRoot "$Name.err.log") -PassThru
    $Details = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)"
    if (-not $Details) { throw "New $Name exited; inspect logs." }
    $Record.pid = $Process.Id
    $Record.created = $Details.CreationDate.ToUniversalTime().ToString('o')
    $Record.script = $ScriptPath
    ConvertTo-Json -InputObject $Records | Set-Content -LiteralPath $StatePath
    Write-Output "$Name restarted with the CAN TX update."
}
