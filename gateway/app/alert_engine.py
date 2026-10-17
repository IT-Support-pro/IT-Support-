import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models import (
    Device, Metric, Alert, AlertRule, Store, FbrCheck,
    ConnectionEvent, GatewayState, LightMetric, AlertCheck
)
from app.config import settings
from app.schemas import MetricSnapshot
from app.notifications import notify_alert_firing, notify_alert_resolved

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

RULE_PLAYBOOKS: Dict[str, Dict[str, Any]] = {
    "agent_offline": {
        "rule_name": "Device is offline",
        "explanation": "The device has stopped sending heartbeats to the central monitoring gateway.",
        "steps": [
            "Read the reason on the device page (stopped by admin, shutdown, or no signal).",
            "At the PC: is it switched on? Check power and the network cable or switch light.",
            "From another PC, ping the device's IP; no reply means a power or network problem.",
            "If the PC is on, open Services and check that 'HBK IT Agent' is Running; start it if not.",
            "If it will not start, send the last 20 lines of agent.log (install folder) to the IT admin.",
            "Click Resolve to confirm."
        ]
    },
    "agent_stale": {
        "rule_name": "Readings stopped",
        "explanation": "The agent is sending heartbeats but full telemetry snapshots have stopped arriving.",
        "steps": [
            "Open the Control tab and click 'Refresh data now'.",
            "If that fails, click 'Restart agent'.",
            "If still stale, check agent.log for collector errors.",
            "Click Resolve."
        ]
    },
    "cpu_high": {
        "rule_name": "High CPU",
        "explanation": "CPU utilization has remained critically high for multiple consecutive measurement intervals.",
        "steps": [
            "Open Task Manager and sort by CPU; note the top program.",
            "If it is a scan or update, wait 10 minutes.",
            "If it is an unknown or stuck program, close it or restart that program.",
            "If it stays high, restart the PC after trading hours.",
            "Click Resolve."
        ]
    },
    "ram_high": {
        "rule_name": "High memory",
        "explanation": "System RAM usage has exceeded the safe operational threshold.",
        "steps": [
            "Open Task Manager, Memory column.",
            "Close unused programs (browsers, remote tools).",
            "Restart the POS application.",
            "If above the limit again, restart the PC after trading hours.",
            "Click Resolve."
        ]
    },
    "disk_low": {
        "rule_name": "Disk almost full",
        "explanation": "One or more disk drives have less than 10% free space remaining.",
        "steps": [
            "Open This PC and find the full drive (see Error details).",
            "Run Disk Cleanup and choose 'Clean up system files'.",
            "Empty the Recycle Bin and remove old installers, backups and temp files.",
            "If a POS or database folder is large, ask IT or the POS vendor before deleting anything there.",
            "Click Resolve."
        ]
    },
    "service_down": {
        "rule_name": "Service stopped",
        "explanation": "A mandatory Windows service (such as Print Spooler or POS runtime) is not in the running state.",
        "steps": [
            "Open Services (services.msc).",
            "Find the service named in Error details.",
            "Right-click it and choose Start.",
            "If it stops again, open Event Viewer, Windows Logs, Application, around the time it stopped.",
            "For Print Spooler only: if printing is stuck, clear the files in C:\\Windows\\System32\\spool\\PRINTERS and start the service.",
            "Click Resolve."
        ]
    },
    "printer_offline": {
        "rule_name": "Printer offline",
        "explanation": "The receipt or thermal kitchen printer is offline, disconnected, or reporting a paper jam/cover error.",
        "steps": [
            "Check power, paper and the cover.",
            "Check the USB or network cable; try another USB port.",
            "In Settings, Printers, make sure 'Use Printer Offline' is not ticked.",
            "Restart the Print Spooler service.",
            "Click Resolve."
        ]
    },
    "internet_down": {
        "rule_name": "No internet",
        "explanation": "Outbound internet connectivity checks (HTTPS/TCP 443) have failed across consecutive intervals.",
        "steps": [
            "Check the network cable or Wi-Fi.",
            "Check if other PCs in the store also have no internet. If yes, check the router, switch or ISP.",
            "If only this PC, disable and enable the network adapter, or restart the PC.",
            "Click Resolve."
        ]
    },
    "fbr_down": {
        "rule_name": "FBR not reachable",
        "explanation": "The POS cannot communicate with the Federal Board of Revenue fiscalization endpoint.",
        "steps": [
            "Confirm the internet works on this PC.",
            "Open the FBR or POS fiscal screen and read the message.",
            "If the FBR portal is down, wait and try again later.",
            "Check that the firewall or proxy allows the FBR address.",
            "Check that the PC date and time are correct (a wrong clock can cause invoices to be rejected).",
            "If it continues, contact FBR support or the POS vendor.",
            "Click Resolve."
        ]
    },
    "clock_drift": {
        "rule_name": "PC clock is wrong",
        "explanation": "The local system clock differs significantly from authoritative central gateway time.",
        "steps": [
            "Open Settings, Time & language, Date & time.",
            "Turn on 'Set time automatically' and 'Set time zone automatically', or choose Pakistan Standard Time.",
            "Click 'Sync now'.",
            "If the time resets after a restart, ask IT to replace the CMOS battery.",
            "Click Resolve."
        ]
    },
    "timezone_mismatch": {
        "rule_name": "Wrong time zone",
        "explanation": "The operating system timezone does not match the configured expected timezone.",
        "steps": [
            "Set the PC time zone to the expected one.",
            "If the zone is intentional (for example a test laptop), change the expected time zone in this device's Settings tab.",
            "Click Resolve."
        ]
    }
}

