import os
import sys
import re
from typing import List, Dict, Any

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
except ImportError:
    tomllib = None

def _simple_toml_fallback(text: str) -> Dict[str, Any]:
    """Lightweight fallback parser when tomllib/tomli is not yet installed."""
    data: Dict[str, Any] = {}
    current_sec = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_sec = line[1:-1].strip()
            data[current_sec] = {}
            continue
        if "=" in line:
            parts = line.split("=", 1)
            k = parts[0].strip()
            v_raw = parts[1].split("#")[0].strip()
            # Parse booleans, numbers, strings, lists
            if v_raw.lower() == "true":
                val: Any = True
            elif v_raw.lower() == "false":
                val = False
            elif v_raw.isdigit():
                val = int(v_raw)
            elif (v_raw.startswith('"') and v_raw.endswith('"')) or (v_raw.startswith("'") and v_raw.endswith("'")):
                val = v_raw[1:-1]
            elif v_raw.startswith("[") and v_raw.endswith("]"):
                inner = v_raw[1:-1]
                items = [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
                val = items
            else:
                val = v_raw
            if current_sec:
                data[current_sec][k] = val
            else:
                data[k] = val
    return data

class AgentConfig:
    def __init__(self, config_path: str = "config.toml"):
        self.config_path = os.path.abspath(config_path)
        self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        if tomllib is not None:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)
        else:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = _simple_toml_fallback(f.read())

        gateway = data.get("gateway", {})
        self.gateway_url = str(gateway.get("url", "http://localhost:8000")).rstrip("/")
        self.verify_tls = bool(gateway.get("verify_tls", True))

        device = data.get("device", {})
        self.device_id = str(device.get("device_id", "POS-01"))
        self.store = str(device.get("store", "ISL-01"))
        self.device_type = str(device.get("device_type", "POS"))
        self.enrollment_key = str(device.get("enrollment_key", ""))

        collect = data.get("collect", {})
        # Defaults: heartbeat_sec = 30, metrics_sec = 900 (15 min)
        self.heartbeat_sec = int(collect.get("heartbeat_sec", 30))
        self.metrics_sec = int(collect.get("metrics_sec", 900))
        self.services = collect.get("services", ["Spooler"])
        self.ping_targets = collect.get("ping_targets", ["8.8.8.8", "1.1.1.1"])

        # Printer ignore configuration
        self.ignore_printers: List[str] = collect.get(
            "ignore_printers",
            ["OneNote", "Microsoft", "XPS", "PDF", "Fax", "AnyDesk", "RustDesk", "Send To"]
        )
        self.ignore_ports: List[str] = collect.get(
            "ignore_ports",
            ["nul:", "PORTPROMPT:", "SHRFAX:", "FILE:", "AD_Port", "RustDesk Printer"]
        )

        # FBR connectivity configuration
        fbr = data.get("fbr", {})
        self.fbr_url = str(fbr.get("url", "")).strip()
        self.fbr_timeout_sec = int(fbr.get("timeout_sec", 5))
        self.fbr_check_sec = int(fbr.get("check_sec", 300))

        limits = data.get("limits", {})
        self.max_buffer_mb = int(limits.get("max_buffer_mb", 20))

    def blank_enrollment_key(self):
        """Blanks the enrollment_key from config.toml after first registration."""
        if not os.path.exists(self.config_path):
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Replace enrollment_key = "..." with enrollment_key = ""
            new_content = re.sub(
                r'(enrollment_key\s*=\s*)[^\r\n]+',
                r'\1""',
                content
            )

            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.enrollment_key = ""
        except Exception:
            pass
