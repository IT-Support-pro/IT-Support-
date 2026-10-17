from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_

from app.database import get_db
from app.models import (
    Alert, AlertRule, Device, Store, User, UserStore,
    AlertCheck, ConnectionEvent, Metric, AgentTask
)
from app.schemas import (
    AlertResponse, AlertRuleResponse, AlertRuleUpdate,
    AlertAckRequest, AlertResolveResponse, AlertDetailResponse, AlertCheckItem
)
from app.deps import get_current_user, require_role, get_user_store_ids, check_store_access
from app.audit import log_audit, get_client_ip
from app.alert_engine import RULE_PLAYBOOKS, get_expected_timezone

router = APIRouter(prefix="/api/v1", tags=["Alerts & Rules"])

def utc_now():
    return datetime.now(timezone.utc)

def enrich_alert_response(a: Alert, db: Session) -> AlertResponse:
    res = AlertResponse.model_validate(a)
    res.device_id = a.device.device_id if a.device else "UNKNOWN"
    res.store_code = a.device.store.code if (a.device and a.device.store) else "UNKNOWN"
    res.rule_name = RULE_PLAYBOOKS.get(a.rule_key, {}).get("rule_name", a.rule_key)
    if a.acked_by:
        u = db.query(User).filter(User.id == a.acked_by).first()
        res.acked_by_name = u.username if u else None
    return res

@router.get("/alerts", response_model=List[AlertResponse])
def list_alerts(
    state: Optional[str] = Query(None, description="active, firing, acknowledged, resolved, all"),
    severity: Optional[str] = Query(None, description="warning, critical"),
    store: Optional[str] = Query(None, description="Store code e.g. ISL-01"),
    device: Optional[str] = Query(None, description="Device ID e.g. POS-12"),
    search: Optional[str] = Query(None, description="Search keyword in message or rule"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Alert).join(Device, Alert.device_pk == Device.id)

    if user.role != "admin":
        assigned_stores = get_user_store_ids(user, db)
        query = query.filter(Device.store_id.in_(assigned_stores))

    if state:
        st = state.strip().lower()
        if st == "active":
            query = query.filter(Alert.state.in_(["FIRING", "ACKNOWLEDGED"]))
        elif st == "firing":
            query = query.filter(Alert.state == "FIRING")
        elif st == "acknowledged":
            query = query.filter(Alert.state == "ACKNOWLEDGED")
        elif st == "resolved":
            query = query.filter(Alert.state == "RESOLVED")
        # 'all' does not filter by state

    if severity:
        query = query.filter(Alert.severity == severity.lower())
    if device:
        query = query.filter(Device.device_id == device.strip())
    if store:
        target_store = db.query(Store).filter(Store.code == store.strip().upper()).first()
        if target_store:
            query = query.filter(Device.store_id == target_store.id)
        else:
            return []
    if search:
        s_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Alert.message.ilike(s_term),
                Alert.rule_key.ilike(s_term),
                Device.device_id.ilike(s_term)
            )
        )

    alerts = query.order_by(desc(Alert.fired_at)).offset(offset).limit(limit).all()
    return [enrich_alert_response(a, db) for a in alerts]

