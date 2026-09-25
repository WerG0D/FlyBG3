param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $root 'dashboard')
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
    npm run dev
} finally { Pop-Location }
