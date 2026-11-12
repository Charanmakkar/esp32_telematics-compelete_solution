param([string]$BindAddress = '127.0.0.1', [int]$Port = 5173)
. "$PSScriptRoot\common.ps1"
Set-Location (Join-Path $ProjectRoot 'frontend')
& npm.cmd run dev -- --host $BindAddress --port $Port --strictPort