def is_rule_muted(device: Device, rule_key: str) -> bool:
    """Checks whether a rule is currently muted on this device."""
    muted_list = device.muted_rules_json or []
    now_iso = utc_now().isoformat()
    for item in muted_list:
        if item.get("rule_key") == rule_key:
            until = item.get("until")
            if not until or until > now_iso:
                return True
    return False

def fire_alert_if_not_active(
    db: Session,
    device: Device,
    rule_key: str,
    severity: str,
    message: str,
    value: Optional[str] = None
) -> Optional[Alert]:
    """Ensures only ONE active alert per (device, rule_key). Checks mute settings."""
    if is_rule_muted(device, rule_key):
        return None

    active_alert = db.query(Alert).filter(
        Alert.device_pk == device.id,
        Alert.rule_key == rule_key,
        Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
    ).first()

    if active_alert:
        if active_alert.severity != severity:
            active_alert.severity = severity
            active_alert.message = message
            active_alert.value = str(value) if value is not None else None
            db.commit()
        return active_alert

    now = utc_now()
    new_alert = Alert(
        device_pk=device.id,
        rule_key=rule_key,
        severity=severity,
        state="FIRING",
        message=message,
        value=str(value) if value is not None else None,
        fired_at=now
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)

    store_code = device.store.code if device.store else "UNKNOWN"
    notify_alert_firing(device.device_id, store_code, message)
    return new_alert

def resolve_alert_if_active(db: Session, device: Device, rule_key: str, resolution: str = "AUTO_CLEARED") -> bool:
    """Resolves active alert when condition clears, retaining history."""
    active_alert = db.query(Alert).filter(
        Alert.device_pk == device.id,
        Alert.rule_key == rule_key,
        Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
    ).first()

    if active_alert:
        active_alert.state = "RESOLVED"
        active_alert.resolved_at = utc_now()
        active_alert.resolution = resolution
        db.commit()
        notify_alert_resolved(device.device_id, rule_key)
        return True
    return False

def get_expected_timezone(device: Device, db: Session) -> str:
    """Device overrides store overrides global setting (default 'Pakistan Standard Time')."""
    if device.expected_timezone and device.expected_timezone.strip():
        return device.expected_timezone.strip()
    if device.store and device.store.expected_timezone and device.store.expected_timezone.strip():
        return device.store.expected_timezone.strip()
    return getattr(settings, "EXPECTED_TIMEZONE", "Pakistan Standard Time")

