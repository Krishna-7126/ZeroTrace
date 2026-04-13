param(
    [string]$Entry = "main.py",
    [string]$Name = "ZeroTrace"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\\.venv\\Scripts\\python.exe")) {
    throw "Virtual environment not found at .venv. Create it first."
}

& ".\\.venv\\Scripts\\python.exe" -m pip install --upgrade pip
& ".\\.venv\\Scripts\\python.exe" -m pip install -r requirements.txt
& ".\\.venv\\Scripts\\python.exe" -m pip install -r requirements-dev.txt

& ".\\.venv\\Scripts\\python.exe" -m PyInstaller --noconfirm --clean --windowed --name $Name $Entry

Write-Host "Build complete. Output folder: .\\dist\\$Name"
