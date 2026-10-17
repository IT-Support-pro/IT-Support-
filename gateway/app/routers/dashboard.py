from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_, func

from app.database import get_db
from app.models import (
    Device, Store, Alert, Metric, LightMetric, Note, User,
    UserStore, FbrCheck, AgentTask, ConnectionEvent, GatewayState,
    AuditLog
)
from app.schemas import (
    NoteCreate, AgentTaskCreate, AgentTaskResponse,
    DeviceSettingsUpdate, SeriesResponse, SeriesDataPoint,
    ConnectionEventResponse, GatewayStatusResponse
)
from app.deps import get_current_user, require_role, get_user_store_ids, check_store_access
from app.audit import log_audit, get_client_ip
from app.config import settings
from app.alert_engine import get_expected_timezone

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])

def utc_now():
    return datetime.now(timezone.utc)

def calculate_device_uptime(device_pk: str, db: Session) -> Dict[str, float]:
    """Calculates availability % over 24 hours and 7 days based on ConnectionEvents."""
    now = utc_now()
    results = {"uptime_24h": 100.0, "uptime_7d": 100.0}

    for period_key, hours in [("uptime_24h", 24), ("uptime_7d", 168)]:
        cutoff = now - timedelta(hours=hours)
        total_period_sec = hours * 3600.0
        
        # Sum offline duration within period
        events = db.query(ConnectionEvent).filter(
            ConnectionEvent.device_pk == device_pk,
            ConnectionEvent.type.in_(["OFFLINE", "STOPPED", "RECONNECTED"]),
            ConnectionEvent.ts >= cutoff
        ).order_by(ConnectionEvent.ts.asc()).all()

        offline_sec = 0.0
        last_down_ts = None

        for ev in events:
            if ev.type in ["OFFLINE", "STOPPED"]:
                last_down_ts = ev.ts
            elif ev.type == "RECONNECTED" and last_down_ts:
                offline_sec += (ev.ts - last_down_ts).total_seconds()
                last_down_ts = None

        # If currently down
        dev = db.query(Device).filter(Device.id == device_pk).first()
        if dev and dev.status in ["OFFLINE", "STOPPED"] and dev.offline_since:
            effective_start = max(dev.offline_since, cutoff)
            offline_sec += (now - effective_start).total_seconds()

        up_pct = max(0.0, min(100.0, ((total_period_sec - offline_sec) / total_period_sec) * 100.0))
        results[period_key] = round(up_pct, 1)

    return results

# ----------------- 1. OVERVIEW & HEALTH -----------------

