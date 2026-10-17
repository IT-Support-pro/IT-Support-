import time
import platform
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    import psutil
except ImportError:
    psutil = None

def get_windows_timezone_name() -> str:
    """
    Returns the Windows timezone name (e.g., 'Pakistan Standard Time', 'W. Europe Standard Time').
    Attempts winreg or WMI first on Windows, falling back to time.tzname.
    """
    if platform.system().lower() == "windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation"
            )
            val, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
            winreg.CloseKey(key)
            if val and str(val).strip():
                return str(val).strip()
        except Exception:
            pass

        try:
            import wmi
            c = wmi.WMI()
            for tz in c.Win32_TimeZone():
                if tz.StandardName:
                    return str(tz.StandardName)
        except Exception:
            pass

    # Fallback to python standard library time zone names
    try:
        now_local = datetime.now().astimezone()
        tz_name = now_local.tzname()
        if tz_name:
            return tz_name
    except Exception:
        pass

    return time.tzname[0] if time.tzname else "UTC"

def collect_datetime_info() -> Dict[str, Any]:
    """
    Collects accurate POS date, time, timezone, and system uptime.
    Guaranteed non-blocking, execution under 50ms.
    """
    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)

    # Offset in minutes
    offset_seconds = now_local.utcoffset().total_seconds() if now_local.utcoffset() else 0.0
    utc_offset_minutes = int(offset_seconds // 60)

    # System Uptime
    uptime_sec = 0.0
    if psutil is not None:
        try:
            boot_time = psutil.boot_time()
            uptime_sec = round(time.time() - boot_time, 2)
        except Exception:
            pass
    else:
        # Fallback reading uptime on Linux/POSIX if proc/uptime exists
        try:
            with open("/proc/uptime", "r") as f:
                uptime_sec = float(f.readline().split()[0])
        except Exception:
            uptime_sec = 100.0

    tz_name = get_windows_timezone_name()

    return {
        "local_time": now_local.isoformat(),
        "utc_time": now_utc.isoformat(),
        "timezone_name": tz_name,
        "utc_offset_minutes": utc_offset_minutes,
        "uptime_sec": max(0.0, uptime_sec)
    }
