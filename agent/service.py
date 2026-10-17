import sys
import time
import threading
import platform

from logger import logger

def run_as_service(config_path: str = "config.toml"):
    """
    Entry point for running as a native Windows Service via pywin32 or NSSM wrapper.
    """
    if platform.system().lower() == "windows":
        try:
            import win32serviceutil
            import win32service
            import win32event
            import servicemanager

            class HBKWindowsService(win32serviceutil.ServiceFramework):
                _svc_name_ = "HBKAgent"
                _svc_display_name_ = "HBK IT Monitoring Agent"
                _svc_description_ = "Collects system, network, printer, and service telemetry and pushes outbound to HBK Gateway."

                def __init__(self, args):
                    super().__init__(args)
                    self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
                    self.is_running = True

                def SvcStop(self):
                    self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                    win32event.SetEvent(self.hWaitStop)
                    self.is_running = False

                def SvcDoRun(self):
                    servicemanager.LogMsg(
                        servicemanager.EVENTLOG_INFORMATION_TYPE,
                        servicemanager.PYS_SERVICE_STARTED,
                        (self._svc_name_, "")
                    )
                    from main import HBKAgent
                    agent = HBKAgent(config_path, is_service=True)
                    t = threading.Thread(target=agent.run_console, daemon=True)
                    t.start()
                    win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
                    agent.stop()

            win32serviceutil.HandleCommandLine(HBKWindowsService)
            return
        except ImportError:
            logger.info("pywin32 service framework not installed. Running service worker in background loop mode.")

    # Fallback to direct loop
    from main import HBKAgent
    agent = HBKAgent(config_path, is_service=True)
    agent.run_console()
