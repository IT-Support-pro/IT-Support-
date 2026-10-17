from datetime import datetime, timedelta, timezone
from app.models import Device, Alert
from app.alert_engine import check_offline_devices

def test_health_check(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert "version" in res.json()

def test_login_and_lockout(client, seed_data):
    # 1. Successful login
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # 2. Failed login attempt
    bad_res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "WrongPassword123"
    })
    assert bad_res.status_code == 401

    # 3. Trigger 5 failed attempts lockout
    for _ in range(4):
        client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "WrongPassword123"
        })
    
    locked_res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    })
    assert locked_res.status_code == 423
    assert "locked" in locked_res.json()["detail"].lower()

def test_role_restrictions(client, seed_data):
    admin_login = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()
    admin_token = admin_login["access_token"]

    tech_login = client.post("/api/v1/auth/login", json={
        "username": "tech1",
        "password": "TechSecurePassword123!"
    }).json()
    tech_token = tech_login["access_token"]

    res_admin = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200

    res_tech = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {tech_token}"}
    )
    assert res_tech.status_code == 403

def test_agent_register(client, seed_data):
    key = seed_data["enrollment_key"]

    res_bad = client.post("/api/v1/agent/register", json={
        "enrollment_key": "INVALID-KEY-123",
        "device_id": "POS-01",
        "computer_name": "POS-01-TERMINAL",
        "device_type": "POS",
        "ip_address": "192.168.1.101",
        "os_version": "Windows 11 Enterprise",
        "agent_version": "1.0.0"
    })
    assert res_bad.status_code == 403

    res = client.post("/api/v1/agent/register", json={
        "enrollment_key": key,
        "device_id": "POS-01",
        "computer_name": "POS-01-TERMINAL",
        "device_type": "POS",
        "ip_address": "192.168.1.101",
        "os_version": "Windows 11 Enterprise",
        "agent_version": "1.0.0"
    })
    assert res.status_code == 200
    data = res.json()
    assert "device_token" in data
    assert data["device_id"] == "POS-01"
    assert data["store_code"] == "ISL-01"

# ----------------- STAGE 2 TESTS -----------------

def test_device_going_silent_and_offline_detection(client, db_session, seed_data):
    # 1. Register a POS terminal
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-SILENT-01",
        "computer_name": "POS-SILENT-TERMINAL",
        "device_type": "POS",
        "ip_address": "192.168.1.201",
        "os_version": "Windows 11 Pro",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]

    # 2. Simulate device going silent (last_seen 120s ago > 90s)
    dev = db_session.query(Device).filter(Device.device_id == "POS-SILENT-01").first()
    dev.last_seen = datetime.now(timezone.utc) - timedelta(seconds=120)
    dev.status = "ONLINE"
    db_session.commit()

    # 3. Trigger offline check
    check_offline_devices(db_session)

    # 4. Assert device marked OFFLINE and alert fired with 'POS offline' message
    db_session.refresh(dev)
    assert dev.status == "OFFLINE"

    alert = db_session.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.rule_key == "agent_offline"
    ).first()
    assert alert is not None
    assert alert.state == "FIRING"
    assert alert.severity == "critical"
    assert alert.message == "POS offline" # Required exact message for POS devices

    # 5. Device wakes up and sends heartbeat -> auto-resolves alert
    hb = client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={"agent_version": "1.0.0", "ip_address": "192.168.1.201"}
    )
    assert hb.status_code == 200
    db_session.refresh(dev)
    db_session.refresh(alert)
    assert dev.status == "ONLINE"
    assert alert.state == "RESOLVED"
    assert alert.resolved_at is not None