@router.get("/overview")
def get_dashboard_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device_query = db.query(Device)
    store_query = db.query(Store)
    alert_query = db.query(Alert).join(Device, Alert.device_pk == Device.id)

    if user.role != "admin":
        accessible_store_ids = get_user_store_ids(user, db)
        device_query = device_query.filter(Device.store_id.in_(accessible_store_ids))
        store_query = store_query.filter(Store.id.in_(accessible_store_ids))
        alert_query = alert_query.filter(Device.store_id.in_(accessible_store_ids))

    all_devices = device_query.all()
    devices_total = len(all_devices)
    online_count = sum(1 for d in all_devices if d.status == "ONLINE")
    offline_count = sum(1 for d in all_devices if d.status == "OFFLINE")
    paused_or_stopped = sum(1 for d in all_devices if d.status in ["PAUSED", "STOPPED"] or d.agent_state == "PAUSED")
    fbr_down_count = sum(1 for d in all_devices if d.fbr_connectivity_status in ["DISCONNECTED", "LOCAL_SERVICE_DOWN"] or d.fbr_status == "DOWN")

    active_alerts = alert_query.filter(Alert.state.in_(["FIRING", "ACKNOWLEDGED"])).count()
    critical_alerts = alert_query.filter(Alert.state == "FIRING", Alert.severity == "critical").count()
    warning_alerts = alert_query.filter(Alert.state == "FIRING", Alert.severity == "warning").count()

    # Needs Attention list: offline devices with reason + critical alerts
    needs_attention = []
    for d in all_devices:
        if d.status in ["OFFLINE", "STOPPED"]:
            needs_attention.append({
                "type": "device_offline",
                "device_id": d.device_id,
                "computer_name": d.computer_name,
                "store_code": d.store.code if d.store else "UNKNOWN",
                "status": d.status,
                "reason": d.offline_reason_text or f"Device {d.status.lower()}",
                "since_utc": d.offline_since.isoformat() if d.offline_since else None,
            })

    crit_alert_rows = alert_query.filter(Alert.state == "FIRING", Alert.severity == "critical").limit(10).all()
    for a in crit_alert_rows:
        needs_attention.append({
            "type": "critical_alert",
            "alert_id": a.id,
            "device_id": a.device.device_id if a.device else "UNKNOWN",
            "store_code": a.device.store.code if (a.device and a.device.store) else "UNKNOWN",
            "rule_key": a.rule_key,
            "message": a.message,
            "fired_at_utc": a.fired_at.isoformat() if a.fired_at else None
        })

    # Recent activity timeline (connection events and task actions)
    recent_events_query = db.query(ConnectionEvent).join(Device, ConnectionEvent.device_pk == Device.id)
    if user.role != "admin":
        recent_events_query = recent_events_query.filter(Device.store_id.in_(get_user_store_ids(user, db)))
    
    recent_events = recent_events_query.order_by(desc(ConnectionEvent.ts)).limit(10).all()
    activity_timeline = []
    for ev in recent_events:
        activity_timeline.append({
            "id": ev.id,
            "ts": ev.ts.isoformat(),
            "type": ev.type,
            "device_id": ev.device.device_id if ev.device else "UNKNOWN",
            "store_code": ev.device.store.code if (ev.device and ev.device.store) else "UNKNOWN",
            "reason_code": ev.reason_code,
            "reason_text": ev.reason_text,
            "duration_sec": ev.duration_sec
        })

    # Store health table
    stores = store_query.order_by(Store.code).all()
    store_health = []
    for s in stores:
        devs = s.devices
        s_total = len(devs)
        s_online = sum(1 for d in devs if d.status == "ONLINE")
        s_offline = sum(1 for d in devs if d.status == "OFFLINE")
        s_fbr_down = sum(1 for d in devs if d.fbr_connectivity_status in ["DISCONNECTED", "LOCAL_SERVICE_DOWN"] or d.fbr_status == "DOWN")
        s_alerts = db.query(Alert).join(Device, Alert.device_pk == Device.id).filter(
            Device.store_id == s.id, Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
        ).count()
        store_health.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "region": s.region,
            "devices_total": s_total,
            "online": s_online,
            "offline": s_offline,
            "fbr_down": s_fbr_down,
            "active_alerts": s_alerts
        })

    # Gateway health card
    gw_state = db.query(GatewayState).first()
    gw_up_since = gw_state.started_at_utc.isoformat() if gw_state else utc_now().isoformat()
    gw_uptime_sec = (utc_now() - gw_state.started_at_utc).total_seconds() if gw_state else 0.0

    return {
        "devices_total": devices_total,
        "online": online_count,
        "offline": offline_count,
        "paused_or_stopped": paused_or_stopped,
        "fbr_down": fbr_down_count,
        "firing_alerts": active_alerts,
        "critical_alerts": critical_alerts,
        "warning_alerts": warning_alerts,
        "stores_count": len(stores),
        "needs_attention": needs_attention,
        "recent_activity": activity_timeline,
        "store_health": store_health,
        "gateway_health": {
            "started_at_utc": gw_up_since,
            "uptime_sec": int(gw_uptime_sec),
            "version": gw_state.version if gw_state else "1.1.0",
            "status": "HEALTHY"
        },
        "generated_at": utc_now().isoformat()
    }

@router.get("/gateway/status", response_model=GatewayStatusResponse)
def get_gateway_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    gw_state = db.query(GatewayState).first()
    now = utc_now()
    started_at = gw_state.started_at_utc if gw_state else now
    uptime_sec = (now - started_at).total_seconds()
    version = gw_state.version if gw_state else "1.1.0"

    last_down = db.query(ConnectionEvent).filter(
        ConnectionEvent.type == "GATEWAY_DOWN"
    ).order_by(desc(ConnectionEvent.ts)).first()

    counts = {
        "total": db.query(Device).count(),
        "online": db.query(Device).filter(Device.status == "ONLINE").count(),
        "offline": db.query(Device).filter(Device.status == "OFFLINE").count(),
        "paused": db.query(Device).filter(Device.agent_state == "PAUSED").count(),
        "stopped": db.query(Device).filter(Device.status == "STOPPED").count(),
    }

    pub_url = getattr(settings, "PUBLIC_GATEWAY_URL", None)

    return GatewayStatusResponse(
        started_at_utc=started_at,
        uptime_sec=uptime_sec,
        version=version,
        last_downtime_event={
            "ts": last_down.ts.isoformat(),
            "duration_sec": last_down.duration_sec,
            "reason": last_down.reason_text
        } if last_down else None,
        device_counts=counts,
        public_gateway_url=pub_url
    )

