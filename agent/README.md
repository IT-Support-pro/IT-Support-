# HBK IT Monitoring Agent (Windows 10/11)

**Internal IT Operations & Deployment Guide**  
Target Environment: ~50 Retail Hypermarket Point-of-Sale (POS) Terminals & PCs running Windows 10/11.

---

## 1. Core Architecture & Non-Intrusive Principles

1. **Strictly Outbound Only**: The agent initiates HTTP POST requests out to the HBK Gateway. It **never** binds to any local listening port and accepts **no** inbound connections.
2. **Read-Only V1 Guardrail**: The agent **cannot** execute remote commands, run remote scripts, download arbitrary files, or open a remote shell.
3. **Low Resource Footprint & Parallel Collections**:
   - Memory consumption: < 50 MB RAM
   - CPU utilization: < 1% CPU
   - Collection runtime: All collectors run concurrently in parallel with a 3.0s per-collector timeout; the entire collection completes under 2.0 seconds.

---

## 2. Directory Structure

```
C:\Program Files\HBKAgent\
├── agent.exe               # Standalone compiled executable (PyInstaller)
├── config.toml             # Configuration file
├── token.dat               # Cryptographic device token (SYSTEM/Admin only)
└── hbk_agent.log           # Rotating log file (max 5 MB x 3)
```

---

## 3. Configuration (`config.toml`)

```toml
[gateway]
url = "http://192.168.1.10:8000"     # IP or hostname of the central gateway
verify_tls = true

[device]
device_id = "POS-12"                  # Unique terminal ID (e.g., POS-01 to POS-50)
store = "ISL-01"                      # Retail store code
device_type = "POS"                   # POS, PC, PRINTER, or SERVER
enrollment_key = "HBK-XXXX-YYYY"      # One-time enrollment key (automatically blanked after first register)

[collect]
heartbeat_sec = 30                    # Heartbeat interval in seconds (tiny status payload)
metrics_sec = 900                     # Full telemetry ingestion interval in seconds (15 minutes)
services = ["Spooler"]                # Monitored Windows services (e.g. "Spooler", "SAPCCOService")
ping_targets = ["8.8.8.8", "1.1.1.1"] # External verification hosts

# Physical Printer Filtering
ignore_printers = ["OneNote", "Microsoft", "XPS", "PDF", "Fax", "AnyDesk", "RustDesk", "Send To"]
ignore_ports = ["nul:", "PORTPROMPT:", "SHRFAX:", "FILE:", "AD_Port", "RustDesk Printer"]

[fbr]
url = "https://fbr.gov.pk"            # Fiscal invoice server URL (or leave empty if not configured)
timeout_sec = 5
check_sec = 300                       # Checked every 5 minutes and included in every 30s heartbeat

[limits]
max_buffer_mb = 20                    # Maximum offline telemetry buffer size
```

---

## 4. Key Subsystems

### A. Accurate Network Information
- **True Device IP**: Resolved dynamically by opening a connectionless UDP socket to the gateway host and inspecting the local address chosen by the Windows routing table. Never reports `169.254.x.x` (APIPA) or `127.x.x.x` (loopback).
- **UP Adapter Discovery**: Enumerates only active interfaces with IPv4, MAC address, link speed, subnet mask, default gateway, DNS servers, and DHCP status. Flags virtual adapters (VMware, VirtualBox, Hyper-V, VPN, Bluetooth) and tags the primary adapter.
- **Firewall-Proof Internet Check**: Uses TCP 443 socket connection or HTTPS GET; does not rely solely on ICMP pings which are often blocked.

### B. POS Date, Time, and Clock Drift
- Reports local ISO 8601 time with offset, UTC time, Windows timezone name (`Pakistan Standard Time`), and system uptime.
- The gateway computes `clock_offset_sec = agent_utc - gateway_utc` and raises alerts if drift exceeds 120s or timezone mismatches.

### C. FBR Fiscal Portal Connectivity
- Evaluates DNS resolution, TCP handshake, and HTTPS request against `[fbr].url`.
- Any HTTP status code (including 401 or 404) denotes the server is reachable; only timeouts, DNS, or TLS failures trigger `fbr_down` after 2 consecutive failures.

### D. Physical Printer Filtering
- Filters out virtual/driver printers (PDF, XPS, Fax, OneNote, AnyDesk).
- Deduplicates duplicate printer instances (`Copy of 1`) sharing the same driver and port.

---

## 5. Run Modes

### A. One-Shot Collection (Verification Mode)
```powershell
.\agent.exe --once
```

### B. Windows Service (Production Mode)
```powershell
# Install Windows Service
.\agent.exe --service --config "C:\Program Files\HBKAgent\config.toml"
```
