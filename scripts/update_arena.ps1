[CmdletBinding()]
param(
    [string]$ToolkitData = (Join-Path ${env:ProgramFiles(x86)} 'Steam\steamapps\common\Baldurs Gate 3\Data'),
    [string]$DivineExe = $env:DIVINE_EXE,
    [switch]$BuildOnly
)
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$folder = 'FlyBG3Arena_00a41563-37f2-988d-98c9-5ca9bb65423a'
$source = [System.IO.Path]::GetFullPath((Join-Path $ToolkitData "Mods\$folder")).TrimEnd('\')
$destination = [System.IO.Path]::GetFullPath((Join-Path $repository "bg3-mod\FlyBG3Arena\Mods\$folder")).TrimEnd('\')
$package = Join-Path $repository 'build\FlyBG3Arena.pak'

if (Get-Process -Name bg3,bg3_dx11 -ErrorAction SilentlyContinue) {
    throw "Close Baldur's Gate 3 before updating the arena package."
}
if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Toolkit arena source not found: $source. Pass -ToolkitData with the game Data directory."
}
if (-not (Test-Path -LiteralPath (Join-Path $source 'meta.lsx') -PathType Leaf)) {
    throw "Toolkit arena metadata is missing from $source. Save the project in the Toolkit first."
}
if (-not $DivineExe) {
    throw 'Pass -DivineExe with the path to LSLib Divine.exe, or set DIVINE_EXE.'
}
if (-not $BuildOnly) {
    $installed = Join-Path $env:LOCALAPPDATA "Larian Studios\Baldur's Gate 3\Mods\FlyBG3Arena.pak"
    if (Test-Path -LiteralPath $installed -PathType Leaf) {
        try {
            $handle = [System.IO.File]::Open($installed, 'Open', 'ReadWrite', 'None')
            $handle.Close()
        } catch {
            throw "Installed arena PAK is open in another process. Close the Toolkit and BG3, then retry: $installed"
        }
    }
}

$sourceFiles = @(Get-ChildItem -LiteralPath $source -Recurse -File)
$sourcePaths = @{}
foreach ($file in $sourceFiles) {
    $relative = $file.FullName.Substring($source.Length + 1)
    $sourcePaths[$relative] = $true
}
$removed = @(Get-ChildItem -LiteralPath $destination -Recurse -File | Where-Object {
    -not $sourcePaths.ContainsKey($_.FullName.Substring($destination.Length + 1))
})
if ($removed.Count -gt 0) {
    $names = $removed | ForEach-Object { $_.FullName.Substring($destination.Length + 1) }
    throw "Files exist only in the packaged source, possibly deleted in Toolkit. Review them before updating: $($names -join ', ')"
}

$changed = 0
foreach ($file in $sourceFiles) {
    $relative = $file.FullName.Substring($source.Length + 1)
    $target = Join-Path $destination $relative
    if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
        Write-Host "Synced: $relative"
        $changed++
    }
}
Write-Host "Toolkit files updated: $changed"

& (Join-Path $PSScriptRoot 'build_arena.ps1') -DivineExe $DivineExe -Output $package
if (-not $?) { throw 'Arena build failed.' }
if ($BuildOnly) { return }

& (Join-Path $PSScriptRoot 'install_mod.ps1') -PackageName FlyBG3Arena -Pak $package -Force
if (-not $?) { throw 'Arena installation failed.' }
$builtHash = (Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash
$installedHash = (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash
if ($builtHash -ne $installedHash) { throw 'Installed PAK does not match the build.' }
Write-Host "Verified installed PAK SHA-256: $installedHash"
