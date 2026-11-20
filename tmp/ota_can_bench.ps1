$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $PSScriptRoot
. (Join-Path $Project 'scripts/common.ps1')
$ReceiverScript = Join-Path $Project '.runtime/run_pcan_receiver.py'
$Existing = Get-CimInstance Win32_Process -Filter 'ProcessId = 32436'
if (-not $Existing -or $Existing.CommandLine -notlike ('*' + $ReceiverScript + '*') -or $Existing.CreationDate.ToUniversalTime().ToString('o') -ne '2026-11-20T08:00:20.7936600Z') {
    throw 'Receiver identity changed; no process was stopped.'
}
Stop-NavSphereProcessTree $Existing
try {
    $TestProcess = Start-Process -FilePath (Join-Path $Project 'backend/.venv/Scripts/python.exe') -ArgumentList @(('"' + (Join-Path $Project 'tmp/ota_can_tx_test.py') + '"')) -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Project '.runtime/ota-can-tx-test.log') -RedirectStandardError (Join-Path $Project '.runtime/ota-can-tx-test.err.log') -Wait -PassThru
    $TestResult = $TestProcess.ExitCode
} finally {
    $Process = Start-Process -FilePath (Join-Path $Project 'backend/.venv/Scripts/python.exe') -ArgumentList @(('"' + $ReceiverScript + '"')) -WorkingDirectory $Project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Project '.runtime/pcan-receiver.out.log') -RedirectStandardError (Join-Path $Project '.runtime/pcan-receiver.err.log') -PassThru
    Write-Output "Restored the project CAN receiver (process $($Process.Id))."
}
exit $TestResult