@router.get("/alerts/{alert_id}", response_model=AlertDetailResponse)
def get_alert_detail(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    dev = alert.device
    if user.role != "admin" and dev:
        check_store_access(user, dev.store_id, db)

    pb = RULE_PLAYBOOKS.get(alert.rule_key, {
        "rule_name": alert.rule_key,
        "explanation": alert.message,
        "steps": ["Investigate the affected system.", "Check services and network.", "Click Resolve to re-check."]
    })

    # Error details assembly
    err_details: Dict[str, Any] = {
        "device_id": dev.device_id if dev else "UNKNOWN",
        "computer_name": dev.computer_name if dev else "UNKNOWN",
        "ip_address": dev.ip_address if dev else "UNKNOWN",
        "observed_value": alert.value,
        "fired_at_utc": alert.fired_at.isoformat() if alert.fired_at else None,
    }

    # Add specific telemetry details
    if alert.rule_key == "clock_drift":
        err_details["clock_offset_sec"] = dev.clock_offset_sec
        err_details["agent_local_time"] = dev.local_time
        err_details["agent_timezone"] = dev.timezone_name
    elif alert.rule_key == "timezone_mismatch":
        err_details["actual_timezone"] = dev.timezone_name
        err_details["expected_timezone"] = get_expected_timezone(dev, db)
    elif alert.rule_key == "fbr_down":
        err_details["fbr_pos_id"] = dev.fbr_pos_id
        err_details["local_ims_status"] = dev.local_ims_status
        err_details["fbr_connectivity"] = dev.fbr_connectivity_status
        err_details["last_error"] = dev.fbr_error
    elif alert.rule_key == "agent_offline":
        err_details["offline_reason_code"] = dev.offline_reason_code
        err_details["offline_reason_text"] = dev.offline_reason_text
        err_details["last_seen_utc"] = dev.last_seen.isoformat() if dev.last_seen else None

    # Timeline events
    timeline = [
        {"ts": alert.fired_at.isoformat(), "event": "Alert fired", "actor": "System"}
    ]
    if alert.acked_at:
        u = db.query(User).filter(User.id == alert.acked_by).first() if alert.acked_by else None
        timeline.append({
            "ts": alert.acked_at.isoformat(),
            "event": "Acknowledged",
            "actor": u.username if u else "User"
        })

    checks = db.query(AlertCheck).filter(AlertCheck.alert_id == alert.id).order_by(AlertCheck.ts.asc()).all()
    for chk in checks:
        timeline.append({
            "ts": chk.ts.isoformat(),
            "event": f"Verification check: {chk.result}",
            "actor": chk.by,
            "message": chk.message
        })

    if alert.resolved_at:
        timeline.append({
            "ts": alert.resolved_at.isoformat(),
            "event": f"Resolved ({alert.resolution or 'VERIFIED_FIXED'})",
            "actor": alert.resolved_by or "System"
        })

    # Related ConnectionEvents
    related_events = []
    if dev:
        events = db.query(ConnectionEvent).filter(
            ConnectionEvent.device_pk == dev.id
        ).order_by(desc(ConnectionEvent.ts)).limit(5).all()
        for ev in events:
            related_events.append({
                "ts": ev.ts.isoformat(),
                "type": ev.type,
                "reason_code": ev.reason_code,
                "reason_text": ev.reason_text
            })

    rule_obj = db.query(AlertRule).filter(AlertRule.rule_key == alert.rule_key).first()
    thresh_str = str(rule_obj.threshold_value) if (rule_obj and rule_obj.threshold_value) else None

    return AlertDetailResponse(
        alert=enrich_alert_response(alert, db),
        explanation=pb["explanation"],
        error_details=err_details,
        current_value=alert.value,
        threshold=thresh_str,
        how_to_fix=pb["steps"],
        timeline=timeline,
        checks=[AlertCheckItem.model_validate(c) for c in checks],
        related_events=related_events
    )

@router.post("/alerts/{alert_id}/ack", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    payload: Optional[AlertAckRequest] = None,
    request: Request = None,
    user: User = Depends(require_role(["admin", "technician"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request) if request else "127.0.0.1"
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    if user.role != "admin" and alert.device:
        check_store_access(user, alert.device.store_id, db)

    now = utc_now()
    alert.state = "ACKNOWLEDGED"
    alert.acked_by = user.id
    alert.acked_at = now
    db.commit()
    db.refresh(alert)

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="alert_acknowledged",
        target=f"alert_{alert.id}",
        ip=ip,
        detail_json={
            "rule_key": alert.rule_key,
            "device_id": alert.device.device_id if alert.device else None,
            "note": payload.note if payload else None
        }
    )

    return enrich_alert_response(alert, db)

@router.post("/alerts/{alert_id}/resolve", response_model=AlertResolveResponse)
def resolve_alert(
    alert_id: int,
    request: Request,
    user: User = Depends(require_role(["admin", "technician"])),
    db: Session = Depends(get_db)
):
    """
    Verify and Resolve workflow:
    1. For agent_offline: checks if device sent a heartbeat in the last 120s.
    2. For metrics/service/printers/fbr/clock:
       If device is offline, returns CANNOT_VERIFY.
       Checks latest telemetry against rule condition.
       If cleared: marks RESOLVED, resolution = "VERIFIED_FIXED".
       If not cleared: remains FIRING / ACKNOWLEDGED, returns NOT_RESOLVED.
    3. Records attempt in AlertCheck table.
    """
    ip = get_client_ip(request)
    now = utc_now()
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    dev = alert.device
    if user.role != "admin" and dev:
        check_store_access(user, dev.store_id, db)

    # 1. Rule: agent_offline
    if alert.rule_key == "agent_offline":
        if not dev or not dev.last_seen:
            res_type = "CANNOT_VERIFY"
            msg = f"{dev.device_id if dev else 'Device'} has no recorded heartbeat."
        else:
            seconds_since = (now - dev.last_seen).total_seconds()
            if seconds_since <= 120.0 and dev.status == "ONLINE":
                res_type = "FIXED"
                msg = f"Fixed successfully. {dev.device_id} is online and sending heartbeats (last seen {int(seconds_since)}s ago)."
            else:
                res_type = "NOT_RESOLVED"
                msg = f"Not resolved. {dev.device_id} is still offline (last seen {int(seconds_since)}s ago)."

    else:
        # Rules requiring live data
        if not dev or dev.status in ["OFFLINE", "STOPPED"]:
            res_type = "CANNOT_VERIFY"
            msg = f"{dev.device_id if dev else 'Device'} is offline, so the fix can't be confirmed."
        else:
            latest_metric = db.query(Metric).filter(
                Metric.device_pk == dev.id
            ).order_by(desc(Metric.ts)).first()

            if alert.rule_key == "clock_drift":
                drift = dev.clock_offset_sec or 0.0
                if abs(drift) <= 120.0:
                    res_type = "FIXED"
                    msg = f"Fixed successfully. Clock drift is now {drift:+.1f}s (within 120s limit)."
                else:
                    res_type = "NOT_RESOLVED"
                    msg = f"Not resolved. Clock drift is still {drift:+.1f}s (limit 120s)."

            elif alert.rule_key == "timezone_mismatch":
                expected = get_expected_timezone(dev, db).strip().lower()
                actual = (dev.timezone_name or "").strip().lower()
                if expected in actual or actual in expected:
                    res_type = "FIXED"
                    msg = f"Fixed successfully. Timezone is now '{dev.timezone_name}'."
                else:
                    res_type = "NOT_RESOLVED"
                    msg = f"Not resolved. Timezone is still '{dev.timezone_name}' (expected '{get_expected_timezone(dev, db)}')."

            elif alert.rule_key == "fbr_down":
                if dev.fbr_ok is True or dev.fbr_connectivity_status == "CONNECTED":
                    res_type = "FIXED"
                    msg = "Fixed successfully. FBR connectivity verified (CONNECTED)."
                else:
                    res_type = "NOT_RESOLVED"
                    msg = f"Not resolved. FBR connectivity status is still '{dev.fbr_connectivity_status or 'DOWN'}'."

            elif alert.rule_key == "disk_low":
                if latest_metric:
                    disks = latest_metric.disk_json or []
                    high_disks = [d for d in disks if d.get("pct", 0) > 90.0]
                    if not high_disks:
                        primary_pct = disks[0].get("pct") if disks else "safe"
                        res_type = "FIXED"
                        msg = f"Fixed successfully. All drives below 90% (Drive C: is now {primary_pct}%)."
                    else:
                        d_info = ", ".join([f"{d.get('mount')} at {d.get('pct')}%" for d in high_disks])
                        res_type = "NOT_RESOLVED"
                        msg = f"Not resolved. {d_info} (limit 90%)."
                else:
                    res_type = "CANNOT_VERIFY"
                    msg = f"{dev.device_id} has not reported recent disk readings."

            elif alert.rule_key == "service_down":
                if latest_metric:
                    services = latest_metric.services_json or []
                    stopped = [s.get("name") for s in services if s.get("state", "").lower() != "running"]
                    if not stopped:
                        res_type = "FIXED"
                        msg = "Fixed successfully. All monitored services are Running."
                    else:
                        res_type = "NOT_RESOLVED"
                        msg = f"Not resolved. Services still stopped: {', '.join(stopped)}."
                else:
                    res_type = "CANNOT_VERIFY"
                    msg = f"No telemetry readings available for {dev.device_id}."

            elif alert.rule_key == "printer_offline":
                if latest_metric:
                    printers = latest_metric.printers_json or []
                    off = [p.get("name") for p in printers if p.get("is_offline") or p.get("status", "").lower() in ["offline", "error"]]
                    if not off:
                        res_type = "FIXED"
                        msg = "Fixed successfully. Printers are online."
                    else:
                        res_type = "NOT_RESOLVED"
                        msg = f"Not resolved. Printer still offline: {', '.join(off)}."
                else:
                    res_type = "CANNOT_VERIFY"
                    msg = f"No telemetry readings available for {dev.device_id}."

            elif alert.rule_key == "internet_down":
                if latest_metric and latest_metric.internet_ok:
                    res_type = "FIXED"
                    msg = "Fixed successfully. Internet connectivity restored."
                else:
                    res_type = "NOT_RESOLVED"
                    msg = "Not resolved. Internet connectivity check still failing."

            elif alert.rule_key in ["cpu_high", "ram_high"]:
                metric_name = "CPU" if alert.rule_key == "cpu_high" else "RAM"
                val = (latest_metric.cpu_pct if alert.rule_key == "cpu_high" else latest_metric.ram_pct) if latest_metric else None
                limit = 90.0 if alert.rule_key == "cpu_high" else 85.0
                if val is not None and val < limit:
                    res_type = "FIXED"
                    msg = f"Fixed successfully. {metric_name} is now {val}% (limit {limit}%)."
                else:
                    res_type = "NOT_RESOLVED"
                    msg = f"Not resolved. {metric_name} is currently {val or 'unknown'}% (limit {limit}%)."

            elif alert.rule_key == "agent_stale":
                if not dev.reading_stale:
                    res_type = "FIXED"
                    msg = "Fixed successfully. Fresh telemetry readings received."
                else:
                    res_type = "NOT_RESOLVED"
                    msg = "Not resolved. Full telemetry readings have not resumed."

            else:
                res_type = "FIXED"
                msg = f"Verification check completed for {alert.rule_key}."

    # Record AlertCheck
    chk = AlertCheck(
        alert_id=alert.id,
        ts=now,
        by=user.username,
        result=res_type,
        observed_value=alert.value,
        message=msg
    )
    db.add(chk)

    # If FIXED, update alert state to RESOLVED
    if res_type == "FIXED":
        alert.state = "RESOLVED"
        alert.resolved_at = now
        alert.resolved_by = user.username
        alert.resolution = "VERIFIED_FIXED"

    db.commit()
    db.refresh(alert)

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="alert_resolve_attempt",
        target=f"alert_{alert.id}",
        ip=ip,
        detail_json={"result": res_type, "message": msg}
    )

    return AlertResolveResponse(
        result=res_type,
        message=msg,
        current_value=alert.value,
        checked_at=now,
        alert=enrich_alert_response(alert, db)
    )

@router.get("/alert-rules", response_model=List[AlertRuleResponse])
def list_alert_rules(
    user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    return db.query(AlertRule).all()

@router.put("/alert-rules/{rule_key}", response_model=AlertRuleResponse)
def update_alert_rule(
    rule_key: str,
    payload: AlertRuleUpdate,
    request: Request,
    user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    rule = db.query(AlertRule).filter(AlertRule.rule_key == rule_key).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert rule '{rule_key}' not found")

    if payload.name is not None:
        rule.name = payload.name
    if payload.severity is not None:
        rule.severity = payload.severity
    if payload.threshold_value is not None:
        rule.threshold_value = payload.threshold_value
    if payload.duration_seconds is not None:
        rule.duration_seconds = payload.duration_seconds
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.description is not None:
        rule.description = payload.description

    db.commit()
    db.refresh(rule)

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="update_alert_rule",
        target=rule_key,
        ip=ip,
        detail_json={"severity": rule.severity, "threshold": rule.threshold_value, "enabled": rule.enabled}
    )

    return rule
