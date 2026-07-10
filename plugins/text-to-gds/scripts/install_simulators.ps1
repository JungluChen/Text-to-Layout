# One-command simulator bootstrap (PowerShell wrapper).
# Usage: .\scripts\install_simulators.ps1 [--detect-only] [--strict]
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = $env:PYTHON
if (-not $python) {
    $candidate = Get-Command python -ErrorAction SilentlyContinue
    if ($candidate) { $python = $candidate.Source } else { $python = "py" }
}
& $python (Join-Path $scriptDir "bootstrap_simulators.py") @args
exit $LASTEXITCODE
