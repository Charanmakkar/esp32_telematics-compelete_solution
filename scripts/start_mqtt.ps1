. "$PSScriptRoot\common.ps1"
$Broker = Join-Path $ProjectRoot '.tools\mosquitto\mosquitto.exe'
if (-not (Test-Path -LiteralPath $Broker)) { $Broker = (Get-Command mosquitto.exe -ErrorAction Stop).Source }
$Configuration = Join-Path $ProjectRoot '.runtime\mqtt\mosquitto.conf'
if (-not (Test-Path -LiteralPath $Configuration)) { throw 'Run setup_windows.ps1 first.' }
& $Broker -c $Configuration
