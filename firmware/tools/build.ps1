param([string]$IdfPath = 'C:\esp\v6.0.2\esp-idf', [string]$ToolsPath = 'C:\Espressif\tools', [string[]]$IdfArguments = @('build'), [string]$ProjectDirectory = '')
$ErrorActionPreference = 'Stop'
$env:IDF_PATH = $IdfPath
$env:IDF_TOOLS_PATH = $ToolsPath
$env:ESP_IDF_VERSION = '6.0.2'
$env:IDF_VERSION = 'v6.0.2'
$env:IDF_TARGET = 'esp32'
$env:ESP_ROM_ELF_DIR = Join-Path $ToolsPath 'esp-rom-elfs\20241011'
$env:IDF_PYTHON_ENV_PATH = Join-Path $ToolsPath 'python\v6.0.2\venv'
$toolDirectories = @('cmake\4.0.3\bin', 'ninja\1.12.1', 'xtensa-esp-elf\esp-15.2.0_20251204\xtensa-esp-elf\bin', 'python\v6.0.2\venv\Scripts')
$env:PATH = (($toolDirectories | ForEach-Object { Join-Path $ToolsPath $_ }) -join ';') + ';' + $env:PATH
$python = Join-Path $env:IDF_PYTHON_ENV_PATH 'Scripts\python.exe'
if (-not $ProjectDirectory) { $ProjectDirectory = Split-Path $PSScriptRoot -Parent }
$ResolvedProjectDirectory = (Resolve-Path -LiteralPath $ProjectDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path $ResolvedProjectDirectory 'CMakeLists.txt'))) {
    throw "ESP-IDF project CMakeLists.txt not found: $ResolvedProjectDirectory"
}
Push-Location $ResolvedProjectDirectory
try {
    & $python (Join-Path $IdfPath 'tools\idf.py') @IdfArguments
    if ($LASTEXITCODE -ne 0) { throw "ESP-IDF failed ($LASTEXITCODE)" }
} finally { Pop-Location }
