# Hermes AI Integration API Reference

The **HBK Gateway Hermes API** provides a high-efficiency, read-only interface specifically optimized for Hermes AI running on IT laptops.

---

## Authentication & Security Rules
- **Header:** `X-API-Key: <HERMES_API_KEY>`
- **Constant-Time Verification:** Keys are verified using timing-attack-safe comparison (`secrets.compare_digest`). Invalid or missing keys return `401 Unauthorized`.
- **Strictly Read-Only:** All endpoints use HTTP `GET`. No write operations, shell execution, or remote actions exist.
- **Audit Log:** Every Hermes API invocation is automatically recorded in the `audit_logs` table with `actor_type="hermes"` and client IP.
- **Rate Limit:** 60 requests/minute per key (returns `429 Too Many Requests` on breach).
- **Zero Secret Exposure:** Tokens, hashes, passwords, and enrollment keys are stripped from all responses.

---

## Endpoint Reference & `curl` Examples

Set your environment variables before testing:
```bash
export GATEWAY_URL="http://localhost:8000"
export HERMES_KEY="hbk-hermes-secret-key-pilot-2026"
```

### 1. Overall System Summary
Compact overview of hypermarket store counts, online/offline terminals, and firing alerts.
```bash
curl -s -X GET "$GATEWAY_URL/api/v1/hermes/summary" \
  -H "X-API-Key: $HERMES_KEY" | jq
```
**Example Response:**
```json
{
  "stores": 1,
  "devices_total": 48,
  "online": 46,
  "offline": 2,
  "degraded": 0,
  "firing_alerts": 3,
  "critical_alerts": 2,
  "generated_at": "2026-10-13T09:30:00Z"
}
```

---

### 2. Stores Health Overview
Lists retail hypermarket branches with terminal counts and active alerts.
```bash
curl -s -X GET "$GATEWAY_URL/api/v1/hermes/stores" \
  -H "X-API-Key: $HERMES_KEY" | jq
```
**Example Response:**
```json
[
  {
    "id": 1,
    "code": "ISL-01",
    "name": "Islamabad Flagship Hypermarket",
    "region": "North Region",
    "devices_total": 48,
    "online_count": 46,
    "offline_count": 2,
    "active_alerts": 3
  }
]
```

---

### 3. Filter Terminals & Devices
Retrieve devices with optional store, status, type, and keyword search filters (max 100).
```bash
curl -s -X GET "$GATEWAY_URL/api/v1/hermes/devices?store=ISL-01&status=OFFLINE" \
  -H "X-API-Key: $HERMES_KEY" | jq
```
**Example Response:**
```json
[
  {
    "device_id": "POS-12",
    "computer_name": "POS12-CASHIER",
    "store": "ISL-01",
    "type": "POS",
    "ip": "192.168.1.112",
    "status": "OFFLINE",
    "last_seen": "2026-10-13T09:18:24Z",
    "agent_version": "1.0.0"
  }
]
```

---

### 4. Device Detailed Telemetry
Full diagnostic context for a terminal: metadata, latest snapshot, active alerts, last 5 resolved alerts, and technician notes.
```bash
curl -s -X GET "$GATEWAY_URL/api/v1/hermes/devices/POS-12" \
  -H "X-API-Key: $HERMES_KEY" | jq
```
**Example Response:**
```json
{
  "device_id": "POS-12",
  "computer_name": "POS12-CASHIER",
  "store": "ISL-01",
  "device_type": "POS",
  "ip_address": "192.168.1.112",
  "os_version": "Windows 11 Enterprise LTSC",
  "agent_version": "1.0.0",
  "status": "OFFLINE",
  "last_seen": "2026-10-13T09:18:24Z",
  "registered_at": "2026-10-13T08:00:00Z",
  "latest_metrics": {
    "ts": "2026-10-13T09:18:24Z",
    "cpu_pct": 24.2,
    "ram_pct": 58.1,
    "ram_used_mb": 4650.0,
    "disks": [{"mount": "C:", "total_gb": 238, "used_gb": 150, "free_gb": 88, "pct": 63}],
    "internet_ok": true
  },
  "active_alerts": [
    {
      "id": 14,
      "rule_key": "agent_offline",
      "severity": "critical",
      "state": "FIRING",
      "message": "POS offline",
      "fired_at": "2026-10-13T09:20:00Z"
    }
  ],
  "resolved_alerts": [],
  "notes": []
}
```

---

### 5. Downsampled Metrics Time Series
Downsampled series for CPU, RAM, primary disk, and internet connectivity (capped at 100 points maximum).
```bash
curl -s -X GET "$GATEWAY_URL/api/v1/hermes/devices/POS-12/metrics?minutes=60&step=5" \
  -H "X-API-Key: $HERMES_KEY" | jq
```
**Example Response:**
```json
{
  "device_id": "POS-12",
  "window_minutes": 60,
  "step_minutes": 5,
  "points_count": 12,
  "series": [
    {
      "ts": "2026-10-13T08:30:00Z",
      "cpu_pct": 19.5,
      "ram_pct": 56.2,
      "disk_pct": 63.0,
      "internet_ok": true
    }
  ]
}
```

---

### 6. Filter Active Alerts
Query alerts with status, severity, store, or device filters.
```bash
curl -s -X GET "$GATEWAY_URL/api/v1/hermes/alerts?state=FIRING&severity=critical" \
  -H "X-API-Key: $HERMES_KEY" | jq
```
**Example Response:**
```json
[
  {
    "id": 14,
    "device_id": "POS-12",
    "store": "ISL-01",
    "rule_key": "agent_offline",
    "severity": "critical",
    "state": "FIRING",
    "message": "POS offline",
    "fired_at": "2026-10-13T09:20:00Z"
  }
]
```

---

### 7. Plain-English Summary Paragraph
Pre-synthesized natural language description ready for direct LLM comprehension and voice summaries.
```bash
curl -s -X GET "$GATEWAY_URL/api/v1/hermes/devices/POS-12/summary_text" \
  -H "X-API-Key: $HERMES_KEY" | jq
```
**Example Response:**
```json
{
  "device_id": "POS-12",
  "store": "ISL-01",
  "status": "OFFLINE",
  "summary": "POS-12 at ISL-01 is OFFLINE since 09:18 (last seen 12 min ago). Active alerts (1): [CRITICAL] POS offline. Latest telemetry (09:18): CPU 24.2%, RAM 58.1% (4650 MB). Disk C: at 63%."
}
```
