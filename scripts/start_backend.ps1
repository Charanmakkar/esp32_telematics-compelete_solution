param([string]$BindAddress = '127.0.0.1', [int]$Port = 8000)
. "$PSScriptRoot\common.ps1"
Set-Location (Join-Path $ProjectRoot 'backend')
& $PythonExe -m alembic upgrade head
Assert-ExitCode 'Database migration'
& $PythonExe -m uvicorn app.main:app --host $BindAddress --port $Port
