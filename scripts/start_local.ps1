param([switch]$Simulator)
. "$PSScriptRoot\common.ps1"
$Runtime = Join-Path $ProjectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
$PreviousState = Join-Path $Runtime 'processes.json'
if (Test-Path -LiteralPath $PreviousState) {
    $Previous = Get-Content -LiteralPath $PreviousState -Raw | ConvertFrom-Json
    foreach ($Item in $Previous) {
        $Existing = Get-CimInstance Win32_Process -Filter "ProcessId = $($Item.pid)" -ErrorAction SilentlyContinue
        $RecordedScript = if ($Item.script) { [string]$Item.script } else { Join-Path $PSScriptRoot "start_$($Item.name).ps1" }
        if (Test-NavSphereProcessIdentity $Existing ([string]$Item.created) $RecordedScript) { throw 'NavSphere processes are already running. Use stop_local.ps1 first.' }
    }
}
$Specs = @(
    @{ name='mqtt'; script='start_mqtt.ps1' },
    @{ name='backend'; script='start_backend.ps1' },
    @{ name='frontend'; script='start_frontend.ps1' }
)
if ($Simulator) { $Specs += @{ name='simulator'; script='start_simulator.ps1' } }
$Records = @()
foreach ($Spec in $Specs) {
    $ScriptPath = Join-Path $PSScriptRoot $Spec.script
    $Process = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$ScriptPath`"") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Runtime "$($Spec.name).out.log") -RedirectStandardError (Join-Path $Runtime "$($Spec.name).err.log") -PassThru
    $Details = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)"
    if (-not $Details) { throw "$($Spec.name) exited immediately; inspect .runtime logs" }
    $Records += @{ name=$Spec.name; pid=$Process.Id; created=$Details.CreationDate.ToUniversalTime().ToString('o'); script=$ScriptPath }
    ConvertTo-Json -InputObject @($Records) | Set-Content -LiteralPath $PreviousState
    Start-Sleep -Seconds 2
    if ($Process.HasExited) { throw "$($Spec.name) exited; inspect .runtime logs" }
}
Write-Output 'NavSphere started: http://localhost:5173  API docs: http://localhost:8000/docs'
Write-Output 'Use scripts/stop_local.ps1 to stop only these NavSphere processes.'

