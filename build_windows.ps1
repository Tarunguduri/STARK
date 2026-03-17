param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Building STARK for Windows..." -ForegroundColor Cyan

if ($Clean) {
    if (Test-Path ".\\build") { Remove-Item ".\\build" -Recurse -Force }
    if (Test-Path ".\\dist") { Remove-Item ".\\dist" -Recurse -Force }
}

.\\stark_venv\\Scripts\\python.exe -m pip install -r requirements_build.txt
.\\stark_venv\\Scripts\\python.exe -m PyInstaller --noconfirm .\\stark_windows.spec

if (-not (Test-Path ".\\release")) {
    New-Item -ItemType Directory -Path ".\\release" | Out-Null
}

$innoCandidates = @(
    "${env:ProgramFiles(x86)}\\Inno Setup 6\\ISCC.exe",
    "$env:ProgramFiles\\Inno Setup 6\\ISCC.exe",
    "$env:LOCALAPPDATA\\Programs\\Inno Setup 6\\ISCC.exe"
)
$iscc = ($innoCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1)
if (-not $iscc) {
    $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
}

if ($iscc) {
    Write-Host "Building installer with Inno Setup..." -ForegroundColor Cyan
    & $iscc ".\\stark_installer.iss"
    Write-Host "Installer complete. Output: .\\release\\" -ForegroundColor Green
} else {
    Write-Host "PyInstaller build complete. Inno Setup not found, so installer was skipped." -ForegroundColor Yellow
}

$releaseZip = ".\\release\\STARK_Windows.zip"
if (Test-Path $releaseZip) {
    Remove-Item $releaseZip -Force
}

$installer = Get-ChildItem ".\\release\\STARK_Setup_*.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($installer) {
    Write-Host "Creating shareable ZIP from installer..." -ForegroundColor Cyan
    Compress-Archive -Path $installer.FullName -DestinationPath $releaseZip -Force
    Write-Host "ZIP ready: $releaseZip" -ForegroundColor Green
} elseif (Test-Path ".\\dist\\STARK") {
    Write-Host "Creating shareable ZIP from app folder..." -ForegroundColor Cyan
    Compress-Archive -Path ".\\dist\\STARK" -DestinationPath $releaseZip -Force
    Write-Host "ZIP ready: $releaseZip" -ForegroundColor Green
} else {
    Write-Host "No release asset found to zip." -ForegroundColor Yellow
}

Write-Host "App output: .\\dist\\STARK\\" -ForegroundColor Green