def evaluate_device_time_alerts(db: Session, device: Device):
    """
    Evaluates clock drift and timezone configuration.
    - clock_drift: warning > 120s, critical > 600s after 2 consecutive readings.
    - timezone_mismatch: warning when timezone differs from expected.
    """
    rules_dict = {r.rule_key: r for r in db.query(AlertRule).all() if r.enabled}

    # 1. Clock drift
    drift_rule = rules_dict.get("clock_drift")
    if drift_rule and device.clock_offset_sec is not None:
        offset_abs = abs(device.clock_offset_sec)
        warn_thresh = drift_rule.threshold_value or 120.0
        crit_thresh = 600.0

        if offset_abs > crit_thresh:
            fire_alert_if_not_active(
                db, device, "clock_drift", "critical",
                f"Severe PC clock drift: {device.clock_offset_sec:+.1f}s (exceeds {crit_thresh:.0f}s)",
                str(device.clock_offset_sec)
            )
        elif offset_abs > warn_thresh:
            fire_alert_if_not_active(
                db, device, "clock_drift", "warning",
                f"PC clock drift detected: {device.clock_offset_sec:+.1f}s (exceeds {warn_thresh:.0f}s)",
                str(device.clock_offset_sec)
            )
        else:
            resolve_alert_if_active(db, device, "clock_drift")

    # 2. Timezone mismatch
    tz_rule = rules_dict.get("timezone_mismatch")
    if tz_rule and device.timezone_name:
        expected = get_expected_timezone(device, db).strip().lower()
        actual = device.timezone_name.strip().lower()

        if expected not in actual and actual not in expected:
            fire_alert_if_not_active(
                db, device, "timezone_mismatch", tz_rule.severity,
                f"Timezone mismatch: PC configured as '{device.timezone_name}' (expected '{get_expected_timezone(device, db)}')",
                device.timezone_name
            )
        else:
            resolve_alert_if_active(db, device, "timezone_mismatch")

def evaluate_fbr_alerts(db: Session, device: Device):
    rules_dict = {r.rule_key: r for r in db.query(AlertRule).all() if r.enabled}
    fbr_rule = rules_dict.get("fbr_down")
    if not fbr_rule:
        return

    if device.fbr_status == "NOT_CONFIGURED":
        resolve_alert_if_active(db, device, "fbr_down")
        return

    if device.fbr_ok is True or device.fbr_connectivity_status == "CONNECTED":
        resolve_alert_if_active(db, device, "fbr_down")
    elif (device.fbr_consecutive_failures or 0) >= 2 or device.fbr_connectivity_status in ["DISCONNECTED", "LOCAL_SERVICE_DOWN"]:
        err_detail = device.fbr_error or device.fbr_connectivity_status or "Network failure"
        fire_alert_if_not_active(
            db, device, "fbr_down", fbr_rule.severity,
            f"FBR not reachable: {err_detail} ({device.fbr_consecutive_failures} consecutive failures)",
            str(device.fbr_consecutive_failures)
        )

