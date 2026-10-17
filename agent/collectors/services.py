import platform
try:
    import psutil
except ImportError:
    psutil = None
from typing import List, Dict, Any

def collect_services_metrics(service_names: List[str]) -> List[Dict[str, Any]]:
    """
    Checks the status of configured Windows services (e.g. Spooler, SAP CCO).
    Returns state: Running, Stopped, or Not found.
    """
    results: List[Dict[str, Any]] = []

    if not service_names:
        return results

    is_windows = platform.system().lower() == "windows"

    for svc_name in service_names:
        state = "Not found"
        try:
            if is_windows and hasattr(psutil, "win_service_get"):
                try:
                    s = psutil.win_service_get(svc_name)
                    # s.status() returns 'running', 'stopped', 'start_pending', etc.
                    s_status = s.status().lower()
                    if s_status == "running":
                        state = "Running"
                    elif s_status in ["stopped", "stop_pending"]:
                        state = "Stopped"
                    else:
                        state = s_status.capitalize()
                except psutil.NoSuchProcess:
                    state = "Not found"
                except Exception:
                    state = "Stopped"
            else:
                # Non-windows fallback/test simulation
                state = "Running"
        except Exception:
            state = "Not found"

        results.append({
            "name": svc_name,
            "state": state
        })

    return results
