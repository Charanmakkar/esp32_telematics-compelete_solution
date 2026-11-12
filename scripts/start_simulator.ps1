param([double]$Duration = 0)
. "$PSScriptRoot\common.ps1"
Set-Location $ProjectRoot
& $PythonExe simulator\telemetry_simulator.py --duration $Duration
