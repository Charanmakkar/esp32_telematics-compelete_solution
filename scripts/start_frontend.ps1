param([string]$BindAddress = '0.0.0.0', [int]$Port = 5173)
. "$PSScriptRoot\common.ps1"
Set-Location (Join-Path $ProjectRoot 'frontend')
& npm.cmd run dev -- --host $BindAddress --port $Port --strictPort
