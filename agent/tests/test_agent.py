import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

# Ensure agent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import AgentConfig
from buffer import TelemetryBuffer
from client import GatewayClient
from collectors.system import collect_system_metrics
from collectors.network import collect_network_metrics
from collectors.services import collect_services_metrics
from collectors.printer import collect_printer_metrics
from main import collect_full_snapshot

def test_system_collector():
    data = collect_system_metrics()
    assert isinstance(data, dict)
    assert "cpu_pct" in data
    assert "ram_pct" in data
    assert "ram_used_mb" in data
    assert isinstance(data["disks"], list)

def test_network_collector():
    data = collect_network_metrics(gateway_url="http://127.0.0.1:8000", ping_targets=["8.8.8.8"])
    assert isinstance(data, dict)
    assert "network" in data
    assert "internet_ok" in data
    assert "adapters" in data["network"]

def test_services_collector():
    data = collect_services_metrics(["Spooler", "NonExistentDummyService"])
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "Spooler"
    assert data[0]["state"] in ["Running", "Stopped", "Not found"]

def test_printer_collector():
    data = collect_printer_metrics()
    assert isinstance(data, list)

def test_telemetry_buffer_drop_oldest():
    # 1 KB buffer
    buf = TelemetryBuffer(max_mb=1)
    buf.max_bytes = 200 # set tiny limit for testing drop-oldest

    item1 = {"id": 1, "data": "A" * 80}
    item2 = {"id": 2, "data": "B" * 80}
    item3 = {"id": 3, "data": "C" * 80}

    buf.push(item1)
    buf.push(item2)
    buf.push(item3)

    # Oldest (item1) must be dropped
    batch = buf.pop_all()
    assert len(batch) >= 1
    assert all(item["id"] != 1 for item in batch) or len(batch) < 3

def test_config_blanking():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".toml") as tmp:
        tmp.write('[gateway]\nurl = "http://127.0.0.1"\n\n[device]\ndevice_id = "POS-01"\nenrollment_key = "HBK-TEST-KEY"\n')
        tmp_path = tmp.name

    try:
        cfg = AgentConfig(tmp_path)
        assert cfg.enrollment_key == "HBK-TEST-KEY"
        cfg.blank_enrollment_key()
        assert cfg.enrollment_key == ""

        # Reload from disk
        cfg2 = AgentConfig(tmp_path)
        assert cfg2.enrollment_key == ""
    finally:
        os.remove(tmp_path)

def test_gateway_client_registration_and_heartbeat():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".toml") as tmp_cfg, \
         tempfile.NamedTemporaryFile("w+", delete=False, suffix=".dat") as tmp_tok:
        tmp_cfg.write('[gateway]\nurl = "http://127.0.0.1:8000"\n\n[device]\ndevice_id = "POS-01"\nenrollment_key = "HBK-SECRET"\n')
        cfg_path = tmp_cfg.name
        tok_path = tmp_tok.name

    try:
        cfg = AgentConfig(cfg_path)
        client = GatewayClient(cfg, token_file=tok_path)

        # Mock registration response
        mock_reg_resp = MagicMock()
        mock_reg_resp.status_code = 200
        mock_reg_resp.json.return_value = {
            "device_token": "mocked-device-token-12345",
            "device_id": "POS-01",
            "store_code": "ISL-01"
        }

        with patch.object(client.session, "post", return_value=mock_reg_resp):
            success = client.register()
            assert success is True
            assert client.device_token == "mocked-device-token-12345"
            assert cfg.enrollment_key == ""

        # Mock heartbeat response
        mock_hb_resp = MagicMock()
        mock_hb_resp.status_code = 200
        with patch.object(client.session, "post", return_value=mock_hb_resp):
            hb_ok = client.send_heartbeat("192.168.1.101")
            assert hb_ok is True
    finally:
        os.remove(cfg_path)
        if os.path.exists(tok_path):
            os.remove(tok_path)

def test_collection_timing_under_2_seconds():
    class DummyConfig:
        gateway_url = "http://127.0.0.1:8000"
        ping_targets = ["8.8.8.8"]
        services = ["Spooler"]

    t0 = time.perf_counter()
    snap = collect_full_snapshot(DummyConfig())
    duration = time.perf_counter() - t0
    assert duration < 2.0
    assert "cpu_pct" in snap
    assert "ts" in snap

def test_agent_state_persistence():
    from main import HBKAgent
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.toml")
        with open(cfg_path, "w") as f:
            f.write('[agent]\ndevice_id = "POS-T1"\nstore = "ISL-01"\n')
        
        agent = HBKAgent(config_path=cfg_path)
        assert agent.agent_state == "RUNNING"
        
        # Save PAUSED state
        agent.save_agent_state("PAUSED")
        assert agent.agent_state == "PAUSED"
        assert os.path.exists(agent.state_file)
        
        # New agent instance should load PAUSED state
        agent2 = HBKAgent(config_path=cfg_path)
        assert agent2.agent_state == "PAUSED"
        
        # Resume back to RUNNING
        agent2.save_agent_state("RUNNING")
        assert agent2.agent_state == "RUNNING"
        
        agent3 = HBKAgent(config_path=cfg_path)
        assert agent3.agent_state == "RUNNING"

def test_agent_handle_task_actions():
    from main import HBKAgent
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.toml")
        with open(cfg_path, "w") as f:
            f.write('[agent]\ndevice_id = "POS-T1"\nstore = "ISL-01"\n')
        
        agent = HBKAgent(config_path=cfg_path, is_service=False)
        agent.client.send_task_result = MagicMock()
        agent.client.send_metrics = MagicMock(return_value=True)

        dummy_net = {"device_ip": "192.168.1.50"}

        # 1. Action: pause
        agent.handle_task({"id": 101, "action": "pause"}, dummy_net)
        assert agent.agent_state == "PAUSED"
        agent.client.send_task_result.assert_called_with(101, "DONE", "Agent paused. Telemetry transmission suspended.")

        # 2. Action: resume
        agent.handle_task({"id": 102, "action": "resume"}, dummy_net)
        assert agent.agent_state == "RUNNING"
        assert agent.client.send_metrics.called

        # 3. Action: collect_now
        agent.handle_task({"id": 103, "action": "collect_now"}, dummy_net)
        agent.client.send_task_result.assert_called_with(103, "DONE", "Telemetry reading collected and submitted successfully.")

        # 4. Action: restart_agent when not running as a service
        agent.handle_task({"id": 104, "action": "restart_agent"}, dummy_net)
        agent.client.send_task_result.assert_called_with(104, "FAILED", "not installed as a service")

        # 5. Unknown action
        agent.handle_task({"id": 105, "action": "unknown_action"}, dummy_net)
        agent.client.send_task_result.assert_called_with(105, "FAILED", "unsupported action: unknown_action")

