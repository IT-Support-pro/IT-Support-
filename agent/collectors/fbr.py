import time
import socket
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

class FbrChecker:
    """
    Performs real per-POS FBR monitoring by separating:
    1. Local PRAL / IMS Windows service health (GET http://localhost:8524/api/IMSFiscal/Get)
    2. Actual remote FBR cloud connectivity (official probe endpoint if configured)

    Rules:
    - Never call invoice submission endpoint (GetInvoiceNumberByModel) during health checks.
    - If interface only proves local IMS health, mark local_ims_status='RUNNING' and
      fbr_connectivity_status='UNKNOWN'.
    - Distinct states: CONNECTED, DISCONNECTED, LOCAL_SERVICE_DOWN, UNKNOWN, CHECKING.
    """

    def __init__(
        self, 
        ims_url: str = "http://localhost:8524/api/IMSFiscal/Get", 
        remote_fbr_url: str = "", 
        timeout_sec: int = 4
    ):
        self.ims_url = (ims_url or "http://localhost:8524/api/IMSFiscal/Get").strip()
        self.remote_fbr_url = (remote_fbr_url or "").strip()
        self.timeout_sec = max(1, timeout_sec)
        self.consecutive_failures = 0
        self.last_ok_time: Optional[str] = None
        self.last_check_time: Optional[str] = None
        self.cached_result: Optional[Dict[str, Any]] = None

    def check(self) -> Dict[str, Any]:
        """
        Executes dual probe: local IMS service + optional remote FBR probe.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        self.last_check_time = now_str
        start_time = time.perf_counter()

        # Step 1: Probe local IMS service (port 8524)
        local_ims_ok = False
        local_ims_status = "UNKNOWN"
        local_ims_latency = None
        local_ims_msg = None

        if requests is not None:
            t0 = time.perf_counter()
            try:
                resp = requests.get(
                    self.ims_url,
                    timeout=self.timeout_sec,
                    headers={"User-Agent": "HBK-POS-Agent/1.0 (Local PRAL Health Probe)"}
                )
                local_ims_latency = round((time.perf_counter() - t0) * 1000, 1)
                if resp.status_code == 200:
                    local_ims_ok = True
                    local_ims_status = "RUNNING"
                    local_ims_msg = resp.text.strip()[:80] if resp.text else "Service is responding"
                else:
                    local_ims_ok = False
                    local_ims_status = "DOWN"
                    local_ims_msg = f"HTTP {resp.status_code}: {resp.text.strip()[:60]}"
            except requests.exceptions.ConnectionError:
                local_ims_ok = False
                local_ims_status = "DOWN"
                local_ims_msg = "Connection refused on port 8524 (PRAL/IMS service stopped or not listening)"
            except requests.exceptions.Timeout:
                local_ims_ok = False
                local_ims_status = "DOWN"
                local_ims_msg = f"Timeout ({self.timeout_sec}s) contacting local IMS on port 8524"
            except Exception as e:
                local_ims_ok = False
                local_ims_status = "DOWN"
                local_ims_msg = f"Local IMS probe error: {e}"
        else:
            # Socket fallback if requests module is missing
            try:
                parsed_ims = urlparse(self.ims_url)
                host = parsed_ims.hostname or "127.0.0.1"
                port = parsed_ims.port or 8524
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout_sec)
                sock.connect((host, port))
                sock.close()
                local_ims_ok = True
                local_ims_status = "RUNNING"
                local_ims_msg = "TCP 8524 port listening"
            except Exception as e:
                local_ims_ok = False
                local_ims_status = "DOWN"
                local_ims_msg = f"TCP connect failed on 8524: {e}"

        # If local IMS is down, FBR connectivity is directly LOCAL_SERVICE_DOWN
        if not local_ims_ok:
            self.consecutive_failures += 1
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            res = {
                "fbr_status": "DOWN",
                "fbr_connectivity_status": "LOCAL_SERVICE_DOWN",
                "local_ims_ok": False,
                "local_ims_status": "DOWN",
                "fbr_ok": False,
                "latency_ms": elapsed_ms,
                "http_status": None,
                "last_ok_time": self.last_ok_time,
                "last_check_time": now_str,
                "consecutive_failures": self.consecutive_failures,
                "error_text": local_ims_msg,
                "record_history": True
            }
            self.cached_result = res
            return res

        # Step 2: Probe actual remote FBR connectivity if remote URL is configured
        if self.remote_fbr_url and "PASTE" not in self.remote_fbr_url.upper():
            remote_res = self._probe_remote_fbr(self.remote_fbr_url, start_time, now_str)
            remote_res["local_ims_ok"] = True
            remote_res["local_ims_status"] = "RUNNING"
            self.cached_result = remote_res
            return remote_res

        # If only local IMS was probed and responded, actual FBR cloud reachability is UNKNOWN
        elapsed_ms = local_ims_latency or round((time.perf_counter() - start_time) * 1000, 1)
        res = {
            "fbr_status": "UNKNOWN",
            "fbr_connectivity_status": "UNKNOWN",
            "local_ims_ok": True,
            "local_ims_status": "RUNNING",
            "fbr_ok": True, # local service is healthy
            "latency_ms": elapsed_ms,
            "http_status": 200,
            "last_ok_time": now_str,
            "last_check_time": now_str,
            "consecutive_failures": 0,
            "error_text": "Local IMS responds ('Service is responding'). Remote FBR cloud reachability is UNKNOWN until verified.",
            "record_history": True
        }
        self.last_ok_time = now_str
        self.cached_result = res
        return res

    def _probe_remote_fbr(self, url: str, start_time: float, now_str: str) -> Dict[str, Any]:
        """Probes independent external FBR endpoint."""
        parsed = urlparse(url)
        host = parsed.hostname or url
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        # 1. DNS check
        try:
            socket.gethostbyname(host)
        except Exception as e:
            self.consecutive_failures += 1
            return {
                "fbr_status": "DOWN",
                "fbr_connectivity_status": "DISCONNECTED",
                "fbr_ok": False,
                "latency_ms": None,
                "http_status": None,
                "last_ok_time": self.last_ok_time,
                "last_check_time": now_str,
                "consecutive_failures": self.consecutive_failures,
                "error_text": f"FBR DNS resolution failed for {host}: {e}",
                "record_history": True
            }

        # 2. HTTP probe
        try:
            resp = requests.get(
                url,
                timeout=self.timeout_sec,
                allow_redirects=True,
                headers={"User-Agent": "HBK-POS-Agent/1.0 (FBR Remote Reachability Probe)"}
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            self.consecutive_failures = 0
            self.last_ok_time = now_str

            return {
                "fbr_status": "OK",
                "fbr_connectivity_status": "CONNECTED",
                "fbr_ok": True,
                "latency_ms": elapsed_ms,
                "http_status": resp.status_code,
                "last_ok_time": self.last_ok_time,
                "last_check_time": now_str,
                "consecutive_failures": 0,
                "error_text": None,
                "record_history": True
            }
        except Exception as e:
            self.consecutive_failures += 1
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                "fbr_status": "DOWN",
                "fbr_connectivity_status": "DISCONNECTED",
                "fbr_ok": False,
                "latency_ms": elapsed_ms,
                "http_status": None,
                "last_ok_time": self.last_ok_time,
                "last_check_time": now_str,
                "consecutive_failures": self.consecutive_failures,
                "error_text": f"Remote FBR probe failed: {e}",
                "record_history": True
            }

    def get_latest_summary(self) -> Dict[str, Any]:
        if self.cached_result:
            return self.cached_result
        return self.check()