# ----------------- 2. STORES -----------------

@router.get("/stores")
def get_stores_for_user(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Store)
    if user.role != "admin":
        assigned_ids = get_user_store_ids(user, db)
        query = query.filter(Store.id.in_(assigned_ids))

    stores = query.order_by(Store.code).all()
    results = []

    for s in stores:
        devs = s.devices
        dev_total = len(devs)
        online = sum(1 for d in devs if d.status == "ONLINE")
        offline = sum(1 for d in devs if d.status == "OFFLINE")
        alerts_firing = db.query(Alert).join(Device, Alert.device_pk == Device.id).filter(
            Device.store_id == s.id,
            Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
        ).count()

        results.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "region": s.region,
            "expected_timezone": s.expected_timezone or "Pakistan Standard Time",
            "created_at": s.created_at.isoformat(),
            "devices_total": dev_total,
            "online_count": online,
            "offline_count": offline,
            "firing_alerts": alerts_firing
        })

    return results

# ----------------- 3. DEVICES -----------------

@router.get("/devices")
def get_devices(
    store: Optional[str] = Query(None, description="Store code filter"),
    status_filter: Optional[str] = Query(None, alias="status", description="ONLINE, OFFLINE, PAUSED, STOPPED"),
    type_filter: Optional[str] = Query(None, alias="type", description="POS, PC, PRINTER, SERVER"),
    search: Optional[str] = Query(None, description="Search device_id or computer_name"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Device).join(Store, Device.store_id == Store.id)

    if user.role != "admin":
        assigned_stores = get_user_store_ids(user, db)
        query = query.filter(Device.store_id.in_(assigned_stores))

    if store:
        query = query.filter(Store.code == store.strip().upper())
    if status_filter:
        st = status_filter.strip().upper()
        if st == "PAUSED":
            query = query.filter(or_(Device.status == "PAUSED", Device.agent_state == "PAUSED"))
        else:
            query = query.filter(Device.status == st)
    if type_filter:
        query = query.filter(Device.device_type == type_filter.strip().upper())
    if search:
        s_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Device.device_id.ilike(s_term),
                Device.computer_name.ilike(s_term),
                Device.ip_address.ilike(s_term)
            )
        )

    devices = query.order_by(Store.code, Device.device_id).all()
    results = []

    for d in devices:
        active_alerts_count = db.query(Alert).filter(
            Alert.device_pk == d.id,
            Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
        ).count()

        latest_note = db.query(Note).filter(Note.device_pk == d.id).order_by(desc(Note.created_at)).first()

        results.append({
            "id": d.id,
            "device_id": d.device_id,
            "computer_name": d.computer_name,
            "store_id": d.store_id,
            "store_code": d.store.code if d.store else "UNKNOWN",
            "store_name": d.store.name if d.store else "UNKNOWN",
            "device_type": d.device_type,
            "ip_address": d.ip_address,
            "os_version": d.os_version,
            "agent_version": d.agent_version,
            "status": d.status,
            "connection_status": d.connection_status or d.status,
            "agent_state": d.agent_state or "RUNNING",
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "registered_at": d.registered_at.isoformat() if d.registered_at else None,
            "active_alerts_count": active_alerts_count,
            "notes_snippet": latest_note.text[:80] if latest_note else None,
            "offline_reason_code": d.offline_reason_code,
            "offline_reason_text": d.offline_reason_text,
            "offline_since": d.offline_since.isoformat() if d.offline_since else None,
            "reading_stale": d.reading_stale,
            
            # POS Date, Time & Uptime
            "local_time": d.local_time,
            "utc_time": d.utc_time.isoformat() if d.utc_time else None,
            "timezone_name": d.timezone_name,
            "utc_offset_minutes": d.utc_offset_minutes,
            "uptime_sec": d.uptime_sec,
            "clock_offset_sec": d.clock_offset_sec,

            # FBR Fields
            "fbr_status": d.fbr_status or "NOT_CONFIGURED",
            "fbr_ok": d.fbr_ok,
            "fbr_pos_id": d.fbr_pos_id,
            "fbr_pos_identification": d.fbr_pos_identification,
            "local_ims_status": d.local_ims_status or "UNKNOWN",
            "fbr_connectivity_status": d.fbr_connectivity_status or "UNKNOWN",
            "last_fiscal_sync": d.last_fiscal_sync.isoformat() if d.last_fiscal_sync else None
        })

    return results