def test_disk_95_alert_and_auto_resolve(client, db_session, seed_data):
    # Register device
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-DISK-01",
        "computer_name": "POS-DISK-TERMINAL",
        "device_type": "POS",
        "ip_address": "192.168.1.202",
        "os_version": "Windows 11 Pro",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]
    dev = db_session.query(Device).filter(Device.device_id == "POS-DISK-01").first()

    # Send metric with disk at 95%
    metric_bad = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": 20.0,
        "ram_pct": 50.0,
        "ram_used_mb": 4000.0,
        "disks": [{"mount": "C:", "total_gb": 200, "used_gb": 190, "free_gb": 10, "pct": 95.0}],
        "network": {"adapters": []},
        "internet_ok": True,
        "printers": [],
        "services": [{"name": "Spooler", "state": "Running"}]
    }

    res = client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {token}"},
        json=metric_bad
    )
    assert res.status_code == 200

    # Verify disk_low alert fired
    alert = db_session.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.rule_key == "disk_low"
    ).first()
    assert alert is not None
    assert alert.state == "FIRING"
    assert alert.severity == "critical"
    assert "95" in alert.message

    # Send healthy metric with disk at 60% -> auto-resolves
    metric_good = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": 20.0,
        "ram_pct": 50.0,
        "ram_used_mb": 4000.0,
        "disks": [{"mount": "C:", "total_gb": 200, "used_gb": 120, "free_gb": 80, "pct": 60.0}],
        "network": {"adapters": []},
        "internet_ok": True,
        "printers": [],
        "services": [{"name": "Spooler", "state": "Running"}]
    }
    client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {token}"},
        json=metric_good
    )

    db_session.refresh(alert)
    assert alert.state == "RESOLVED"
    assert alert.resolved_at is not None

def test_service_stopped_alert(client, db_session, seed_data):
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-SVC-01",
        "computer_name": "POS-SVC-TERMINAL",
        "device_type": "POS",
        "ip_address": "192.168.1.203",
        "os_version": "Windows 11 Pro",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]
    dev = db_session.query(Device).filter(Device.device_id == "POS-SVC-01").first()

    metric_stopped = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": 20.0,
        "ram_pct": 50.0,
        "ram_used_mb": 4000.0,
        "disks": [{"mount": "C:", "total_gb": 200, "used_gb": 100, "free_gb": 100, "pct": 50.0}],
        "network": {"adapters": []},
        "internet_ok": True,
        "printers": [],
        "services": [
            {"name": "Print Spooler", "state": "Stopped"}
        ]
    }

    res = client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {token}"},
        json=metric_stopped
    )
    assert res.status_code == 200

    alert = db_session.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.rule_key == "service_down"
    ).first()
    assert alert is not None
    assert alert.state == "FIRING"
    assert alert.severity == "critical"
    assert "Print Spooler" in alert.message

def test_alert_ack_and_resolve_api(client, db_session, seed_data):
    # Admin login
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    # Register device & trigger alert
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-ACK-01",
        "computer_name": "POS-ACK-TERMINAL",
        "device_type": "POS",
        "ip_address": "192.168.1.204",
        "os_version": "Windows 11 Pro",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]

    client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ts": datetime.now(timezone.utc).isoformat(),
            "cpu_pct": 10.0,
            "ram_pct": 20.0,
            "ram_used_mb": 1000.0,
            "disks": [{"mount": "C:", "total_gb": 100, "used_gb": 95, "free_gb": 5, "pct": 95.0}],
            "network": {"adapters": []},
            "internet_ok": True,
            "printers": [],
            "services": []
        }
    )

    # List alerts
    alerts_res = client.get(
        "/api/v1/alerts?state=FIRING",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert alerts_res.status_code == 200
    alerts_list = alerts_res.json()
    assert len(alerts_list) >= 1
    alert_id = alerts_list[0]["id"]

    # Acknowledge alert
    ack_res = client.post(
        f"/api/v1/alerts/{alert_id}/ack",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["state"] == "ACKNOWLEDGED"

    # Resolve alert manually
    res_res = client.post(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_res.status_code == 200
    assert res_res.json()["state"] == "RESOLVED"

def test_clock_drift_and_timezone_mismatch(client, db_session, seed_data):
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-TIME-01",
        "computer_name": "POS-TIME-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.205",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]
    dev = db_session.query(Device).filter(Device.device_id == "POS-TIME-01").first()

    # 1. Send heartbeat with timezone mismatch and clock drift > 120s
    now = datetime.now(timezone.utc)
    drifted_utc = now + timedelta(seconds=250)
    hb_res = client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.205",
            "local_time": "2026-10-14T11:00:00-08:00",
            "utc_time": drifted_utc.isoformat(),
            "timezone_name": "Pacific Standard Time",
            "utc_offset_minutes": -480,
            "uptime_sec": 3600.0
        }
    )
    assert hb_res.status_code == 200

    # Verify clock drift alert fired (warning)
    drift_alert = db_session.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.rule_key == "clock_drift",
        Alert.state == "FIRING"
    ).first()
    assert drift_alert is not None
    assert drift_alert.severity == "warning"

    # Verify timezone mismatch alert fired
    tz_alert = db_session.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.rule_key == "timezone_mismatch",
        Alert.state == "FIRING"
    ).first()
    assert tz_alert is not None
    assert tz_alert.severity == "warning"

    # 2. Correct timezone and sync clock -> auto-resolves
    hb_correct = client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.205",
            "local_time": "2026-10-14T19:00:00+05:00",
            "utc_time": datetime.now(timezone.utc).isoformat(),
            "timezone_name": "Pakistan Standard Time",
            "utc_offset_minutes": 300,
            "uptime_sec": 3660.0
        }
    )
    assert hb_correct.status_code == 200
    db_session.refresh(drift_alert)
    db_session.refresh(tz_alert)
    assert drift_alert.state == "RESOLVED"
    assert tz_alert.state == "RESOLVED"

