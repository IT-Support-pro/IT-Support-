import re
import platform
import subprocess
from typing import List, Dict, Any, Optional

DEFAULT_IGNORE_PRINTERS = [
    "onenote", "microsoft", "xps", "pdf", "fax", "anydesk", "rustdesk", "send to"
]

DEFAULT_IGNORE_PORTS = [
    "nul:", "portprompt:", "shrfax:", "file:", "ad_port", "rustdesk printer"
]

def clean_copy_suffix(name: str) -> str:
    """Removes '(copy N)' or '(copy of N)' suffixes from printer names."""
    # Matches (Copy 1), (Copy of 1), (Copy of 2), etc.
    cleaned = re.sub(r'\s*\(\s*copy(?:\s+of)?\s+\d+\s*\)', '', name, flags=re.IGNORECASE)
    return cleaned.strip()

def is_ignored_printer(name: str, port: str, ignore_printers: List[str] = None, ignore_ports: List[str] = None) -> bool:
    """Checks whether a printer is virtual, software-based, or remote-desktop redirected."""
    name_lower = (name or "").lower()
    port_lower = (port or "").lower()

    pr_ignores = [w.lower() for w in (ignore_printers or DEFAULT_IGNORE_PRINTERS)]
    port_ignores = [p.lower() for p in (ignore_ports or DEFAULT_IGNORE_PORTS)]

    # 1. Skip if name matches any ignore word
    if any(ign in name_lower for ign in pr_ignores):
        return True

    # 2. Skip if port matches ignore list
    if any(ign == port_lower for ign in port_ignores):
        return True

    # 3. Skip if port starts with Microsoft.Office
    if port_lower.startswith("microsoft.office"):
        return True

    return False

def filter_and_deduplicate_printers(
    raw_printers: List[Dict[str, Any]],
    ignore_printers: List[str] = None,
    ignore_ports: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Filters out virtual/ignored printers and deduplicates multiple copies
    pointing to the same port and driver.
    """
    filtered = []
    seen_keys = set()

    for p in raw_printers:
        name = str(p.get("name") or "").strip()
        port = str(p.get("port") or "").strip()
        driver = str(p.get("driver") or "").strip()

        if is_ignored_printer(name, port, ignore_printers, ignore_ports):
            continue

        base_name = clean_copy_suffix(name)
        # Deduplication key based on port, base name or driver
        dedup_key = f"{port.lower()}|{driver.lower() or base_name.lower()}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        filtered.append({
            "name": name,
            "port": port,
            "status": p.get("status", "Idle"),
            "queue": int(p.get("queue", 0)),
            "is_offline": bool(p.get("is_offline", False))
        })

    return filtered

def collect_printer_metrics(
    ignore_printers: List[str] = None,
    ignore_ports: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Collects real physical receipt/kitchen printers via WMI on Windows.
    Applies aggressive virtual printer filtering and deduplication.
    """
    raw_printers: List[Dict[str, Any]] = []

    if platform.system().lower() != "windows":
        # On non-Windows platforms (e.g. testing), return empty or test items
        return []

    # 1. Query WMI Win32_Printer
    try:
        import wmi
        c = wmi.WMI()
        for p in c.Win32_Printer():
            name = str(p.Name or "Unknown")
            port = str(p.PortName or "")
            queue = int(p.Jobs or 0)
            offline = bool(p.WorkOffline or False)
            status_code = getattr(p, "PrinterStatus", 3)
            driver = str(getattr(p, "DriverName", ""))

            # Status mapping
            # 3 = Idle, 4 = Printing, 5 = Warmup, 1 = Other, 2 = Unknown, 7 = Offline
            status_text = "Offline" if offline else "Idle"
            if status_code == 4:
                status_text = "Printing"
            elif status_code == 7 or offline:
                status_text = "Offline"
                offline = True

            raw_printers.append({
                "name": name,
                "port": port,
                "driver": driver,
                "status": status_text,
                "queue": queue,
                "is_offline": offline
            })
    except Exception:
        pass

    # 2. Fallback to PowerShell Get-CimInstance Win32_Printer if WMI returned nothing
    if not raw_printers:
        try:
            ps_cmd = (
                "Get-CimInstance Win32_Printer | "
                "Select-Object Name, PortName, DriverName, PrinterStatus, WorkOffline | "
                "ConvertTo-Json -Compress"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=2.5
            )
            if proc.returncode == 0 and proc.stdout.strip():
                import json
                data = json.loads(proc.stdout)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    name = str(item.get("Name") or "Printer")
                    port = str(item.get("PortName") or "")
                    driver = str(item.get("DriverName") or "")
                    offline = bool(item.get("WorkOffline", False))
                    raw_printers.append({
                        "name": name,
                        "port": port,
                        "driver": driver,
                        "status": "Offline" if offline else "Idle",
                        "queue": 0,
                        "is_offline": offline
                    })
        except Exception:
            pass

    return filter_and_deduplicate_printers(raw_printers, ignore_printers, ignore_ports)
