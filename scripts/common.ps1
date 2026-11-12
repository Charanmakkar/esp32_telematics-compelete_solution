$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot 'backend\.venv\Scripts\python.exe'
$NodeDirectory = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot '.tools') -Directory -Filter 'node-*-win-x64' -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
if ($NodeDirectory) { $env:PATH = "$($NodeDirectory.FullName);$env:PATH" }
function Assert-ExitCode([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed with exit code $LASTEXITCODE" }
}

function Test-NavSphereProcessIdentity($Process, [string]$Created, [string]$ScriptPath) {
    if (-not $Process -or -not $Process.CreationDate -or -not $Process.CommandLine) { return $false }
    if ($Process.CreationDate.ToUniversalTime().ToString('o') -ne $Created) { return $false }
    return $Process.CommandLine.IndexOf($ScriptPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Stop-NavSphereProcessTree($RootProcess) {
    # Ownership starts at a verified wrapper. Never select by process name or port.
    $Snapshot = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    $Owned = New-Object 'System.Collections.Generic.List[object]'
    $Owned.Add($RootProcess)
    for ($Index = 0; $Index -lt $Owned.Count; $Index++) {
        $ParentProcess = $Owned[$Index]
        foreach ($ChildProcess in $Snapshot) {
            if ($ChildProcess.ParentProcessId -eq $ParentProcess.ProcessId -and
                $ChildProcess.CreationDate -ge $ParentProcess.CreationDate -and
                -not ($Owned | Where-Object ProcessId -eq $ChildProcess.ProcessId)) {
                $Owned.Add($ChildProcess)
            }
        }
    }
    # Freeze the wrapper first so it cannot launch another service while we stop children.
    $Order = @($Owned[0])
    for ($Index = $Owned.Count - 1; $Index -ge 1; $Index--) { $Order += $Owned[$Index] }
    foreach ($Candidate in $Order) {
        $Current = Get-CimInstance Win32_Process -Filter "ProcessId = $($Candidate.ProcessId)" -ErrorAction SilentlyContinue
        if ($Current -and $Current.CreationDate -eq $Candidate.CreationDate) {
            Stop-Process -Id $Candidate.ProcessId -ErrorAction Stop
        }
    }
}
