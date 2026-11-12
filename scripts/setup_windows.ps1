param([string]$DatabaseHost = '127.0.0.1', [int]$DatabasePort = 3306, [string]$DatabaseAdmin = 'root', [string]$DatabaseClientHost = '')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
python scripts\install_tools.py
if ($LASTEXITCODE -ne 0) { throw 'Portable tool setup failed' }
if (-not (Test-Path -LiteralPath 'backend\.venv\Scripts\python.exe')) { python -m venv backend\.venv }
. "$PSScriptRoot\common.ps1"
& $PythonExe -m pip install -r backend\requirements.lock
Assert-ExitCode 'Python dependency installation'
$SetupArguments = @('scripts\setup_local.py', '--db-host', $DatabaseHost, '--db-port', $DatabasePort, '--admin-user', $DatabaseAdmin)
if ($DatabaseClientHost) { $SetupArguments += @('--db-client-host', $DatabaseClientHost) }
& $PythonExe @SetupArguments
Assert-ExitCode 'Local credential setup'
Set-Location (Join-Path $ProjectRoot 'backend')
& $PythonExe -m alembic upgrade head
Assert-ExitCode 'Database migration'
Set-Location (Join-Path $ProjectRoot 'frontend')
& npm.cmd ci
Assert-ExitCode 'Frontend dependency installation'
Write-Output 'Ready. Start MQTT, backend and frontend with the three start scripts; simulator is optional.'