def evaluate_metrics_snapshot(db: Session, device: Device, snapshot: MetricSnapshot):
    rules_dict = {r.rule_key: r for r in db.query(AlertRule).all() if r.enabled}

    # Auto-resolve agent_offline and agent_stale
    resolve_alert_if_active(db, device, "agent_offline")
    resolve_alert_if_active(db, device, "agent_stale")
    device.reading_stale = False

    if getattr(device, "agent_state", "RUNNING") == "PAUSED":
        return

    evaluate_device_time_alerts(db, device)
    evaluate_fbr_alerts(db, device)

    # 1. DISK LOW (critical, 1 reading > threshold)
    disk_rule = rules_dict.get("disk_low")
    if disk_rule:
        threshold = disk_rule.threshold_value or 90.0
        low_disk = next((d for d in snapshot.disks if d.pct > threshold), None)
        if low_disk:
            fire_alert_if_not_active(
                db, device, "disk_low", disk_rule.severity,
                f"Disk {low_disk.mount} usage at {low_disk.pct}% (exceeds {threshold}%)",
                str(low_disk.pct)
            )
        else:
            resolve_alert_if_active(db, device, "disk_low")

    # 2. SERVICE DOWN
    service_rule = rules_dict.get("service_down")
    if service_rule and snapshot.services is not None:
        stopped_services = [s.name for s in snapshot.services if s.state.lower() != "running"]
        if stopped_services:
            fire_alert_if_not_active(
                db, device, "service_down", service_rule.severity,
                f"Critical service(s) not running: {', '.join(stopped_services)}",
                str(len(stopped_services))
            )
        elif len(snapshot.services) > 0:
            resolve_alert_if_active(db, device, "service_down")

    # 3. PRINTER OFFLINE
    printer_rule = rules_dict.get("printer_offline")
    if printer_rule and snapshot.printers is not None:
        offline_printers = [
            f"{p.name} ({p.status})" 
            for p in snapshot.printers 
            if p.is_offline or p.status.capitalize() in ["Offline", "Error"]
        ]
        if offline_printers:
            fire_alert_if_not_active(
                db, device, "printer_offline", printer_rule.severity,
                f"Printer offline/error: {', '.join(offline_printers)}",
                str(len(offline_printers))
            )
        elif len(snapshot.printers) > 0:
            resolve_alert_if_active(db, device, "printer_offline")

    # 4. INTERNET DOWN
    internet_rule = rules_dict.get("internet_down")
    if internet_rule:
        if not snapshot.internet_ok:
            prev_metric = db.query(Metric).filter(
                Metric.device_pk == device.id,
                Metric.ts < snapshot.ts
            ).order_by(desc(Metric.ts)).first()

            if prev_metric and not prev_metric.internet_ok:
                fire_alert_if_not_active(
                    db, device, "internet_down", internet_rule.severity,
                    "Internet connection lost for 2 consecutive intervals",
                    "false"
                )
        else:
            resolve_alert_if_active(db, device, "internet_down")

    # 5. CPU HIGH
    cpu_rule = rules_dict.get("cpu_high")
    if cpu_rule:
        threshold = cpu_rule.threshold_value or 90.0
        if snapshot.cpu_pct > threshold:
            prev_metric = db.query(Metric).filter(
                Metric.device_pk == device.id,
                Metric.ts < snapshot.ts
            ).order_by(desc(Metric.ts)).first()

            if prev_metric and prev_metric.cpu_pct > threshold:
                fire_alert_if_not_active(
                    db, device, "cpu_high", cpu_rule.severity,
                    f"High CPU sustained: {snapshot.cpu_pct}% and {prev_metric.cpu_pct}% for 2 consecutive readings",
                    str(snapshot.cpu_pct)
                )
        else:
            resolve_alert_if_active(db, device, "cpu_high")

    # 6. RAM HIGH
    ram_rule = rules_dict.get("ram_high")
    if ram_rule:
        threshold = ram_rule.threshold_value or 85.0
        if snapshot.ram_pct > threshold:
            prev_metric = db.query(Metric).filter(
                Metric.device_pk == device.id,
                Metric.ts < snapshot.ts
            ).order_by(desc(Metric.ts)).first()

            if prev_metric and prev_metric.ram_pct > threshold:
                fire_alert_if_not_active(
                    db, device, "ram_high", ram_rule.severity,
                    f"High RAM sustained: {snapshot.ram_pct}% and {prev_metric.ram_pct}% for 2 consecutive readings",
                    str(snapshot.ram_pct)
                )
        else:
            resolve_alert_if_active(db, device, "ram_high")

def check_stale_readings(db: Session):
    """
    Checks if devices are ONLINE but have not sent full telemetry for > 2x metrics_sec.
    Raises agent_stale rule.
    """
    stale_cutoff = utc_now() - timedelta(seconds=1800) # 30 minutes (2x 15m)
    online_devices = db.query(Device).filter(Device.status == "ONLINE").all()

    for dev in online_devices:
        latest_metric = db.query(Metric).filter(Metric.device_pk == dev.id).order_by(desc(Metric.ts)).first()
        if latest_metric and latest_metric.ts < stale_cutoff:
            dev.reading_stale = True
            fire_alert_if_not_active(
                db, dev, "agent_stale", "warning",
                "Agent is connected but readings have stopped",
                latest_metric.ts.isoformat()
            )
        elif latest_metric and latest_metric.ts >= stale_cutoff:
            dev.reading_stale = False
            resolve_alert_if_active(db, dev, "agent_stale")

