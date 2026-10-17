import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

# Ensure agent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import HBKAgent

def test_agent_state_persistence():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".toml") as tmp:
        tmp.write('[gateway]\nurl = "http://127.0.0.1"\n\n[device]\ndevice_id = "POS-01"\n')
        cfg_path = tmp.name

    try:
        agent = HBKAgent(config_path=cfg_path, is_service=False)
        assert agent.agent_state == "RUNNING"

        # Persist PAUSED state
        agent.save_agent_state("PAUSED")
        assert agent.agent_state == "PAUSED"
        assert os.path.exists(agent.state_file)

        # Create new agent instance pointing to same config directory -> must load PAUSED
        agent2 = HBKAgent(config_path=cfg_path, is_service=False)
        assert agent2.agent_state == "PAUSED"

        # Resume to RUNNING
        agent2.save_agent_state("RUNNING")
        assert agent2.agent_state == "RUNNING"
    finally:
        os.remove(cfg_path)
        state_file = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "agent_state.dat")
        if os.path.exists(state_file):
            os.remove(state_file)

def test_agent_handle_tasks():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".toml") as tmp:
        tmp.write('[gateway]\nurl = "http://127.0.0.1"\n\n[device]\ndevice_id = "POS-01"\n')
        cfg_path = tmp.name

    try:
        agent = HBKAgent(config_path=cfg_path, is_service=False)
        agent.client.send_task_result = MagicMock(return_value=True)
        agent.client.send_metrics = MagicMock(return_value=True)

        net_info = {"device_ip": "192.168.1.100"}

        # 1. Action: pause
        agent.handle_task({"id": 1, "action": "pause"}, net_info)
        assert agent.agent_state == "PAUSED"
        agent.client.send_task_result.assert_called_with(1, "DONE", "Agent paused. Telemetry transmission suspended.")

        # 2. Action: resume
        agent.handle_task({"id": 2, "action": "resume"}, net_info)
        assert agent.agent_state == "RUNNING"
        agent.client.send_task_result.assert_called_with(2, "DONE", "Agent resumed. Immediately sent full telemetry reading.")
        assert agent.client.send_metrics.called

        # 3. Action: collect_now
        agent.client.send_metrics.reset_mock()
        agent.handle_task({"id": 3, "action": "collect_now"}, net_info)
        assert agent.client.send_metrics.called
        agent.client.send_task_result.assert_called_with(3, "DONE", "Telemetry reading collected and submitted successfully.")

        # 4. Action: fbr_check_now
        agent.fbr_checker.check = MagicMock(return_value={
            "fbr_status": "OK",
            "fbr_ok": True,
            "latency_ms": 45.0,
            "http_status": 200,
            "error_text": None
        })
        agent.handle_task({"id": 4, "action": "fbr_check_now"}, net_info)
        assert agent.fbr_checker.check.called

        # 5. Action: restart_agent when not running as a Windows service -> must fail
        agent.is_service = False
        agent.handle_task({"id": 5, "action": "restart_agent"}, net_info)
        agent.client.send_task_result.assert_called_with(5, "FAILED", "not installed as a service")

        # 6. Action: unknown action -> FAILED
        agent.handle_task({"id": 6, "action": "arbitrary_command"}, net_info)
        agent.client.send_task_result.assert_called_with(6, "FAILED", "unsupported action: arbitrary_command")
    finally:
        os.remove(cfg_path)
        state_file = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "agent_state.dat")
        if os.path.exists(state_file):
            os.remove(state_file)