@router.get("/devices/{device_id}")
def get_device_detail(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

    if user.role != "admin":
        check_store_access(user, dev.store_id, db)

    latest_metric = db.query(Metric).filter(
        Metric.device_pk == dev.id
    ).order_by(desc(Metric.ts)).first()

    active_alerts = db.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
    ).order_by(desc(Alert.fired_at)).all()

    notes = db.query(Note).filter(
        Note.device_pk == dev.id
    ).order_by(desc(Note.created_at)).all()

    recent_fbr_checks = db.query(FbrCheck).filter(
        FbrCheck.device_pk == dev.id
    ).order_by(desc(FbrCheck.ts)).limit(20).all()

    recent_tasks = db.query(AgentTask).filter(
        AgentTask.device_pk == dev.id
    ).order_by(desc(AgentTask.requested_at)).limit(10).all()

    uptime_stats = calculate_device_uptime(dev.id, db)

    return {
        "id": dev.id,
        "device_id": dev.device_id,
        "computer_name": dev.computer_name,
        "store_id": dev.store_id,
        "store_code": dev.store.code if dev.store else "UNKNOWN",
        "store_name": dev.store.name if dev.store else "UNKNOWN",
        "device_type": dev.device_type,
        "ip_address": dev.ip_address,
        "os_version": dev.os_version,
        "agent_version": dev.agent_version,
        "status": dev.status,
        "connection_status": dev.connection_status or dev.status,
        "agent_state": dev.agent_state or "RUNNING",
        "last_seen": dev.last_seen.isoformat() if dev.last_seen else None,
        "registered_at": dev.registered_at.isoformat() if dev.registered_at else None,
        "offline_reason_code": dev.offline_reason_code,
        "offline_reason_text": dev.offline_reason_text,
        "offline_since": dev.offline_since.isoformat() if dev.offline_since else None,
        "reading_stale": dev.reading_stale,
        "w32time_running": dev.w32time_running,
        "capabilities": dev.capabilities_json or ["pause", "resume", "collect_now", "fbr_check_now", "restart_agent", "stop_agent", "recheck"],
        "uptime_24h": uptime_stats["uptime_24h"],
        "uptime_7d": uptime_stats["uptime_7d"],

        # Clock details
        "local_time": dev.local_time,
        "utc_time": dev.utc_time.isoformat() if dev.utc_time else None,
        "timezone_name": dev.timezone_name,
        "expected_timezone": get_expected_timezone(dev, db),
        "utc_offset_minutes": dev.utc_offset_minutes,
        "uptime_sec": dev.uptime_sec,
        "clock_offset_sec": dev.clock_offset_sec,
        "clock_raw": dev.clock_raw_json,
        "muted_rules": dev.muted_rules_json or [],

        # FBR telemetry
        "fbr": {
            "status": dev.fbr_status or "NOT_CONFIGURED",
            "ok": dev.fbr_ok,
            "pos_id": dev.fbr_pos_id,
            "pos_identification": dev.fbr_pos_identification,
            "local_ims_status": dev.local_ims_status or "UNKNOWN",
            "fbr_connectivity_status": dev.fbr_connectivity_status or "UNKNOWN",
            "latency_ms": dev.fbr_latency_ms,
            "http_status": dev.fbr_http_status,
            "last_check": dev.fbr_last_check.isoformat() if dev.fbr_last_check else None,
            "last_ok_time": dev.fbr_last_ok_time.isoformat() if dev.fbr_last_ok_time else None,
            "last_fiscal_sync": dev.last_fiscal_sync.isoformat() if dev.last_fiscal_sync else None,
            "consecutive_failures": dev.fbr_consecutive_failures,
            "error": dev.fbr_error
        },
        "fbr_history": [
            {
                "id": c.id,
                "ts": c.ts.isoformat(),
                "ok": c.ok,
                "latency_ms": c.latency_ms,
                "http_status": c.http_status,
                "error": c.error
            } for c in recent_fbr_checks
        ],

        "network_details": dev.network_details_json,

        "latest_metrics": {
            "ts": latest_metric.ts.isoformat(),
            "cpu_pct": latest_metric.cpu_pct,
            "ram_pct": latest_metric.ram_pct,
            "ram_used_mb": latest_metric.ram_used_mb,
            "disks": latest_metric.disk_json,
            "network": latest_metric.net_json,
            "internet_ok": latest_metric.internet_ok,
            "printers": latest_metric.printers_json or [],
            "services": latest_metric.services_json or []
        } if latest_metric else None,

        "active_alerts": [
            {
                "id": a.id,
                "rule_key": a.rule_key,
                "severity": a.severity,
                "state": a.state,
                "message": a.message,
                "value": a.value,
                "fired_at": a.fired_at.isoformat()
            } for a in active_alerts
        ],

        "recent_tasks": [
            {
                "id": t.id,
                "action": t.action,
                "status": t.status,
                "requested_by": t.requested_by,
                "requested_at": t.requested_at.isoformat(),
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
                "result_text": t.result_text
            } for t in recent_tasks
        ],

        "notes": [
            {
                "id": n.id,
                "author": n.author.username if n.author else "Unknown",
                "text": n.text,
                "created_at": n.created_at.isoformat()
            } for n in notes
        ]
    }

