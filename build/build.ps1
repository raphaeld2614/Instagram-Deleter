# Builds the Instagram Deleter into a distributable Windows app.
#
#   1. Creates an isolated virtual environment (.venv)
#   2. Installs runtime dependencies + PyInstaller
#   3. Runs PyInstaller (onedir, windowed) -> dist\InstagramDeleter\
#   4. Wraps it in an Inno Setup installer if iscc.exe is available,
#      otherwise zips the folder as a fallback.
#
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File build\build.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "Project root: $root" -ForegroundColor Cyan

# --- 1. virtual environment ---
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
}

# --- 2. dependencies ---
Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Installing requirements failed." }
& $venvPy -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Installing PyInstaller failed." }

# --- 3. build ---
Write-Host "Running PyInstaller..." -ForegroundColor Cyan
& $venvPy -m PyInstaller build\unliker.spec --noconfirm --distpath dist --workpath build\_work
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$appDir = Join-Path $root "dist\InstagramDeleter"
if (-not (Test-Path (Join-Path $appDir "InstagramDeleter.exe"))) {
    throw "Build did not produce InstagramDeleter.exe."
}
Write-Host "Build succeeded: $appDir" -ForegroundColor Green

# --- 4. installer or zip fallback ---
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $default = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $default) { $iscc = $default }
}

if ($iscc) {
    Write-Host "Building installer with Inno Setup..." -ForegroundColor Cyan
    & $iscc "build\installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
    Write-Host "Installer created: dist\InstagramDeleter-Setup.exe" -ForegroundColor Green
} else {
    Write-Host "Inno Setup (iscc.exe) not found - creating a zip fallback instead." -ForegroundColor Yellow
    $zip = Join-Path $root "dist\InstagramDeleter.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    # Freshly written files can be briefly locked by antivirus scanning; retry.
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Compress-Archive -Path (Join-Path $appDir "*") -DestinationPath $zip -ErrorAction Stop
            break
        } catch {
            if ($attempt -eq 3) { throw }
            Write-Host "Zip locked (attempt $attempt) - retrying..." -ForegroundColor Yellow
            Start-Sleep -Seconds 3
        }
    }
    Write-Host "Created: $zip" -ForegroundColor Green
}

Write-Host "Done." -ForegroundColor Green
