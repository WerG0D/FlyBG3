[CmdletBinding()]
param(
    [string]$DivineExe = $env:DIVINE_EXE,
    [string]$Output = ""
)
$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repository "bg3-mod\FlyBG3"
if (-not $Output) { $Output = Join-Path $repository "build\FlyBG3.pak" }
$Output = [System.IO.Path]::GetFullPath($Output)
if (-not $DivineExe) { $DivineExe = "C:\tools\LSLib\Packed\Tools\Divine.exe" }
$DivineExe = [System.IO.Path]::GetFullPath($DivineExe)
if (-not (Test-Path -LiteralPath $DivineExe -PathType Leaf)) {
    throw "Divine.exe not found at '$DivineExe'. Install LSLib and pass -DivineExe or set DIVINE_EXE."
}
if (-not (Test-Path -LiteralPath (Join-Path $source "Mods\FlyBG3\meta.lsx") -PathType Leaf)) {
    throw "FlyBG3 source is incomplete: $source"
}
$parent = Split-Path -Parent $Output
New-Item -ItemType Directory -Path $parent -Force | Out-Null
& $DivineExe -g bg3 -s $source -d $Output -a create-package
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Output -PathType Leaf)) {
    throw "Divine.exe failed to build FlyBG3.pak (exit $LASTEXITCODE)."
}
Write-Host "Built: $Output"
