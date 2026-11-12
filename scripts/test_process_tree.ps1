# Uses sacrificial hidden processes; never selects live services by name or port.
. "$PSScriptRoot\common.ps1"
$TestToken = [guid]::NewGuid().ToString('N')
$TestDirectory = Join-Path $ProjectRoot '.runtime'
New-Item -ItemType Directory -Path $TestDirectory -Force | Out-Null
$TestScript = Join-Path $TestDirectory "tree-test-$TestToken.ps1"
$ChildState = Join-Path $TestDirectory "tree-child-$TestToken.txt"
@'
param([string]$ChildIdPath)
$Child = Start-Process powershell.exe -ArgumentList @('-NoProfile','-Command','Start-Sleep -Seconds 300') -WindowStyle Hidden -PassThru
Set-Content -LiteralPath $ChildIdPath -Value $Child.Id
Start-Sleep -Seconds 300
'@ | Set-Content -LiteralPath $TestScript
$TestProcess = Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$TestScript`"",'-ChildIdPath',"`"$ChildState`"") -WindowStyle Hidden -PassThru
try {
    for ($Attempt = 0; $Attempt -lt 30 -and -not (Test-Path -LiteralPath $ChildState); $Attempt++) { Start-Sleep -Milliseconds 100 }
    if (-not (Test-Path -LiteralPath $ChildState)) { throw 'Sacrificial child did not start' }
    $ChildIdentifier = [int](Get-Content -LiteralPath $ChildState)
    $RootDetails = Get-CimInstance Win32_Process -Filter "ProcessId = $($TestProcess.Id)"
    if (-not (Test-NavSphereProcessIdentity $RootDetails ($RootDetails.CreationDate.ToUniversalTime().ToString('o')) $TestScript)) { throw 'Identity check failed' }
    if (Test-NavSphereProcessIdentity $RootDetails 'wrong-creation-time' $TestScript) { throw 'Reused PID guard failed' }
    Stop-NavSphereProcessTree $RootDetails
    Start-Sleep -Milliseconds 500
    if ((Get-Process -Id $TestProcess.Id -ErrorAction SilentlyContinue) -or (Get-Process -Id $ChildIdentifier -ErrorAction SilentlyContinue)) { throw 'Owned process tree survived stop' }
    Write-Output 'Process identity and owned descendant shutdown test passed'
} finally {
    if (Get-Process -Id $TestProcess.Id -ErrorAction SilentlyContinue) { Stop-NavSphereProcessTree (Get-CimInstance Win32_Process -Filter "ProcessId = $($TestProcess.Id)") }
    Remove-Item -LiteralPath $TestScript -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $ChildState -ErrorAction SilentlyContinue
}
