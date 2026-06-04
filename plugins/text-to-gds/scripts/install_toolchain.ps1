param(
    [switch]$InstallJulia,
    [switch]$InstallJoSIM,
    [string]$JuliaVersion = "1.12.6",
    [string]$JoSIMVersion = "v2.7",
    [string]$ToolsRoot = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $ToolsRoot) {
    $ToolsRoot = Join-Path $repoRoot ".tools"
}
$toolsPath = New-Item -ItemType Directory -Force -Path $ToolsRoot

function Download-File {
    param(
        [string]$Uri,
        [string]$OutFile
    )
    if (Test-Path $OutFile) {
        return
    }
    curl.exe -L --fail --retry 3 --output $OutFile $Uri
}

function Install-Julia {
    param([string]$Version)

    $archiveName = "julia-$Version-win64.zip"
    $archivePath = Join-Path $toolsPath.FullName $archiveName
    $installPath = Join-Path $toolsPath.FullName "julia-$Version"
    $downloadUrl = "https://julialang-s3.julialang.org/bin/winnt/x64/1.12/$archiveName"

    Download-File -Uri $downloadUrl -OutFile $archivePath
    if (-not (Test-Path $installPath)) {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $toolsPath.FullName -Force
    }

    $julia = Join-Path $installPath "bin\julia.exe"
    if (-not (Test-Path $julia)) {
        throw "Julia executable not found after install: $julia"
    }

    $env:JULIA_DEPOT_PATH = Join-Path $toolsPath.FullName "julia-depot"
    & $julia -e 'using Pkg; Pkg.add(url="https://github.com/kpobrien/JosephsonCircuits.jl"); using JosephsonCircuits; println("JosephsonCircuits loaded")'
    & $julia --version
}

function Install-JoSIM {
    param([string]$Version)

    $plainVersion = $Version.TrimStart("v")
    $archiveName = "JoSIM-v$plainVersion-windows-x64.zip"
    $archivePath = Join-Path $toolsPath.FullName $archiveName
    $installPath = Join-Path $toolsPath.FullName "josim-v$plainVersion"
    $downloadUrl = "https://github.com/JoeyDelp/JoSIM/releases/download/v$plainVersion/$archiveName"

    Download-File -Uri $downloadUrl -OutFile $archivePath
    if (-not (Test-Path $installPath)) {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $installPath -Force
    }

    $josim = Join-Path $installPath "bin\josim-cli.exe"
    if (-not (Test-Path $josim)) {
        throw "JoSIM executable not found after install: $josim"
    }
    & $josim --version
}

if (-not $InstallJulia -and -not $InstallJoSIM) {
    $InstallJulia = $true
    $InstallJoSIM = $true
}

if ($InstallJulia) {
    Install-Julia -Version $JuliaVersion
}
if ($InstallJoSIM) {
    Install-JoSIM -Version $JoSIMVersion
}

Write-Host "Installed Text-to-GDS toolchain under $($toolsPath.FullName)"
