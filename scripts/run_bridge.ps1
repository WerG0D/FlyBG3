[CmdletBinding()]
param([string]$Config = "config\default.toml", [switch]$Debug)
$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repository ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Virtual environment not found. Create .venv with Python 3.11-3.13 and install -e ."
}
$configPath = Join-Path $repository $Config
$arguments = @("-m", "flybg3", "--config", $configPath)
if ($Debug) { $arguments += "--debug" }
& $python @arguments
