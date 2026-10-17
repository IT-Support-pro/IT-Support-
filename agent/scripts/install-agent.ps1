# ==============================================================================
# HBK IT Monitoring Agent - Silent Windows Installer
# Run as Administrator in PowerShell:
# .\install-agent.ps1 -DeviceId POS-12 -Store ISL-01 -Gateway http://192.168.1.10:8000 -EnrollmentKey XXXX -Type POS
# ==============================================================================
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DeviceId,
    [Parameter(Mandatory=$true)][string]$Store,
    [Parameter(Mandatory=$true)][string]$Gateway,
    [Parameter(Mandatory=$true)][string]$EnrollmentKey,
    [Parameter(Mandatory=$false)][string]$Type = "POS",
    [Parameter(Mandatory=$false)][string]$InstallDir = "C:\Program Files\HBKAgent"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " HBK IT Monitoring Agent - Silent Windows Deployment" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check Administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "[!] Error: Administrator privileges are required to install HBKAgent service."
    exit 1
}

# 1. Create Target Directory
Write-Host "[*] Creating target directory: $InstallDir"
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# 2. Copy Agent Executable or Source
$sourceDir = $PSScriptRoot
$exePath = Join-Path $sourceDir "..\agent.exe"
$targetExe = Join-Path $InstallDir "agent.exe"

if (Test-Path $exePath) {
    Write-Host "[*] Copying binary agent.exe..."
    Copy-Item -Path $exePath -Destination $targetExe -Force
} else {
    Write-Host "[-] Note: agent.exe binary not found in source directory; copying Python files for script execution."
    Copy-Item -Path "$sourceDir\..\*" -Destination $InstallDir -Recurse -Force
}

# 3. Generate config.toml
$configPath = Join-Path $InstallDir "config.toml"
Write-Host "[*] Writing config.toml..."
$configContent = @"
[gateway]
url = "$Gateway"
verify_tls = true

[device]
device_id = "$DeviceId"
store = "$Store"
device_type = "$Type"
enrollment_key = "$EnrollmentKey"

[collect]
heartbeat_sec = 30
metrics_sec = 60
services = ["Spooler"]
ping_targets = ["8.8.8.8", "1.1.1.1"]

[limits]
max_buffer_mb = 20
"@

Set-Content -Path $configPath -Value $configContent -Encoding UTF8

# 4. Protect Permissions (SYSTEM and Administrators only)
Write-Host "[*] Hardening file permissions on $InstallDir..."
try {
    & icacls "$InstallDir" /inheritance:r /grant:r "Administrators":(OI)(CI)F /grant:r "SYSTEM":(OI)(CI)F | Out-Null
} catch {
    Write-Warning "Could not set strict icacls: $_"
}

# 5. Install Windows Service 'HBKAgent'
$serviceName = "HBKAgent"
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue

if ($existingService) {
    Write-Host "[*] Existing $serviceName service found. Stopping and removing..."
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    & sc.exe delete $serviceName | Out-Null
    Start-Sleep -Seconds 2
}

Write-Host "[*] Creating Windows Service '$serviceName'..."
$binPath = "`"$targetExe`" --service --config `"$configPath`""

# Use sc.exe to create service set to auto start
& sc.exe create $serviceName binPath= $binPath start= auto DisplayName= "HBK IT Monitoring Agent" | Out-Null
& sc.exe description $serviceName "Outbound telemetry monitor for HBK retail hypermarket POS terminals." | Out-Null

# Configure Restart-on-failure recovery (restart after 30 s on failure: actions= restart/30000/restart/30000/restart/30000 reset= 86400)
& sc.exe failure $serviceName reset= 86400 actions= restart/30000/restart/30000/restart/30000 | Out-Null

# 6. Start Service
Write-Host "[*] Starting $serviceName service..."
Start-Service -Name $serviceName
Start-Sleep -Seconds 2

# 7. Print Status
$svcStatus = Get-Service -Name $serviceName
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "[✓] Deployment Complete!" -ForegroundColor Green
Write-Host "    - Service Name: $($svcStatus.Name)" -ForegroundColor Green
Write-Host "    - Status:       $($svcStatus.Status)" -ForegroundColor Green
Write-Host "    - Startup Type: $($svcStatus.StartType)" -ForegroundColor Green
Write-Host "    - Firewall:     Zero inbound ports opened (strictly outbound HTTP)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
