from datetime import datetime, timezone
from app.models import Device, Metric, Store, Alert

def test_dashboard_overview(client, seed_data):
    # Admin login
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    res = client.get("/api/v1/overview", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "devices_total" in data
    assert "online" in data
    assert "offline" in data
    assert "firing_alerts" in data
    assert "stores_count" in data

def test_dashboard_stores(client, seed_data):
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    res = client.get("/api/v1/stores", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    stores = res.json()
    assert len(stores) >= 1
    assert stores[0]["code"] == "ISL-01"

def test_dashboard_devices_list_and_detail(client, seed_data):
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    # Register a device
    reg = client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-DASH-01",
        "computer_name": "POS-DASH-01-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.75",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    }).json()
    token = reg["device_token"]

    # Ingest a metric
    client.post(
        "/api/v1/agent/metrics",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ts": datetime.now(timezone.utc).isoformat(),
            "cpu_pct": 19.5,
            "ram_pct": 52.0,
            "ram_used_mb": 4160.0,
            "disks": [{"mount": "C:", "total_gb": 240, "used_gb": 120, "free_gb": 120, "pct": 50}],
            "network": {"adapters": []},
            "internet_ok": True,
            "printers": [{"name": "Receipt TM-T88", "status": "Idle", "queue": 0, "port": "USB001"}],
            "services": [{"name": "Spooler", "state": "Running"}]
        }
    )

    # 1. List devices
    res_list = client.get("/api/v1/devices?search=DASH", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_list.status_code == 200
    devs = res_list.json()
    assert any(d["device_id"] == "POS-DASH-01" for d in devs)

    # 2. Get device detail
    res_detail = client.get("/api/v1/devices/POS-DASH-01", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["device_id"] == "POS-DASH-01"
    assert detail["latest_metrics"] is not None
    assert detail["latest_metrics"]["cpu_pct"] == 19.5

    # 3. Get metrics series
    res_metrics = client.get("/api/v1/devices/POS-DASH-01/metrics?minutes=60", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_metrics.status_code == 200
    assert len(res_metrics.json()["series"]) >= 1

def test_dashboard_notes_flow(client, seed_data):
    # Tech login
    tech_token = client.post("/api/v1/auth/login", json={
        "username": "tech1",
        "password": "TechSecurePassword123!"
    }).json()["access_token"]

    # Viewer login
    viewer_token = client.post("/api/v1/auth/login", json={
        "username": "viewer1",
        "password": "ViewerSecurePassword123!"
    }).json()["access_token"]

    # Assign store 1 to tech1 and viewer1 via admin
    admin_token = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "AdminSecurePassword123!"
    }).json()["access_token"]

    client.post(
        f"/api/v1/admin/users/{seed_data['tech'].id}/assign-stores",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"store_ids": [seed_data["store"].id]}
    )
    client.post(
        f"/api/v1/admin/users/{seed_data['viewer'].id}/assign-stores",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"store_ids": [seed_data["store"].id]}
    )

    # Register device
    client.post("/api/v1/agent/register", json={
        "enrollment_key": seed_data["enrollment_key"],
        "device_id": "POS-NOTE-01",
        "computer_name": "POS-NOTE-PC",
        "device_type": "POS",
        "ip_address": "192.168.1.80",
        "os_version": "Windows 11",
        "agent_version": "1.0.0"
    })

    # Tech posts note -> 201
    post_res = client.post(
        "/api/v1/devices/POS-NOTE-01/notes",
        headers={"Authorization": f"Bearer {tech_token}"},
        json={"text": "Inspected receipt printer. Cleaned paper feeder rollers."}
    )
    assert post_res.status_code == 201
    assert post_res.json()["author_username"] == "tech1"

    # Viewer tries to post note -> 403 Forbidden
    viewer_post = client.post(
        "/api/v1/devices/POS-NOTE-01/notes",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"text": "Viewer cannot add notes"}
    )
    assert viewer_post.status_code == 403

    # Viewer can read notes -> 200
    get_res = client.get(
        "/api/v1/devices/POS-NOTE-01/notes",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert get_res.status_code == 200
    assert len(get_res.json()) >= 1
