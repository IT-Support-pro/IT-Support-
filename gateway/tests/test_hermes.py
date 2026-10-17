from datetime import datetime, timezone, timedelta
from app.config import settings
from app.models import AuditLog, Device, Metric, Alert

def test_hermes_auth_missing_or_invalid(client):
    # Missing header -> 401
    res1 = client.get("/api/v1/hermes/summary")
    assert res1.status_code == 401

    # Bad header -> 401
    res2 = client.get("/api/v1/hermes/summary", headers={"X-API-Key": "wrong-key"})
    assert res2.status_code == 401

def test_hermes_auth_success_and_audit(client, db_session, seed_data):
    api_key = settings.HERMES_API_KEY
    res = client.get("/api/v1/hermes/summary", headers={"X-API-Key": api_key})
    assert res.status_code == 200
    data = res.json()
    assert "devices_total" in data
    assert "online" in data
    assert "firing_alerts" in data

    # Verify audit log recorded
    log = db_session.query(AuditLog).filter(
        AuditLog.actor_type == "hermes",
        AuditLog.action == "hermes_read_summary"
    ).first()
    assert log is not None
    assert log.actor == "hermes_ai"

def test_hermes_key_cannot_access_other_routes(client):
    api_key = settings.HERMES_API_KEY
    # Hermes key cannot access admin routes
    res = client.get("/api/v1/admin/users", headers={"X-API-Key": api_key})
    assert res.status_code == 401

    # Hermes key cannot post agent heartbeats
    res_agent = client.post("/api/v1/agent/heartbeat", headers={"X-API-Key": api_key}, json={
        "agent_version": "1.0", "ip_address": "127.0.0.1"
    })
    assert res_agent.status_code == 401

def test_hermes_devices_and_detail_no_secrets_leaked(client, seed_data):
    # 1. Register a test device
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-HERMES-01",
        "computer_name": "POS-HERMES-01-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.50",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]

    # 2. Ingest a metric
    client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ts": datetime.now(timezone.utc).isoformat(),
            "cpu_pct": 22.0,
            "ram_pct": 54.0,
            "ram_used_mb": 4200.0,
            "disks": [{"mount": "C:", "total_gb": 240, "used_gb": 120, "free_gb": 120, "pct": 50}],
            "network": {"adapters": []},
            "internet_ok": True,
            "printers": [],
            "services": []
        }
    )

    # 3. Query via Hermes API
    headers = {"X-API-Key": settings.HERMES_API_KEY}
    res_list = client.get("/api/v1/hermes/devices?store=ISL-01", headers=headers)
    assert res_list.status_code == 200
    devices = res_list.json()
    assert any(d["device_id"] == "POS-HERMES-01" for d in devices)

    # Inspect device response: ensure NO token or hash leaked
    pos = next(d for d in devices if d["device_id"] == "POS-HERMES-01")
    assert "token" not in pos
    assert "token_hash" not in pos
    assert "password" not in pos

    # 4. Query detail endpoint
    res_detail = client.get("/api/v1/hermes/devices/POS-HERMES-01", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["device_id"] == "POS-HERMES-01"
    assert detail["latest_metrics"] is not None
    assert detail["latest_metrics"]["cpu_pct"] == 22.0
    assert "token" not in detail
    assert "token_hash" not in detail

def test_hermes_downsampled_metrics(client, seed_data):
    # Register device
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-HERMES-02",
        "computer_name": "POS-HERMES-02-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.51",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]

    # Ingest 3 metrics spaced in time
    now = datetime.now(timezone.utc)
    for i in range(3):
        ts = (now - timedelta(minutes=i * 6)).isoformat()
        client.post(
            "/api/v1/agent/metrics",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "ts": ts,
                "cpu_pct": 20.0 + i,
                "ram_pct": 50.0 + i,
                "ram_used_mb": 4000.0,
                "disks": [{"mount": "C:", "total_gb": 200, "used_gb": 100, "free_gb": 100, "pct": 50}],
                "network": {"adapters": []},
                "internet_ok": True,
                "printers": [],
                "services": []
            }
        )

    headers = {"X-API-Key": settings.HERMES_API_KEY}
    res_metrics = client.get("/api/v1/hermes/devices/POS-HERMES-02/metrics?minutes=60&step=5", headers=headers)
    assert res_metrics.status_code == 200
    data = res_metrics.json()
    assert data["device_id"] == "POS-HERMES-02"
    assert len(data["series"]) >= 1
    assert "cpu_pct" in data["series"][0]

def test_hermes_summary_text(client, seed_data):
    # Register device
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-HERMES-03",
        "computer_name": "POS-HERMES-03-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.52",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]

    # Send heartbeat with datetime & FBR
    client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.52",
            "local_time": "2026-10-14T18:30:00+05:00",
            "utc_time": datetime.now(timezone.utc).isoformat(),
            "timezone_name": "Pakistan Standard Time",
            "utc_offset_minutes": 300,
            "uptime_sec": 7200.0,
            "fbr": {
                "fbr_status": "OK",
                "fbr_ok": True,
                "latency_ms": 38.0,
                "http_status": 200,
                "record_history": True
            }
        }
    )

    headers = {"X-API-Key": settings.HERMES_API_KEY}
    res = client.get("/api/v1/hermes/devices/POS-HERMES-03/summary_text", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["device_id"] == "POS-HERMES-03"
    assert "summary" in data
    assert "ONLINE" in data["summary"]
    assert "CPU 31.5%" in data["summary"]
    assert "Local time:" in data["summary"]
    assert "Pakistan Standard Time" in data["summary"]
    assert "FBR portal: OK" in data["summary"]
