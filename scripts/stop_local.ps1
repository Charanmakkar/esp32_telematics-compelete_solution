. "$PSScriptRoot\common.ps1"
$StatePath = Join-Path $ProjectRoot '.runtime\processes.json'
if (-not (Test-Path -LiteralPath $StatePath)) { Write-Output 'No NavSphere-owned processes recorded.'; exit 0 }
$Items = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
foreach ($Item in $Items) {
    if ([string]$Item.pid -notmatch '^\d+$') { throw 'Invalid process ID in NavSphere runtime state' }
    $AllowedScripts = @{ mqtt='start_mqtt.ps1'; backend='start_backend.ps1'; frontend='start_frontend.ps1'; simulator='start_simulator.ps1' }
    if (-not $AllowedScripts.ContainsKey([string]$Item.name)) { throw 'Unknown process in NavSphere runtime state' }
    $ExpectedScript = Join-Path $PSScriptRoot $AllowedScripts[[string]$Item.name]
    if ($Item.script -and [string]$Item.script -ne $ExpectedScript) { throw 'Unexpected script path in NavSphere runtime state' }
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $($Item.pid)" -ErrorAction SilentlyContinue
    if (Test-NavSphereProcessIdentity $Process ([string]$Item.created) $ExpectedScript) {
        Stop-NavSphereProcessTree $Process
        Write-Output "Stopped $($Item.name) and its owned child processes"
    } elseif ($Process) {
        Write-Output "Skipped $($Item.name): PID identity no longer matches the recorded NavSphere process"
    }
}
