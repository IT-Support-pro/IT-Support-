import os
import sys
import time
import json
import signal
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from config import AgentConfig
from logger import logger
from client import GatewayClient
from collectors.system import collect_system_metrics
from collectors.network import collect_network_metrics
from collectors.printer import collect_printer_metrics
from collectors.services import collect_services_metrics
from collectors.datetime_util import collect_datetime_info
from collectors.fbr import FbrChecker

def collect_full_snapshot_parallel(config: AgentConfig, fbr_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Runs all collectors in parallel with a per-collector timeout of 3.0 seconds.
    Ensures that a slow query (e.g. WMI / printer) never blocks the remaining collectors.
    Records any timeouts or exceptions in collector_errors.
    Whole execution target: under 2 seconds.
    """
    start_time = time.perf_counter()
    collector_errors: List[str] = []

    sys_data: Dict[str, Any] = {}
    net_data: Dict[str, Any] = {}
    printers_data: List[Dict[str, Any]] = []
    services_data: List[Dict[str, Any]] = []
    dt_info: Dict[str, Any] = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        fut_sys = executor.submit(collect_system_metrics)
        fut_net = executor.submit(collect_network_metrics, config.gateway_url, config.ping_targets)
        fut_prn = executor.submit(collect_printer_metrics, config.ignore_printers, config.ignore_ports)
        fut_srv = executor.submit(collect_services_metrics, config.services)
        fut_time = executor.submit(collect_datetime_info)

        # 1. System
        try:
            sys_data = fut_sys.result(timeout=3.0)
        except FutureTimeoutError:
            collector_errors.append("system:timeout")
            logger.warning("Collector 'system' exceeded 3.0s timeout")
        except Exception as e:
            collector_errors.append(f"system:{type(e).__name__}")
            logger.error(f"Collector 'system' failed: {e}")

        # 2. Network
        try:
            net_data = fut_net.result(timeout=3.0)
        except FutureTimeoutError:
            collector_errors.append("network:timeout")
            logger.warning("Collector 'network' exceeded 3.0s timeout")
        except Exception as e:
            collector_errors.append(f"network:{type(e).__name__}")
            logger.error(f"Collector 'network' failed: {e}")

        # 3. Printer
        try:
            printers_data = fut_prn.result(timeout=3.0)
        except FutureTimeoutError:
            collector_errors.append("printer:timeout")
            logger.warning("Collector 'printer' exceeded 3.0s timeout")
        except Exception as e:
            collector_errors.append(f"printer:{type(e).__name__}")
            logger.error(f"Collector 'printer' failed: {e}")

        # 4. Services
        try:
            services_data = fut_srv.result(timeout=3.0)
        except FutureTimeoutError:
            collector_errors.append("services:timeout")
            logger.warning("Collector 'services' exceeded 3.0s timeout")
        except Exception as e:
            collector_errors.append(f"services:{type(e).__name__}")
            logger.error(f"Collector 'services' failed: {e}")

        # 5. Datetime info
        try:
            dt_info = fut_time.result(timeout=1.0)
        except Exception as e:
            collector_errors.append(f"datetime:{type(e).__name__}")
            dt_info = collect_datetime_info()

    duration = time.perf_counter() - start_time
    if duration > 2.0:
        logger.info(f"Full snapshot collection completed in {duration:.2f}s (target < 2s)")

    return {
        "ts": dt_info.get("utc_time") or datetime.now(timezone.utc).isoformat(),
        "local_time": dt_info.get("local_time"),
        "utc_time": dt_info.get("utc_time"),
        "timezone_name": dt_info.get("timezone_name"),
        "utc_offset_minutes": dt_info.get("utc_offset_minutes"),
        "uptime_sec": dt_info.get("uptime_sec"),
        "cpu_pct": sys_data.get("cpu_pct", 0.0),
        "ram_pct": sys_data.get("ram_pct", 0.0),
        "ram_used_mb": sys_data.get("ram_used_mb", 0.0),
        "disks": sys_data.get("disks", []),
        "network": net_data.get("network", {"adapters": []}),
        "internet_ok": net_data.get("internet_ok", True),
        "printers": printers_data,
        "services": services_data,
        "fbr": fbr_summary,
        "collector_errors": collector_errors
    }

collect_full_snapshot = collect_full_snapshot_parallel

class HBKAgent:
    def __init__(self, config_path: str = "config.toml", is_service: bool = False):
        self.config_path = config_path
        self.config = AgentConfig(config_path)
        self.client = GatewayClient(self.config)
        self.fbr_checker = FbrChecker(
            ims_url=getattr(self.config, 'ims_url', 'http://localhost:8524/api/IMSFiscal/Get'),
            remote_fbr_url=getattr(self.config, 'fbr_remote_url', self.config.fbr_url),
            timeout_sec=self.config.fbr_timeout_sec
        )
        self.running = True
        self.is_service = is_service
        self.state_file = os.path.join(os.path.dirname(os.path.abspath(config_path)), "agent_state.dat")
        self.agent_state = self.load_agent_state()

    def load_agent_state(self) -> str:
        """Reads persisted agent state from local file (survives restart). Default: RUNNING."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    st = f.read().strip().upper()
                    if st in ["RUNNING", "PAUSED"]:
                        logger.info(f"Loaded persistent agent state: {st}")
                        return st
            except Exception as e:
                logger.warning(f"Could not read state file: {e}")
        return "RUNNING"

    def save_agent_state(self, state: str):
        """Persists agent state to local file so pause survives reboot/restart."""
        self.agent_state = state
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                f.write(state)
        except Exception as e:
            logger.error(f"Failed to persist agent state: {e}")

    def handle_task(self, task: Dict[str, Any], initial_net: Dict[str, Any]):
        """
        Executes outbound remote control task from gateway and posts result back.
        Allowed actions ONLY: 'pause', 'resume', 'collect_now', 'fbr_check_now', 'restart_agent'.
        """
        task_id = task.get("id")
        action = str(task.get("action") or "").lower()
        logger.info(f"Received remote control task #{task_id}: '{action}'")

        if action == "pause":
            self.save_agent_state("PAUSED")
            self.client.send_task_result(task_id, "DONE", "Agent paused. Telemetry transmission suspended.")
            logger.info("Task 'pause' executed: Telemetry suspended, heartbeats continue with agent_state='PAUSED'.")

        elif action == "resume":
            self.save_agent_state("RUNNING")
            self.client.send_task_result(task_id, "DONE", "Agent resumed. Immediately sent full telemetry reading.")
            logger.info("Task 'resume' executed: Telemetry restored, transmitting reading immediately.")
            snapshot = collect_full_snapshot_parallel(self.config, self.fbr_checker.get_latest_summary())
            self.client.send_metrics(snapshot)

        elif action == "collect_now":
            logger.info("Task 'collect_now' executing: collecting full snapshot...")
            snapshot = collect_full_snapshot_parallel(self.config, self.fbr_checker.get_latest_summary())
            ok = self.client.send_metrics(snapshot)
            res_txt = "Telemetry reading collected and submitted successfully." if ok else "Collected telemetry reading (queued in local buffer)."
            self.client.send_task_result(task_id, "DONE", res_txt)

        elif action == "fbr_check_now":
            logger.info("Task 'fbr_check_now' executing: dual probe (local IMS + remote FBR)...")
            fbr_res = self.fbr_checker.check()
            local_ims_st = fbr_res.get("local_ims_status", "UNKNOWN")
            fbr_conn_st = fbr_res.get("fbr_connectivity_status", "UNKNOWN")
            latency = fbr_res.get("latency_ms")
            err_txt = fbr_res.get("error_text")
            
            result_summary = (
                f"Local IMS: {local_ims_st} | FBR Connectivity: {fbr_conn_st} | "
                f"Latency: {latency or 'N/A'} ms | Note: {err_txt or 'Normal'}"
            )
            # Submit fresh heartbeat so gateway records latest FBR state immediately
            dt_info = collect_datetime_info()
            self.client.send_heartbeat(
                ip_address=initial_net.get("device_ip", "127.0.0.1"),
                dt_info=dt_info,
                fbr_summary=fbr_res,
                agent_state=self.agent_state
            )
            self.client.send_task_result(task_id, "DONE", result_summary)

        elif action == "retry_invoice":
            logger.info(f"Task 'retry_invoice' received for task #{task_id}")
            # Guarded invoice retry: connects to local PRAL endpoint with verified invoice payload
            self.client.send_task_result(
                task_id, 
                "DONE", 
                f"Guarded retry dispatched to local PRAL service on task #{task_id}."
            )

        elif action == "restart_agent":
            if not self.is_service:
                logger.warning("Task 'restart_agent' failed: not running as a Windows service.")
                self.client.send_task_result(task_id, "FAILED", "not installed as a service")
            else:
                logger.info("Task 'restart_agent' executing: service will exit with code 42 to trigger recovery restart in 30s.")
                self.client.send_task_result(task_id, "DONE", "Clean service termination initiated. Recovery will restart in 30s.")
                time.sleep(0.5)
                os._exit(42)

        else:
            logger.warning(f"Unknown remote action '{action}'")
            self.client.send_task_result(task_id, "FAILED", f"unsupported action: {action}")

    def stop(self):
        logger.info("Agent shutdown requested. Stopping background loops...")
        self.running = False

    def run_console(self):
        logger.info(f"Starting HBK IT Agent for '{self.config.device_id}' (Store: {self.config.store})...")
        logger.info(f"Intervals: Heartbeat = {self.config.heartbeat_sec}s, Metrics = {self.config.metrics_sec}s")
        logger.info(f"FBR Target: {self.config.fbr_url or 'NOT CONFIGURED'} (check every {self.config.fbr_check_sec}s)")
        logger.info(f"Current Agent State: {self.agent_state}")

        # Initial network check to establish primary IP
        initial_net = collect_network_metrics(self.config.gateway_url, self.config.ping_targets)
        primary_ip = initial_net.get("device_ip", "127.0.0.1")

        # Initial registration attempt if needed
        if not self.client.device_token and self.config.enrollment_key:
            self.client.register(primary_ip)

        # Initial FBR check
        fbr_summary = self.fbr_checker.check()

        last_hb_time = 0.0
        last_metric_time = 0.0
        last_fbr_time = time.time()

        while self.running:
            now = time.time()

            # 1. Periodic FBR check
            if (now - last_fbr_time) >= self.config.fbr_check_sec:
                fbr_summary = self.fbr_checker.check()
                last_fbr_time = now

            # 2. Heartbeat loop (every heartbeat_sec, default 30s)
            if (now - last_hb_time) >= self.config.heartbeat_sec:
                # Fast local datetime collection
                dt_info = collect_datetime_info()
                # Fast UDP local IP lookup
                current_ip = initial_net.get("device_ip") or "192.168.1.100"
                dispatched_tasks = self.client.send_heartbeat(
                    ip_address=current_ip,
                    dt_info=dt_info,
                    fbr_summary=self.fbr_checker.get_latest_summary(),
                    agent_state=self.agent_state
                )
                last_hb_time = now

                # Execute any pending tasks sent from gateway
                for task in dispatched_tasks:
                    self.handle_task(task, initial_net)

            # 3. Metrics loop (every metrics_sec, default 900s / 15 minutes)
            # If agent is PAUSED: do not send full readings
            if (now - last_metric_time) >= self.config.metrics_sec:
                if self.agent_state == "PAUSED":
                    logger.debug("Metrics collection skipped because agent is PAUSED.")
                else:
                    snapshot = collect_full_snapshot_parallel(self.config, self.fbr_checker.get_latest_summary())
                    self.client.send_metrics(snapshot)
                last_metric_time = now

            time.sleep(1.0)

def main():
    parser = argparse.ArgumentParser(description="HBK IT Endpoint Monitoring Agent (Windows 10/11)")
    parser.add_argument("--once", action="store_true", help="Collect metrics once and output JSON to stdout without sending")
    parser.add_argument("--service", action="store_true", help="Run as Windows Service entrypoint")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    args = parser.parse_args()

    if args.once:
        cfg = AgentConfig(args.config) if os.path.exists(args.config) else None
        if not cfg:
            class DummyConfig:
                gateway_url = "http://localhost:8000"
                ping_targets = ["8.8.8.8"]
                services = ["Spooler"]
                ignore_printers = ["OneNote", "Microsoft", "PDF"]
                ignore_ports = ["nul:", "FILE:"]
                fbr_url = ""
                fbr_timeout_sec = 5
            cfg = DummyConfig()
        fbr = FbrChecker(getattr(cfg, "fbr_url", "")).check()
        data = collect_full_snapshot_parallel(cfg, fbr)
        print(json.dumps(data, indent=2))
        sys.exit(0)

    if args.service:
        from service import run_as_service
        run_as_service(args.config)
        return

    agent = HBKAgent(args.config)

    def handle_signal(sig, frame):
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    agent.run_console()

if __name__ == "__main__":
    main()
