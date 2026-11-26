# Builds dist\MacLikeKeyboard.exe: a single file that runs without Python installed.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Step {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}

# A separate environment, so the exe only contains what the program needs.
$python = "build\venv\Scripts\python.exe"
if (-not (Test-Path $python)) { Invoke-Step python @("-m", "venv", "build\venv") }
Invoke-Step $python @("-m", "pip", "install", "--quiet", "pillow", "pyinstaller")

# The name must not start with "PowerToys": the program closes every process whose name does.
Invoke-Step $python @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "MacLikeKeyboard",
    "--add-data", "$PSScriptRoot\locales;locales",
    "--add-data", "$PSScriptRoot\assets\icon.ico;assets",
    "--icon", "$PSScriptRoot\assets\icon.ico",
    "--specpath", "build", "--workpath", "build\work", "--distpath", "dist",
    "app.py"
)