# ----------------- 4. SERIES FOR CHARTS -----------------

@router.get("/devices/{device_id}/series", response_model=SeriesResponse)
def get_device_series(
    device_id: str,
    metric: str = Query("cpu", pattern="^(cpu|ram|disk)$"),
    range: str = Query("1h", pattern="^(1h|6h|24h|7d)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if user.role != "admin":
        check_store_access(user, dev.store_id, db)

    now = utc_now()
    range_map = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }
    cutoff = now - range_map[range]

    # Query light_metrics table
    light_rows = db.query(LightMetric).filter(
        LightMetric.device_pk == dev.id,
        LightMetric.ts >= cutoff
    ).order_by(LightMetric.ts.asc()).all()

    points: List[SeriesDataPoint] = []
    
    # We leave null gaps where the device was offline (no artificial interpolation)
    prev_ts = None
    for row in light_rows:
        # If gap between readings exceeds 3 minutes, insert a null marker point
        if prev_ts and (row.ts - prev_ts).total_seconds() > 180.0:
            points.append(SeriesDataPoint(
                ts=(prev_ts + timedelta(seconds=60)).isoformat(),
                value=None
            ))

        val = None
        if metric == "cpu":
            val = row.cpu_pct
        elif metric == "ram":
            val = row.ram_pct
        elif metric == "disk":
            val = row.system_disk_pct

        points.append(SeriesDataPoint(
            ts=row.ts.isoformat(),
            value=val
        ))
        prev_ts = row.ts

    return SeriesResponse(
        device_id=dev.device_id,
        metric=metric,
        range=range,
        points=points
    )

# ----------------- 5. CONNECTION EVENTS -----------------

@router.get("/devices/{device_id}/events", response_model=List[ConnectionEventResponse])
def get_device_events(
    device_id: str,
    type_filter: Optional[str] = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if user.role != "admin":
        check_store_access(user, dev.store_id, db)

    q = db.query(ConnectionEvent).filter(ConnectionEvent.device_pk == dev.id)
    if type_filter:
        q = q.filter(ConnectionEvent.type == type_filter.strip().upper())

    events = q.order_by(desc(ConnectionEvent.ts)).limit(limit).all()
    results = []
    for ev in events:
        res = ConnectionEventResponse.model_validate(ev)
        res.device_id = dev.device_id
        res.store_code = dev.store.code if dev.store else None
        results.append(res)
    return results

@router.get("/events", response_model=List[ConnectionEventResponse])
def get_all_events(
    device: Optional[str] = Query(None),
    store: Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(ConnectionEvent).join(Device, ConnectionEvent.device_pk == Device.id)

    if user.role != "admin":
        accessible = get_user_store_ids(user, db)
        q = q.filter(Device.store_id.in_(accessible))

    if device:
        q = q.filter(Device.device_id == device.strip())
    if store:
        q = q.join(Store, Device.store_id == Store.id).filter(Store.code == store.strip().upper())
    if type_filter:
        q = q.filter(ConnectionEvent.type == type_filter.strip().upper())

    events = q.order_by(desc(ConnectionEvent.ts)).limit(limit).all()
    results = []
    for ev in events:
        res = ConnectionEventResponse.model_validate(ev)
        res.device_id = ev.device.device_id if ev.device else "UNKNOWN"
        res.store_code = ev.device.store.code if (ev.device and ev.device.store) else "UNKNOWN"
        results.append(res)
    return results

# ----------------- 6. DEVICE SETTINGS -----------------

@router.put("/devices/{device_id}/settings")
def update_device_settings(
    device_id: str,
    payload: DeviceSettingsUpdate,
    request: Request,
    user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if payload.expected_timezone is not None:
        dev.expected_timezone = payload.expected_timezone.strip()
    if payload.muted_rules is not None:
        dev.muted_rules_json = payload.muted_rules

    db.commit()
    db.refresh(dev)

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="update_device_settings",
        target=dev.device_id,
        ip=get_client_ip(request),
        detail_json={"expected_timezone": dev.expected_timezone, "muted_rules": dev.muted_rules_json}
    )

    return {
        "status": "ok",
        "device_id": dev.device_id,
        "expected_timezone": dev.expected_timezone,
        "muted_rules": dev.muted_rules_json
    }

# ----------------- 7. REMOTE ACTIONS (WHITELIST ONLY) -----------------

@router.post("/devices/{device_id}/tasks", response_model=AgentTaskResponse)
def create_agent_task(
    device_id: str,
    payload: AgentTaskCreate,
    request: Request,
    user: User = Depends(require_role(["admin", "technician"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if user.role != "admin":
        check_store_access(user, dev.store_id, db)

    now = utc_now()

    # Rule: Creating task for OFFLINE or STOPPED device returns 409
    if dev.status in ["OFFLINE", "STOPPED"]:
        offline_time = dev.offline_since.isoformat() if dev.offline_since else "recently"
        offline_reason = dev.offline_reason_text or dev.status.lower()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device has been offline since {offline_time} ({offline_reason}). The request can't be delivered."
        )

    # Rule: PAUSED devices accept only resume, collect_now, and stop_agent
    if dev.agent_state == "PAUSED" and payload.action not in ["resume", "collect_now", "stop_agent"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device is PAUSED. It only accepts 'resume', 'collect_now', and 'stop_agent'."
        )

    # Rule: stop_agent requires confirm_device_id equal to device_id
    if payload.action == "stop_agent":
        if payload.confirm_device_id != dev.device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stopping the agent requires typing the exact device ID '{dev.device_id}' to confirm."
            )

    # Rule: Expire stale tasks older than 3 minutes
    stale_cutoff = now - timedelta(minutes=3)
    db.query(AgentTask).filter(
        AgentTask.device_pk == dev.id,
        AgentTask.status == "PENDING",
        AgentTask.requested_at < stale_cutoff
    ).update({
        AgentTask.status: "EXPIRED",
        AgentTask.result_text: "The agent did not pick this up. The device may be offline or running an old agent version."
    }, synchronize_session=False)
    db.commit()

    # Rule: Deduplication - if same action is already PENDING, SENT, or RUNNING, return existing
    existing = db.query(AgentTask).filter(
        AgentTask.device_pk == dev.id,
        AgentTask.action == payload.action,
        AgentTask.status.in_(["PENDING", "SENT", "RUNNING"])
    ).first()
    if existing:
        return existing

    # Rule: Rate limit to 1 new task per device per 5 seconds
    recent_task = db.query(AgentTask).filter(
        AgentTask.device_pk == dev.id,
        AgentTask.requested_at >= (now - timedelta(seconds=5))
    ).first()
    if recent_task:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limited: Please wait 5 seconds before dispatching another command to this device."
        )

    task = AgentTask(
        device_pk=dev.id,
        action=payload.action,
        status="PENDING",
        requested_by=user.username,
        requested_at=now
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action=f"task_{payload.action}",
        target=f"device_{dev.device_id}",
        ip=ip,
        detail_json={"task_id": task.id, "action": task.action}
    )

    return task

# ----------------- 8. NOTES -----------------

@router.post("/devices/{device_id}/notes")
def create_device_note(
    device_id: str,
    payload: NoteCreate,
    user: User = Depends(require_role(["admin", "technician"])),
    db: Session = Depends(get_db)
):
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if user.role != "admin":
        check_store_access(user, dev.store_id, db)

    note = Note(
        device_pk=dev.id,
        alert_id=payload.alert_id,
        author_id=user.id,
        text=payload.text.strip(),
        created_at=utc_now()
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    return {
        "id": note.id,
        "author": user.username,
        "text": note.text,
        "created_at": note.created_at.isoformat()
    }
