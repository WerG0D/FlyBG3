[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Pak = "",
    [string]$ModsDirectory = "",
    [switch]$Force
)
$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
if (-not $Pak) { $Pak = Join-Path $repository "build\FlyBG3.pak" }
if (-not $ModsDirectory) {
    if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is unavailable; pass -ModsDirectory." }
    $ModsDirectory = Join-Path $env:LOCALAPPDATA "Larian Studios\Baldur's Gate 3\Mods"
}
$Pak = [System.IO.Path]::GetFullPath($Pak)
$ModsDirectory = [System.IO.Path]::GetFullPath($ModsDirectory)
if (Get-Process -Name bg3,bg3_dx11 -ErrorAction SilentlyContinue) {
    throw "Baldur's Gate 3 is running. Close the game before replacing FlyBG3.pak."
}
if (-not (Test-Path -LiteralPath $Pak -PathType Leaf)) {
    throw "Package not found: $Pak. Run scripts\build_mod.ps1 first."
}
New-Item -ItemType Directory -Path $ModsDirectory -Force | Out-Null
$target = Join-Path $ModsDirectory "FlyBG3.pak"
if ((Test-Path -LiteralPath $target) -and -not $Force) {
    throw "Refusing to overwrite existing '$target'. Pass -Force to replace only that package."
}
if ($PSCmdlet.ShouldProcess($target, "Install FlyBG3 package")) {
    Copy-Item -LiteralPath $Pak -Destination $target -Force:$Force
    Write-Host "Installed: $target"
    Write-Host "Enable FlyBG3 in BG3 Mod Manager or the in-game Mod Manager before loading a save."
}
