from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.database import get_db
from app.models import Device, Store, Alert, Metric, Note
from app.deps import get_hermes_auth
from app.audit import log_audit, get_client_ip

router = APIRouter(
    prefix="/api/v1/hermes",
    tags=["Hermes AI (Read-Only)"],
    dependencies=[Depends(get_hermes_auth)]
)

def utc_now():
    return datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# V1 ARCHITECTURAL CONSTRAINT:
# The /api/v1/hermes/* API is strictly READ-ONLY (HTTP GET only).
# TODO [V2/V3 Pilot Extension]: Remote diagnostic triggers or agent actuation
# will ONLY be considered in subsequent major versions with dual-custody authorization.
# NO write endpoints, command executions, or agent shell calls exist in V1.
# ---------------------------------------------------------------------------

@router.get("/summary")
def get_hermes_summary(request: Request, db: Session = Depends(get_db)):
    """
    Overview summary of hypermarket stores, devices, and alerts.
    Output is compact JSON optimized for LLM token efficiency.
    """
    ip = get_client_ip(request)
    now = utc_now()

    stores_count = db.query(Store).count()
    devices_total = db.query(Device).count()
    online_count = db.query(Device).filter(Device.status == "ONLINE").count()
    offline_count = db.query(Device).filter(Device.status == "OFFLINE").count()
    degraded_count = db.query(Device).filter(Device.status == "DEGRADED").count()
    firing_alerts = db.query(Alert).filter(Alert.state == "FIRING").count()
    critical_alerts = db.query(Alert).filter(Alert.state == "FIRING", Alert.severity == "critical").count()

    log_audit(
        db,
        actor_type="hermes",
        actor="hermes_ai",
        action="hermes_read_summary",
        target="gateway",
        ip=ip,
        detail_json={"devices": devices_total, "online": online_count, "firing": firing_alerts}
    )

    return {
        "stores": stores_count,
        "devices_total": devices_total,
        "online": online_count,
        "offline": offline_count,
        "degraded": degraded_count,
        "firing_alerts": firing_alerts,
        "critical_alerts": critical_alerts,
        "generated_at": now.isoformat()
    }

@router.get("/stores")
def get_hermes_stores(request: Request, db: Session = Depends(get_db)):
    """List all stores with device totals and health status."""
    ip = get_client_ip(request)
    stores = db.query(Store).all()
    results = []

    for s in stores:
        dev_count = len(s.devices)
        online = sum(1 for d in s.devices if d.status == "ONLINE")
        offline = sum(1 for d in s.devices if d.status == "OFFLINE")
        alerts_active = db.query(Alert).join(Device, Alert.device_pk == Device.id).filter(
            Device.store_id == s.id,
            Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
        ).count()

        results.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "region": s.region,
            "devices_total": dev_count,
            "online_count": online,
            "offline_count": offline,
            "active_alerts": alerts_active
        })

    log_audit(
        db,
        actor_type="hermes",
        actor="hermes_ai",
        action="hermes_read_stores",
        target="stores",
        ip=ip
    )
    return results

