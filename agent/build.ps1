# ==============================================================================
# HBK IT Monitoring Agent - Build Script
# Compiles agent into standalone single-file agent.exe using PyInstaller
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Building standalone agent.exe (PyInstaller --onefile)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify PyInstaller is installed
$hasPyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $hasPyinstaller) {
    Write-Host "[*] Installing build requirements..."
    pip install pyinstaller psutil requests tomli
}

# 2. Run PyInstaller
# Notes on Antivirus False Positives:
# - Standalone PyInstaller binaries unpack into a temp folder at runtime. Generic heuristics
#   in Windows Defender / Symantec / CrowdStrike may flag new unsigned binaries as false positives.
# - Resolution for Pilot:
#   1. Sign the output binary with the retail company's internal code-signing certificate:
#      signtool sign /f HBK_Cert.pfx /p <password> /t http://timestamp.digicert.com dist\agent.exe
#   2. Or add an exclusion in Windows Defender / EDR for "C:\Program Files\HBKAgent\agent.exe".
Write-Host "[*] Running PyInstaller compiler..."
pyinstaller --onefile `
    --name "agent" `
    --clean `
    --hidden-import "psutil" `
    --hidden-import "requests" `
    --hidden-import "tomllib" `
    --hidden-import "collectors.system" `
    --hidden-import "collectors.network" `
    --hidden-import "collectors.printer" `
    --hidden-import "collectors.services" `
    main.py

if (Test-Path "dist\agent.exe") {
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "[✓] Build Succeeded: dist\agent.exe created!" -ForegroundColor Green
    Write-Host "    Size: $([math]::round((Get-Item dist\agent.exe).Length / 1MB, 2)) MB" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Error "[!] Build failed. Inspect terminal output."
}
