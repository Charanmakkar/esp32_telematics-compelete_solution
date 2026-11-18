$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $PSScriptRoot
. (Join-Path $Project 'scripts/common.ps1')
$StatePath = Join-Path $PSScriptRoot 'processes.json'
$Records = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
if ($Records.PSObject.Properties.Name -contains 'value') { $Records = $Records.value }
$Record = $Records | Where-Object name -eq 'backend'
$Existing = Get-CimInstance Win32_Process -Filter "ProcessId = $($Record.pid)"
if (-not (Test-NavSphereProcessIdentity $Existing ([string]$Record.created) ([string]$Record.script))) {
    throw 'Backend process identity changed; no process was stopped.'
}
& taskkill.exe /PID $Record.pid /T /F
if ($LASTEXITCODE -ne 0) { throw 'Backend stop failed.' }
$ScriptPath = Join-Path $Project 'scripts/start_backend.ps1'
$Process = Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $ScriptPath + '"')) -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'backend.out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'backend.err.log') -PassThru
$Details = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)"
if (-not $Details) { throw 'New backend exited; inspect logs.' }
$Record.pid = $Process.Id
$Record.created = $Details.CreationDate.ToUniversalTime().ToString('o')
$Record.script = $ScriptPath
ConvertTo-Json -InputObject $Records | Set-Content -LiteralPath $StatePath
Write-Output "Updated backend launched, PID $($Process.Id)."
