param([switch]$Integration, [switch]$Firmware)
. "$PSScriptRoot\common.ps1"
Set-Location (Join-Path $ProjectRoot 'backend')
& $PythonExe -m pytest -q
Assert-ExitCode 'Backend tests'
& $PythonExe -m ruff check app tests migrations
Assert-ExitCode 'Backend lint'
Set-Location (Join-Path $ProjectRoot 'frontend')
& npm.cmd test -- --run
Assert-ExitCode 'Frontend tests'
& npm.cmd run build
Assert-ExitCode 'Frontend build'
Set-Location $ProjectRoot
& $PythonExe -m unittest discover -s simulator -p 'test_*.py'
Assert-ExitCode 'Simulator tests'
if ($Firmware) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File firmware\tools\build.ps1
    Assert-ExitCode 'ESP-IDF build'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File firmware\tools\test_host.ps1
    Assert-ExitCode 'Firmware host tests'
}
if ($Integration) {
    & $PythonExe scripts\integration_test.py
    Assert-ExitCode 'Live MQTT/MySQL integration'
}
