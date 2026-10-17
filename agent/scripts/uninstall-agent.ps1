# ==============================================================================
# HBK IT Monitoring Agent - Uninstallation Script
# Run as Administrator in PowerShell: .\uninstall-agent.ps1
# ==============================================================================
[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)][string]$InstallDir = "C:\Program Files\HBKAgent"
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host " HBK IT Monitoring Agent - Uninstaller" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$serviceName = "HBKAgent"

# 1. Stop and Delete Service
$svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host "[*] Stopping service $serviceName..."
    Stop-Service -Name $serviceName -Force
    Start-Sleep -Seconds 2

    Write-Host "[*] Deleting service $serviceName..."
    & sc.exe delete $serviceName | Out-Null
}

# 2. Remove Files
if (Test-Path $InstallDir) {
    Write-Host "[*] Removing directory $InstallDir..."
    Remove-Item -Path $InstallDir -Recurse -Force
}

Write-Host "[✓] HBKAgent uninstallation complete." -ForegroundColor Green