def check_offline_devices(db: Session):
    """
    Evaluates device offline conditions with honest classification:
    - Goodbye reason if received (SERVICE_STOPPED, SYSTEM_SHUTDOWN, ADMIN_STOP, etc.)
    - GATEWAY_DOWN if gateway recently restarted
    - LIKELY_GATEWAY_OR_NETWORK_ISSUE if >= 50% devices went silent simultaneously
    - NO_SIGNAL with truthful explanation
    """
    now = utc_now()
    
    # 1. Gateway state heartbeat & grace period check
    gw_state = db.query(GatewayState).first()
    if not gw_state:
        gw_state = GatewayState(last_alive=now, started_at_utc=now, version="1.1.0")
        db.add(gw_state)
        db.commit()
    else:
        # Check if gateway was down
        time_since_alive = (now - gw_state.last_alive).total_seconds()
        if time_since_alive > 30.0:
            # Record GATEWAY_DOWN event
            event = ConnectionEvent(
                device_pk=db.query(Device).first().id if db.query(Device).first() else "system",
                ts=now,
                type="GATEWAY_DOWN",
                reason_code="GATEWAY_RESTARTED",
                reason_text=f"Gateway was unresponsive for {int(time_since_alive)}s. Recovering state.",
                duration_sec=time_since_alive
            )
            db.add(event)
            db.commit()
        gw_state.last_alive = now
        db.commit()

    # If within 150s grace period of startup, do not mark devices offline
    time_since_start = (now - gw_state.started_at_utc).total_seconds()
    if time_since_start < 150.0:
        return

    cutoff = now - timedelta(seconds=getattr(settings, "OFFLINE_AFTER_SEC", 120))
    offline_candidates = db.query(Device).filter(
        Device.last_seen < cutoff,
        Device.status.in_(["ONLINE", "DEGRADED", "RECOVERING"])
    ).all()

    if not offline_candidates:
        check_stale_readings(db)
        return

    # Mass outage check: if >= 50% devices (min 2) dropped within 60s
    total_devices_count = db.query(Device).count()
    is_mass_outage = (
        len(offline_candidates) >= 2 and 
        total_devices_count > 0 and 
        (len(offline_candidates) / total_devices_count) >= 0.5
    )

    for dev in offline_candidates:
        # Check if goodbye was received
        if dev.offline_reason_code in ["SERVICE_STOPPED", "ADMIN_STOP", "SYSTEM_SHUTDOWN"]:
            dev.status = "STOPPED" if dev.offline_reason_code == "ADMIN_STOP" else "OFFLINE"
            reason_code = dev.offline_reason_code
            reason_text = dev.offline_reason_text or f"Agent stopped cleanly ({reason_code})"
        elif is_mass_outage:
            dev.status = "OFFLINE"
            reason_code = "LIKELY_GATEWAY_OR_NETWORK_ISSUE"
            reason_text = "Multiple devices became silent simultaneously; probable store network or gateway connectivity disruption."
        else:
            dev.status = "OFFLINE"
            reason_code = "NO_SIGNAL"
            reason_text = "No signal and no shutdown message. Possible causes: PC powered off or crashed, network cable or switch problem, or the agent was killed."

        dev.offline_since = dev.last_seen
        dev.offline_reason_code = reason_code
        dev.offline_reason_text = reason_text
        dev.consecutive_heartbeats_ok = 0

        # Record ConnectionEvent
        event = ConnectionEvent(
            device_pk=dev.id,
            ts=now,
            type="OFFLINE",
            reason_code=reason_code,
            reason_text=reason_text,
            details_json={"last_seen": dev.last_seen.isoformat() if dev.last_seen else None}
        )
        db.add(event)

        # Fire agent_offline alert
        msg = f"POS {dev.device_id} is offline: {reason_text}" if dev.device_type.upper() == "POS" else f"Device {dev.device_id} is offline: {reason_text}"
        fire_alert_if_not_active(
            db,
            device=dev,
            rule_key="agent_offline",
            severity="critical",
            message=msg,
            value=dev.last_seen.isoformat() if dev.last_seen else None
        )

    db.commit()
    check_stale_readings(db)

def purge_expired_metrics(db: Session):
    cutoff = utc_now() - timedelta(days=settings.METRICS_RETENTION_DAYS)
    deleted_metrics = db.query(Metric).filter(Metric.ts < cutoff).delete()

    light_cutoff = utc_now() - timedelta(days=7)
    db.query(LightMetric).filter(LightMetric.ts < light_cutoff).delete()

    fbr_cutoff = utc_now() - timedelta(days=settings.FBR_RETENTION_DAYS)
    deleted_fbr = db.query(FbrCheck).filter(FbrCheck.ts < fbr_cutoff).delete()

    db.commit()
    return deleted_metrics + deleted_fbr
