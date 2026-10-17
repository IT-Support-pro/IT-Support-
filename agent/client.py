import os
import sys
import platform
import subprocess
try:
    import requests
except ImportError:
    requests = None
from typing import Optional, List, Dict, Any

from config import AgentConfig
from logger import logger
from buffer import TelemetryBuffer

class GatewayClient:
    def __init__(self, config: AgentConfig, token_file: str = "token.dat"):
        self.config = config
        self.token_file = os.path.abspath(token_file)
        self.device_token: Optional[str] = None
        self.session = requests.Session() if requests else None
        self.buffer = TelemetryBuffer(max_mb=config.max_buffer_mb)
        
        # Exponential backoff parameters
        self.backoff_delay = 5.0
        self.max_backoff = 300.0 # capped at 5 minutes

        self.load_token()

    def load_token(self):
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    tok = f.read().strip()
                    if tok:
                        self.device_token = tok
            except Exception as e:
                logger.error(f"Failed to read existing token file: {e}")

    def save_token(self, token: str):
        self.device_token = token.strip()
        try:
            with open(self.token_file, "w", encoding="utf-8") as f:
                f.write(self.device_token)

            # Restrict permissions to SYSTEM and Administrators on Windows, or 0600 on Linux
            if platform.system().lower() == "windows":
                try:
                    cmd = f'icacls "{self.token_file}" /inheritance:r /grant:r "Administrators":F /grant:r "SYSTEM":F'
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=2)
                except Exception:
                    pass
            else:
                try:
                    os.chmod(self.token_file, 0o600)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to save device token securely: {e}")

    def register(self, ip_address: str = "127.0.0.1") -> bool:
        """Calls POST /api/v1/agent/register to enroll or re-issue token."""
        if not self.config.enrollment_key:
            logger.warning("No enrollment_key present in config.toml; registration cannot proceed.")
            return False

        url = f"{self.config.gateway_url}/api/v1/agent/register"
        payload = {
            "enrollment_key": self.config.enrollment_key,
            "device_id": self.config.device_id,
            "computer_name": platform.node(),
            "device_type": self.config.device_type,
            "ip_address": ip_address,
            "os_version": f"{platform.system()} {platform.release()}",
            "agent_version": "1.0.0"
        }

        try:
            logger.info(f"Sending registration request for device '{self.config.device_id}'...")
            res = self.session.post(url, json=payload, timeout=8.0, verify=self.config.verify_tls)
            if res.status_code == 200:
                data = res.json()
                raw_token = data.get("device_token")
                if raw_token:
                    self.save_token(raw_token)
                    logger.info("Registration successful. Device token saved and secured.")
                    # Blank out enrollment key in config.toml
                    self.config.blank_enrollment_key()
                    self.backoff_delay = 5.0
                    return True
            else:
                logger.error(f"Registration rejected with status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Network error connecting to gateway for registration: {e}")

        return False

    def send_heartbeat(
        self,
        ip_address: str,
        dt_info: Dict[str, Any],
        fbr_summary: Optional[Dict[str, Any]] = None,
        agent_state: str = "RUNNING"
    ) -> List[Dict[str, Any]]:
        """
        Sends POST /api/v1/agent/heartbeat with Bearer token.
        Includes local_time, utc_time, timezone_name, utc_offset_minutes, uptime_sec,
        fresh FBR connectivity status, and agent_state.
        Returns list of tasks dispatched by the gateway.
        """
        if not self.device_token:
            if self.config.enrollment_key:
                if not self.register(ip_address):
                    return []
            else:
                logger.error("Cannot send heartbeat: no device token and no enrollment key configured.")
                return []

        url = f"{self.config.gateway_url}/api/v1/agent/heartbeat"
        headers = {"Authorization": f"Bearer {self.device_token}"}
        payload = {
            "agent_version": "1.0.0",
            "ip_address": ip_address,
            "local_time": dt_info.get("local_time"),
            "utc_time": dt_info.get("utc_time"),
            "timezone_name": dt_info.get("timezone_name"),
            "utc_offset_minutes": dt_info.get("utc_offset_minutes"),
            "uptime_sec": dt_info.get("uptime_sec"),
            "fbr": fbr_summary,
            "agent_state": agent_state
        }

        try:
            res = self.session.post(url, json=payload, headers=headers, timeout=5.0, verify=self.config.verify_tls)
            if res.status_code == 200:
                self.backoff_delay = 5.0
                data = res.json()
                return data.get("tasks", [])
            elif res.status_code == 401:
                logger.warning("Heartbeat returned 401 Unauthorized. Token may be revoked.")
                if self.config.enrollment_key:
                    logger.info("Attempting re-registration with stored enrollment key...")
                    self.register(ip_address)
            else:
                logger.warning(f"Heartbeat returned HTTP {res.status_code}")
        except Exception as e:
            logger.warning(f"Heartbeat network failed: {e}")

        return []

    def send_task_result(self, task_id: int, status: str, result_text: Optional[str] = None) -> bool:
        """
        Calls POST /api/v1/agent/tasks/{task_id}/result to acknowledge task completion.
        """
        if not self.device_token:
            logger.error("Cannot send task result: no device token.")
            return False

        url = f"{self.config.gateway_url}/api/v1/agent/tasks/{task_id}/result"
        headers = {"Authorization": f"Bearer {self.device_token}"}
        payload = {
            "status": status,
            "result_text": result_text
        }

        try:
            res = self.session.post(url, json=payload, headers=headers, timeout=5.0, verify=self.config.verify_tls)
            if res.status_code == 200:
                logger.info(f"Reported task #{task_id} result ({status}) successfully.")
                return True
            else:
                logger.warning(f"Failed to report task result: HTTP {res.status_code} ({res.text})")
        except Exception as e:
            logger.error(f"Network error reporting task #{task_id} result: {e}")

        return False

    def send_metrics(self, current_snapshot: Dict[str, Any]) -> bool:
        """
        Sends latest metrics or queued buffer snapshots via POST /api/v1/agent/metrics.
        If offline, adds to queue with exponential backoff.
        """
        # Always add current snapshot to queue
        self.buffer.push(current_snapshot)

        if not self.device_token:
            if self.config.enrollment_key:
                if not self.register(current_snapshot.get("network", {}).get("adapters", [{}])[0].get("ipv4", "127.0.0.1")):
                    return False
            else:
                return False

        # Pop all buffered snapshots to transmit batch
        batch = self.buffer.pop_all()
        if not batch:
            return True

        url = f"{self.config.gateway_url}/api/v1/agent/metrics"
        headers = {"Authorization": f"Bearer {self.device_token}"}

        try:
            res = self.session.post(url, json=batch, headers=headers, timeout=8.0, verify=self.config.verify_tls)
            if res.status_code == 200:
                logger.info(f"Transmitted {len(batch)} metric snapshot(s) successfully.")
                self.backoff_delay = 5.0
                return True
            elif res.status_code == 401:
                logger.warning("Metrics returned 401 Unauthorized.")
                self.buffer.restore_batch(batch)
                if self.config.enrollment_key:
                    self.register()
            else:
                logger.warning(f"Metrics submission failed ({res.status_code}). Buffering.")
                self.buffer.restore_batch(batch)
                self.increase_backoff()
        except Exception as e:
            logger.warning(f"Network error sending metrics: {e}. Buffered in local queue (queue size: {self.buffer.size()}).")
            self.buffer.restore_batch(batch)
            self.increase_backoff()

        return False

    def increase_backoff(self):
        self.backoff_delay = min(self.backoff_delay * 1.5, self.max_backoff)