@router.get("/devices")
def get_hermes_devices(
    request: Request,
    store: Optional[str] = Query(None, description="Store code filter (e.g. ISL-01)"),
    status: Optional[str] = Query(None, description="ONLINE, OFFLINE, DEGRADED"),
    type: Optional[str] = Query(None, description="POS, PC, PRINTER, SERVER"),
    search: Optional[str] = Query(None, description="Search device_id or computer_name"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List devices with filtering. Strips all secrets/tokens/hashes."""
    ip = get_client_ip(request)
    query = db.query(Device).join(Store, Device.store_id == Store.id)

    if store:
        query = query.filter(Store.code == store.strip().upper())
    if status:
        query = query.filter(Device.status == status.strip().upper())
    if type:
        query = query.filter(Device.device_type == type.strip().upper())
    if search:
        s_term = f"%{search.strip()}%"
        query = query.filter(or_(Device.device_id.ilike(s_term), Device.computer_name.ilike(s_term)))

    devices = query.order_by(Device.device_id).limit(limit).all()

    results = []
    for d in devices:
        results.append({
            "device_id": d.device_id,
            "computer_name": d.computer_name,
            "store": d.store.code if d.store else "UNKNOWN",
            "type": d.device_type,
            "ip": d.ip_address,
            "status": d.status,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "agent_version": d.agent_version
        })

    log_audit(
        db,
        actor_type="hermes",
        actor="hermes_ai",
        action="hermes_read_devices",
        target="devices",
        ip=ip,
        detail_json={"returned_count": len(results)}
    )
    return results

@router.get("/devices/{device_id}")
def get_hermes_device_detail(
    device_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Detailed telemetry for one device: metadata + latest metric snapshot + 
    active alerts + last 5 resolved alerts + notes.
    """
    ip = get_client_ip(request)
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

    # Latest metric snapshot
    latest_metric = db.query(Metric).filter(
        Metric.device_pk == dev.id
    ).order_by(desc(Metric.ts)).first()

    metric_summary = None
    if latest_metric:
        metric_summary = {
            "ts": latest_metric.ts.isoformat(),
            "cpu_pct": latest_metric.cpu_pct,
            "ram_pct": latest_metric.ram_pct,
            "ram_used_mb": latest_metric.ram_used_mb,
            "disks": latest_metric.disk_json,
            "network": latest_metric.net_json,
            "internet_ok": latest_metric.internet_ok,
            "printers": latest_metric.printers_json,
            "services": latest_metric.services_json
        }

    # Active alerts
    active_alerts = db.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
    ).order_by(desc(Alert.fired_at)).all()

    # Last 5 resolved alerts
    resolved_alerts = db.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.state == "RESOLVED"
    ).order_by(desc(Alert.resolved_at)).limit(5).all()

    # Notes
    device_notes = db.query(Note).filter(
        Note.device_pk == dev.id
    ).order_by(desc(Note.created_at)).limit(10).all()

    log_audit(
        db,
        actor_type="hermes",
        actor="hermes_ai",
        action="hermes_read_device_detail",
        target=dev.device_id,
        ip=ip
    )

    return {
        "device_id": dev.device_id,
        "computer_name": dev.computer_name,
        "store": dev.store.code if dev.store else "UNKNOWN",
        "device_type": dev.device_type,
        "ip_address": dev.ip_address,
        "os_version": dev.os_version,
        "agent_version": dev.agent_version,
        "status": dev.status,
        "last_seen": dev.last_seen.isoformat() if dev.last_seen else None,
        "registered_at": dev.registered_at.isoformat() if dev.registered_at else None,
        "local_time": dev.local_time,
        "timezone_name": dev.timezone_name,
        "clock_offset_sec": dev.clock_offset_sec,
        "uptime_sec": dev.uptime_sec,
        "fbr_status": dev.fbr_status or "NOT_CONFIGURED",
        "fbr_ok": dev.fbr_ok,
        "fbr_latency_ms": dev.fbr_latency_ms,
        "latest_metrics": metric_summary,
        "active_alerts": [
            {
                "id": a.id,
                "rule_key": a.rule_key,
                "severity": a.severity,
                "state": a.state,
                "message": a.message,
                "fired_at": a.fired_at.isoformat()
            }
            for a in active_alerts
        ],
        "resolved_alerts": [
            {
                "id": a.id,
                "rule_key": a.rule_key,
                "severity": a.severity,
                "message": a.message,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None
            }
            for a in resolved_alerts
        ],
        "notes": [
            {
                "id": n.id,
                "text": n.text,
                "author": n.author.username if n.author else "System",
                "created_at": n.created_at.isoformat()
            }
            for n in device_notes
        ]
    }

@router.get("/devices/{device_id}/metrics")
def get_hermes_device_metrics(
    device_id: str,
    request: Request,
    minutes: int = Query(60, ge=5, le=1440),
    step: int = Query(5, ge=1, le=60),
    db: Session = Depends(get_db)
):
    """
    Downsampled telemetry series for CPU, RAM, Disk, and Internet.
    Capped at 100 points maximum for token savings.
    """
    ip = get_client_ip(request)
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

    cutoff = utc_now() - timedelta(minutes=minutes)
    raw_metrics = db.query(Metric).filter(
        Metric.device_pk == dev.id,
        Metric.ts >= cutoff
    ).order_by(Metric.ts.asc()).all()

    # Downsample by step minutes
    step_delta = timedelta(minutes=step)
    downsampled = []
    last_bucket_time = None

    for m in raw_metrics:
        # Normalize timezone if necessary
        metric_time = m.ts
        if metric_time.tzinfo is None:
            metric_time = metric_time.replace(tzinfo=timezone.utc)

        if last_bucket_time is None or (metric_time - last_bucket_time) >= step_delta:
            # Primary disk percentage if available
            primary_disk_pct = None
            if m.disk_json and isinstance(m.disk_json, list) and len(m.disk_json) > 0:
                primary_disk_pct = m.disk_json[0].get("pct")

            downsampled.append({
                "ts": metric_time.isoformat(),
                "cpu_pct": round(m.cpu_pct, 1),
                "ram_pct": round(m.ram_pct, 1),
                "disk_pct": primary_disk_pct,
                "internet_ok": m.internet_ok
            })
            last_bucket_time = metric_time

            if len(downsampled) >= 100:
                break

    log_audit(
        db,
        actor_type="hermes",
        actor="hermes_ai",
        action="hermes_read_metrics",
        target=dev.device_id,
        ip=ip,
        detail_json={"points": len(downsampled), "minutes": minutes, "step": step}
    )

    return {
        "device_id": dev.device_id,
        "window_minutes": minutes,
        "step_minutes": step,
        "points_count": len(downsampled),
        "series": downsampled
    }

