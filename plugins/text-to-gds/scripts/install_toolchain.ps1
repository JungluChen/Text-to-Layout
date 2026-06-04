param(
    [switch]$InstallJulia,
    [switch]$InstallJoSIM,
    [switch]$InstallKLayout,
    [string]$JuliaVersion = "1.12.6",
    [string]$JoSIMVersion = "v2.7",
    [string]$KLayoutVersion = "0.30.9",
    [string]$KLayoutFlavor = "win64",
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
        curl.exe -L --fail --retry 3 -C - --output $OutFile $Uri
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Write-Host "Resume failed for $OutFile; downloading a fresh copy."
        Remove-Item -LiteralPath $OutFile -Force
    }
    curl.exe -L --fail --retry 3 --output $OutFile $Uri
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $Uri"
    }
}

function Test-ArchiveExists {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "Expected archive was not downloaded: $Path"
    }
}

function Test-CommandSucceeded {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    $global:LASTEXITCODE = $null
    & $Executable @Arguments
    if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) {
        throw "Command failed: $Executable $($Arguments -join ' ')"
    }
}

function Install-Julia {
    param([string]$Version)

    $archiveName = "julia-$Version-win64.zip"
    $archivePath = Join-Path $toolsPath.FullName $archiveName
    $installPath = Join-Path $toolsPath.FullName "julia-$Version"
    $downloadUrl = "https://julialang-s3.julialang.org/bin/winnt/x64/1.12/$archiveName"

    Download-File -Uri $downloadUrl -OutFile $archivePath
    Test-ArchiveExists -Path $archivePath
    if (-not (Test-Path $installPath)) {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $toolsPath.FullName -Force
    }

    $julia = Join-Path $installPath "bin\julia.exe"
    if (-not (Test-Path $julia)) {
        throw "Julia executable not found after install: $julia"
    }

    $env:JULIA_DEPOT_PATH = Join-Path $toolsPath.FullName "julia-depot"
    & $julia -e 'using Pkg; Pkg.add(url="https://github.com/kpobrien/JosephsonCircuits.jl"); using JosephsonCircuits; println("JosephsonCircuits loaded")'
    Test-CommandSucceeded -Executable $julia -Arguments @("--version")
}

function Install-JoSIM {
    param([string]$Version)

    $plainVersion = $Version.TrimStart("v")
    $archiveName = "JoSIM-v$plainVersion-windows-x64.zip"
    $archivePath = Join-Path $toolsPath.FullName $archiveName
    $installPath = Join-Path $toolsPath.FullName "josim-v$plainVersion"
    $downloadUrl = "https://github.com/JoeyDelp/JoSIM/releases/download/v$plainVersion/$archiveName"

    Download-File -Uri $downloadUrl -OutFile $archivePath
    Test-ArchiveExists -Path $archivePath
    if (-not (Test-Path $installPath)) {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $installPath -Force
    }

    $josim = Join-Path $installPath "bin\josim-cli.exe"
    if (-not (Test-Path $josim)) {
        throw "JoSIM executable not found after install: $josim"
    }
    Test-CommandSucceeded -Executable $josim -Arguments @("--version")
}

function Install-KLayout {
    param(
        [string]$Version,
        [string]$Flavor
    )

    $archiveName = "klayout-$Version-$Flavor.zip"
    $archivePath = Join-Path $toolsPath.FullName $archiveName
    $installPath = Join-Path $toolsPath.FullName "klayout-$Version-$Flavor"
    $downloadUrl = "https://www.klayout.org/downloads/Windows/$archiveName"

    Download-File -Uri $downloadUrl -OutFile $archivePath
    Test-ArchiveExists -Path $archivePath
    if (-not (Test-Path $installPath)) {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $installPath -Force
    }

    $klayout = Join-Path $installPath "klayout_app.exe"
    if (-not (Test-Path $klayout)) {
        $candidate = Get-ChildItem -Path $installPath -Recurse -Filter "klayout_app.exe" |
            Select-Object -First 1
        if ($candidate) {
            $klayout = $candidate.FullName
        }
    }
    if (-not (Test-Path $klayout)) {
        throw "KLayout executable not found after install: $klayout"
    }
    Test-CommandSucceeded -Executable $klayout -Arguments @("-b", "-h")
}

if (-not $InstallJulia -and -not $InstallJoSIM -and -not $InstallKLayout) {
    $InstallJulia = $true
    $InstallJoSIM = $true
    $InstallKLayout = $true
}

if ($InstallJulia) {
    Install-Julia -Version $JuliaVersion
}
if ($InstallJoSIM) {
    Install-JoSIM -Version $JoSIMVersion
}
if ($InstallKLayout) {
    Install-KLayout -Version $KLayoutVersion -Flavor $KLayoutFlavor
}

Write-Host "Installed Text-to-GDS toolchain under $($toolsPath.FullName)"
