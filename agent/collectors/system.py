try:
    import psutil
except ImportError:
    psutil = None
from typing import Dict, Any, List

def collect_system_metrics() -> Dict[str, Any]:
    """Collects CPU %, RAM %, RAM used MB, and per-disk capacity/usage."""
    result: Dict[str, Any] = {
        "cpu_pct": 0.0,
        "ram_pct": 0.0,
        "ram_used_mb": 0.0,
        "disks": []
    }

    try:
        # CPU % (short non-blocking measurement)
        result["cpu_pct"] = round(psutil.cpu_percent(interval=0.1), 1)
    except Exception:
        result["cpu_pct"] = 0.0

    try:
        # RAM usage
        mem = psutil.virtual_memory()
        result["ram_pct"] = round(mem.percent, 1)
        result["ram_used_mb"] = round(mem.used / (1024 * 1024), 1)
    except Exception:
        pass

    try:
        # Fixed disk partitions
        disks: List[Dict[str, Any]] = []
        partitions = psutil.disk_partitions(all=False)
        for part in partitions:
            # Skip cd-rom or pseudo loopback if any
            if "cdrom" in part.opts or part.fstype == "":
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb = round(usage.total / (1024 ** 3), 1)
                used_gb = round(usage.used / (1024 ** 3), 1)
                free_gb = round(usage.free / (1024 ** 3), 1)
                pct = round(usage.percent, 1)

                disks.append({
                    "mount": part.mountpoint.rstrip("\\"),
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "pct": pct
                })
            except (PermissionError, OSError):
                continue
        result["disks"] = disks
    except Exception:
        result["disks"] = []

    return result
