[CmdletBinding()]
param(
    [string]$DivineExe = $env:DIVINE_EXE,
    [string]$Output = ""
)
$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repository "bg3-mod\FlyBG3Arena"
$folder = "FlyBG3Arena_00a41563-37f2-988d-98c9-5ca9bb65423a"
if (-not $Output) { $Output = Join-Path $repository "build\FlyBG3Arena.pak" }
if (-not $DivineExe) { throw "Pass -DivineExe or set DIVINE_EXE to the installed LSLib Divine.exe." }
$DivineExe = [System.IO.Path]::GetFullPath($DivineExe)
$Output = [System.IO.Path]::GetFullPath($Output)
if (-not (Test-Path -LiteralPath $DivineExe -PathType Leaf)) {
    throw "Divine.exe not found at '$DivineExe'. Pass -DivineExe or set DIVINE_EXE."
}
$meta = Join-Path $source "Mods\$folder\meta.lsx"
$level = Join-Path $source "Mods\$folder\Levels\Basic_Level_A"
if (-not (Test-Path -LiteralPath $meta -PathType Leaf)) { throw "Arena metadata missing: $meta" }
[xml]$metadata = Get-Content -LiteralPath $meta
$moduleId = $metadata.save.region.node.children.node |
    Where-Object id -eq "ModuleInfo" |
    ForEach-Object { ($_.attribute | Where-Object id -eq "UUID").value }
if ($moduleId -ne "00a41563-37f2-988d-98c9-5ca9bb65423a") {
    throw "Arena metadata UUID mismatch: $moduleId"
}
if (-not (Test-Path -LiteralPath $level -PathType Container)) { throw "Arena level missing: $level" }
$items = @(Get-ChildItem -LiteralPath (Join-Path $level "Items") -Filter "*.lsf" -File)
$characters = @(Get-ChildItem -LiteralPath (Join-Path $level "Characters") -Filter "*.lsf" -File)
if ($items.Count -lt 4 -or $characters.Count -lt 1) {
    throw "Arena incomplete: $($items.Count) items, $($characters.Count) characters."
}
New-Item -ItemType Directory -Path (Split-Path -Parent $Output) -Force | Out-Null
& $DivineExe -g bg3 -s $source -d $Output -a create-package
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Output -PathType Leaf)) {
    throw "Divine.exe failed to build FlyBG3Arena.pak."
}
$entries = @(& $DivineExe -g bg3 -s $Output -a list-package)
if ($LASTEXITCODE -ne 0 -or @($entries | Where-Object { $_ -match "Levels/Basic_Level_A/" }).Count -lt 5) {
    throw "Built package does not contain the expected arena objects."
}
Write-Host "Built: $Output"
Write-Host "Items: $($items.Count); characters: $($characters.Count); archive entries: $($entries.Count)"