@router.get("/alerts")
def get_hermes_alerts(
    request: Request,
    state: str = Query("FIRING", description="FIRING, ACKNOWLEDGED, RESOLVED"),
    severity: Optional[str] = Query(None, description="warning, critical"),
    device_id: Optional[str] = Query(None),
    store: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Query alerts for Hermes AI context."""
    ip = get_client_ip(request)
    query = db.query(Alert).join(Device, Alert.device_pk == Device.id)

    if state:
        query = query.filter(Alert.state == state.strip().upper())
    if severity:
        query = query.filter(Alert.severity == severity.strip().lower())
    if device_id:
        query = query.filter(Device.device_id == device_id.strip())
    if store:
        query = query.join(Store, Device.store_id == Store.id).filter(Store.code == store.strip().upper())

    alerts = query.order_by(desc(Alert.fired_at)).limit(limit).all()

    results = []
    for a in alerts:
        results.append({
            "id": a.id,
            "device_id": a.device.device_id if a.device else "UNKNOWN",
            "store": a.device.store.code if (a.device and a.device.store) else "UNKNOWN",
            "rule_key": a.rule_key,
            "severity": a.severity,
            "state": a.state,
            "message": a.message,
            "fired_at": a.fired_at.isoformat()
        })

    log_audit(
        db,
        actor_type="hermes",
        actor="hermes_ai",
        action="hermes_read_alerts",
        target="alerts",
        ip=ip,
        detail_json={"returned": len(results)}
    )
    return results

@router.get("/devices/{device_id}/summary_text")
def get_hermes_device_summary_text(
    device_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Generates a concise, plain-English paragraph describing device health,
    status, active alerts, and recent metrics for direct Hermes LLM reasoning.
    """
    ip = get_client_ip(request)
    dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{device_id}' not found")

    now = utc_now()
    store_code = dev.store.code if dev.store else "Unknown Store"

    # Last seen calculation
    minutes_ago = None
    if dev.last_seen:
        dev_last_seen = dev.last_seen if dev.last_seen.tzinfo else dev.last_seen.replace(tzinfo=timezone.utc)
        minutes_ago = max(0, int((now - dev_last_seen).total_seconds() / 60))

    # Active alerts
    active_alerts = db.query(Alert).filter(
        Alert.device_pk == dev.id,
        Alert.state.in_(["FIRING", "ACKNOWLEDGED"])
    ).all()

    # Latest metrics
    latest_metric = db.query(Metric).filter(
        Metric.device_pk == dev.id
    ).order_by(desc(Metric.ts)).first()

    # Build paragraph
    parts = []
    if dev.status == "ONLINE":
        parts.append(f"{dev.device_id} at {store_code} is ONLINE (last seen {minutes_ago or 0} min ago).")
    else:
        parts.append(
            f"{dev.device_id} at {store_code} is {dev.status} since {dev.last_seen.strftime('%H:%M') if dev.last_seen else 'N/A'} "
            f"(last seen {minutes_ago} min ago)."
        )

    # Local Time, Timezone and Clock Offset
    time_str = f"Local time: {dev.local_time or 'N/A'} ({dev.timezone_name or 'Unknown TZ'}, clock offset: {f'{dev.clock_offset_sec:+.1f}s' if dev.clock_offset_sec is not None else 'N/A'})."
    parts.append(time_str)

    # FBR Fiscal Connectivity Status
    fbr_status_str = f"FBR portal: {dev.fbr_status or 'NOT_CONFIGURED'}"
    if dev.fbr_latency_ms is not None:
        fbr_status_str += f" ({dev.fbr_latency_ms}ms)"
    if dev.fbr_error:
        fbr_status_str += f" [Error: {dev.fbr_error}]"
    parts.append(f"{fbr_status_str}.")

    if active_alerts:
        alert_msgs = [f"[{a.severity.upper()}] {a.message}" for a in active_alerts]
        parts.append(f"Active alerts ({len(active_alerts)}): " + "; ".join(alert_msgs) + ".")
    else:
        parts.append("There are currently no firing alerts.")

    if latest_metric:
        metric_str = f"Latest telemetry ({latest_metric.ts.strftime('%H:%M')}): CPU {latest_metric.cpu_pct:.1f}%, RAM {latest_metric.ram_pct:.1f}% ({int(latest_metric.ram_used_mb)} MB)."
        if latest_metric.disk_json and len(latest_metric.disk_json) > 0:
            d = latest_metric.disk_json[0]
            metric_str += f" Disk {d.get('mount', 'C:')} at {d.get('pct', 0)}%."
        if not latest_metric.internet_ok:
            metric_str += " Internet connectivity is DOWN."
        parts.append(metric_str)

    summary_paragraph = " ".join(parts)

    log_audit(
        db,
        actor_type="hermes",
        actor="hermes_ai",
        action="hermes_read_summary_text",
        target=dev.device_id,
        ip=ip
    )

    return {
        "device_id": dev.device_id,
        "store": store_code,
        "status": dev.status,
        "summary": summary_paragraph
    }
