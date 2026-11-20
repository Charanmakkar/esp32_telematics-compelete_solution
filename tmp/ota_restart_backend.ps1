$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $PSScriptRoot
. (Join-Path $Project 'scripts/common.ps1')
$StatePath = Join-Path $Project '.runtime/processes.json'
$Records = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
if ($Records.PSObject.Properties.Name -contains 'value') { $Records = $Records.value }
$Record = $Records | Where-Object name -eq 'backend'
$Existing = Get-CimInstance Win32_Process -Filter "ProcessId = $($Record.pid)"
if (-not (Test-NavSphereProcessIdentity $Existing ([string]$Record.created) ([string]$Record.script))) { throw 'Backend identity changed; nothing stopped.' }
Stop-NavSphereProcessTree $Existing
$ScriptPath = Join-Path $Project 'scripts/start_backend.ps1'
$Process = Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $ScriptPath + '"')) -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Project '.runtime/backend.out.log') -RedirectStandardError (Join-Path $Project '.runtime/backend.err.log') -PassThru
$Details = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)"
if (-not $Details) { throw 'Backend exited; inspect logs.' }
$Record.pid = $Process.Id
$Record.created = $Details.CreationDate.ToUniversalTime().ToString('o')
$Record.script = $ScriptPath
ConvertTo-Json -InputObject @($Records) -Depth 5 | Set-Content -LiteralPath $StatePath
Write-Output 'Restarted the project backend.'
