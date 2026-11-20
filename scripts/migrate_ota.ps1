param(
    [Parameter(Mandatory=$true)][string]$Port,
    [string]$Python = 'C:\Espressif\tools\python\v6.0.2\venv\Scripts\python.exe'
)
$ErrorActionPreference = 'Stop'
$OtaRoot = Split-Path -Parent $PSScriptRoot
$OtaRelease = Join-Path $OtaRoot 'output\firmware'
$OtaManifest = Get-Content -LiteralPath (Join-Path $OtaRelease 'manifest.json') -Raw | ConvertFrom-Json
if ($OtaManifest.ota.protocol -ne 1 -or $OtaManifest.flash_size -ne '4MB') { throw 'Expected the 4 MB OTA release package' }
if (-not ([System.IO.Ports.SerialPort]::GetPortNames() -contains $Port)) { throw "Serial port $Port is not connected" }
foreach ($OtaName in @('bootloader.bin','partition-table.bin','navsphere.bin','ota_data_initial.bin')) {
    $OtaHash = (Get-FileHash -LiteralPath (Join-Path $OtaRelease $OtaName) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($OtaHash -ne $OtaManifest.files.$OtaName.sha256) { throw "Release hash mismatch: $OtaName" }
}
$OtaBackupDir = Join-Path $OtaRoot '.runtime\ota-backups'
New-Item -ItemType Directory -Path $OtaBackupDir -Force | Out-Null
$OtaBackup = Join-Path $OtaBackupDir ("before-ota-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bin')
Write-Host 'Backing up all 4 MB of flash. The private backup includes device credentials.'
& $Python -m esptool --chip esp32 --port $Port --baud 115200 read-flash 0 0x400000 $OtaBackup
if ($LASTEXITCODE -ne 0 -or (Get-Item -LiteralPath $OtaBackup).Length -ne 0x400000) { throw 'Flash backup failed; migration stopped' }
Write-Host 'Installing OTA bootloader, partition table, first application and initial OTA metadata. NVS is preserved.'
& $Python -m esptool --chip esp32 --port $Port --baud 115200 write-flash --flash-mode dio --flash-freq 40m --flash-size 4MB `
    0x1000 (Join-Path $OtaRelease 'bootloader.bin') `
    0x8000 (Join-Path $OtaRelease 'partition-table.bin') `
    0x10000 (Join-Path $OtaRelease 'navsphere.bin') `
    0x3F0000 (Join-Path $OtaRelease 'ota_data_initial.bin')
if ($LASTEXITCODE -ne 0) { throw "Migration failed; preserve the backup at $OtaBackup for USB recovery" }
Write-Host "Migration written and verified by esptool. Open /ota and wait for a live chip report. Backup: $OtaBackup"
