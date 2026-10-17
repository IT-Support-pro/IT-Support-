import pytest
from datetime import datetime, timezone, timedelta
from app.models import Device, AgentTask, AuditLog, Metric, Alert

def test_remote_control_allowed_actions(client, seed_data):
    """
    G.2: Allowed actions ONLY: 'pause', 'resume', 'collect_now', 'fbr_check_now', 'restart_agent'.
    Reject anything else with 400 Bad Request.
    """
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    # Register device
    reg_res = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-CTRL-01",
        "computer_name": "POS-CTRL-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.55",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    })
    assert reg_res.status_code == 200

    # 1. Test invalid actions -> 400
    for invalid_action in ["stop", "start", "reboot_machine", "shell", "arbitrary_cmd"]:
        res = client.post(
            "/api/v1/devices/POS-CTRL-01/tasks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"action": invalid_action}
        )
        assert res.status_code == 400 or res.status_code == 422
        assert "not allowed" in res.text.lower() or "invalid" in res.text.lower()

    # 2. Test each of the 5 allowed actions -> 201 Created
    for valid_action in ["pause", "resume", "collect_now", "fbr_check_now", "restart_agent"]:
        res = client.post(
            "/api/v1/devices/POS-CTRL-01/tasks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"action": valid_action}
        )
        assert res.status_code == 201
        data = res.json()
        assert data["action"] == valid_action
        assert data["status"] == "PENDING"
        assert data["requested_by"] == "admin"
        assert data["id"] is not None

def test_remote_control_role_permissions(client, seed_data):
    """
    G.7: Gateway endpoints (JWT): POST /api/v1/devices/{device_id}/tasks {action}
    (admin and technician only, technicians only for their stores). Viewers cannot queue tasks.
    """
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    tech_token = client.post("/api/v1/auth/login", json={
        "username": "tech1",
        "password": "TechPassword123!"
    }).json()["access_token"]

    viewer_token = client.post("/api/v1/auth/login", json={
        "username": "viewer1",
        "password": "ViewerPassword123!"
    }).json()["access_token"]

    # Assign store to tech
    client.post(
        f"/api/v1/admin/users/{seed_data['tech'].id}/assign-stores",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"store_ids": [seed_data["store"].id]}
    )

    # Register device in assigned store
    client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-ROLE-01",
        "computer_name": "POS-ROLE-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.56",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    })

    # Technician can queue task for assigned store -> 201
    tech_res = client.post(
        "/api/v1/devices/POS-ROLE-01/tasks",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"action": "collect_now"}
    )
    assert tech_res.status_code == 201
    assert tech_res.json()["requested_by"] == "tech1"

    # Viewer cannot queue task -> 403 Forbidden
    viewer_res = client.post(
        "/api/v1/devices/POS-ROLE-01/tasks",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"action": "collect_now"}
    )
    assert viewer_res.status_code == 403

def test_heartbeat_task_dispatch_and_result_reporting(client, seed_data):
    """
    G.3: Agent heartbeat response includes pending tasks.
    Agent reports result via POST /api/v1/agent/tasks/{id}/result with {status, result_text}.
    AuditLog is recorded for both request and result.
    """
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    # 1. Register device
    reg_resp = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-DISPATCH-01",
        "computer_name": "POS-DISPATCH-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.57",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    })
    device_token = reg_resp.json()["device_token"]

    # 2. Queue 'pause' task via dashboard
    create_task_res = client.post(
        "/api/v1/devices/POS-DISPATCH-01/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "pause"}
    )
    assert create_task_res.status_code == 201
    task_id = create_task_res.json()["id"]

    # 3. Agent sends heartbeat -> tasks returned in response
    hb_res = client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {device_token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.57",
            "agent_state": "RUNNING"
        }
    )
    assert hb_res.status_code == 200
    hb_data = hb_res.json()
    assert "tasks" in hb_data
    task_ids = [t["id"] for t in hb_data["tasks"]]
    assert task_id in task_ids

    # 4. Agent reports task result -> 200
    res_post = client.post(
        f"/api/v1/agent/tasks/{task_id}/result",
        headers={"Authorization": f"Bearer {device_token}"},
        json={
            "status": "DONE",
            "result_text": "Agent paused. Telemetry transmission suspended."
        }
    )
    assert res_post.status_code == 200
    assert res_post.json()["task_status"] == "DONE"

    # 5. Device state should now be PAUSED
    dev_res = client.get(
        "/api/v1/devices/POS-DISPATCH-01",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert dev_res.json()["agent_state"] == "PAUSED"
    assert dev_res.json()["status"] == "PAUSED"

def test_paused_device_suppresses_metric_alerts(client, seed_data, db_session):
    """
    G.8: While device is PAUSED: do not raise metric alerts; offline detection still works.
    """
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    reg_resp = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-PAUSED-01",
        "computer_name": "POS-PAUSED-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.58",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    })
    device_token = reg_resp.json()["device_token"]

    # Pause device
    client.post(
        "/api/v1/devices/POS-PAUSED-01/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "pause"}
    )
    # Agent heartbeat reporting PAUSED
    client.post(
        "/api/v1/agent/heartbeat",
        headers={"Authorization": f"Bearer {device_token}"},
        json={
            "agent_version": "1.0.0",
            "ip_address": "192.168.1.58",
            "agent_state": "PAUSED"
        }
    )

    # Ingest critical metrics (100% CPU, 99% RAM)
    metric_res = client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {device_token}"},
        json={
            "cpu_pct": 100.0,
            "ram_pct": 99.0,
            "ram_used_mb": 8000.0,
            "disks": [{"drive": "C:", "free_gb": 0.5, "total_gb": 100.0, "pct": 99.5}],
            "network": {"adapters": []},
            "internet_ok": False,
            "printers": [],
            "services": []
        }
    )
    assert metric_res.status_code == 200

    # Verify no firing metric alerts were raised because device is PAUSED
    alerts_res = client.get(
        "/api/v1/alerts?state=FIRING",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    device_alerts = [a for a in alerts_res.json() if a.get("device_id") == "POS-PAUSED-01"]
    assert len(device_alerts) == 0