def test_fbr_connectivity_alerts(client, db_session, seed_data):
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-FBR-01",
        "computer_name": "POS-FBR-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.206",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]
    dev = db_session.query(Device).filter(Device.device_id == "POS-FBR-01").first()

    # Failure 1: consecutive_failures = 1 (no alert yet)
    client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.206",
            "fbr": {
                "fbr_status": "DOWN",
                "fbr_ok": False,
                "latency_ms": 5000.0,
                "consecutive_failures": 1,
                "error_text": "Connection timeout",
                "record_history": True
            }
        }
    )
    alert = db_session.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.rule_key == "fbr_down",
        Alert.state == "FIRING"
    ).first()
    assert alert is None

    # Failure 2: consecutive_failures = 2 (alert fires)
    client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.206",
            "fbr": {
                "fbr_status": "DOWN",
                "fbr_ok": False,
                "latency_ms": 5000.0,
                "consecutive_failures": 2,
                "error_text": "Connection timeout",
                "record_history": True
            }
        }
    )
    alert = db_session.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.rule_key == "fbr_down",
        Alert.state == "FIRING"
    ).first()
    assert alert is not None
    assert alert.severity == "critical"

    # Recovery: FBR succeeds -> auto-resolves
    client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.206",
            "fbr": {
                "fbr_status": "OK",
                "fbr_ok": True,
                "latency_ms": 45.0,
                "http_status": 200,
                "consecutive_failures": 0,
                "record_history": True
            }
        }
    )
    db_session.refresh(alert)
    assert alert.state == "RESOLVED"

def test_gateway_printers_filtering(client, db_session, seed_data):
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-PRN-01",
        "computer_name": "POS-PRN-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.207",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]
    dev = db_session.query(Device).filter(Device.device_id == "POS-PRN-01").first()

    # Ingest metrics containing virtual printers & duplicate copies
    client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ts": datetime.now(timezone.utc).isoformat(),
            "cpu_pct": 20.0,
            "ram_pct": 30.0,
            "ram_used_mb": 2000.0,
            "disks": [{"mount": "C:", "total_gb": 100, "used_gb": 40, "free_gb": 60, "pct": 40.0}],
            "network": {"adapters": []},
            "internet_ok": True,
            "printers": [
                {"name": "Microsoft Print to PDF", "status": "Idle", "port": "PORTPROMPT:"},
                {"name": "OneNote (Desktop)", "status": "Idle", "port": "nul:"},
                {"name": "Receipt TM-T88", "status": "Idle", "port": "USB001"},
                {"name": "Receipt TM-T88 (Copy 1)", "status": "Idle", "port": "USB001"}
            ],
            "services": []
        }
    )

    metric = db_session.query(Metric).filter(Metric.device_pk == dev.id).first()
    assert metric is not None
    assert len(metric.printers_json) == 1
    assert metric.printers_json[0]["name"] == "Receipt TM-T88"
