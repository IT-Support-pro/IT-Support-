import re
from datetime import datetime, timezone, timedelta
from typing import List, Union, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import (
    Device, Store, EnrollmentKey, Metric, FbrCheck, AgentTask,
    ConnectionEvent, LightMetric
)
from app.schemas import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentHeartbeatRequest,
    AgentGoodbyeRequest,
    MetricSnapshot,
    AgentTaskResultRequest,
)
from app.security import hash_secret, generate_device_token
from app.audit import log_audit, get_client_ip
from app.deps import get_authenticated_device, verify_payload_size
from app.alert_engine import (
    evaluate_metrics_snapshot,
    resolve_alert_if_active,
    evaluate_device_time_alerts,
    evaluate_fbr_alerts,
)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])

DEFAULT_IGNORE_PRINTER_WORDS = [
    "onenote", "microsoft", "xps", "pdf", "fax", "anydesk", "rustdesk", "send to"
]

DEFAULT_IGNORE_PORTS = [
    "nul:", "portprompt:", "shrfax:", "file:", "ad_port", "rustdesk printer"
]

def filter_real_printers_gateway(raw_printers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = []
    seen = set()

    for p in raw_printers:
        name = str(p.get("name") or "").strip()
        port = str(p.get("port") or "").strip()
        name_lower = name.lower()
        port_lower = port.lower()

        if any(w in name_lower for w in DEFAULT_IGNORE_PRINTER_WORDS):
            continue

        if any(ign == port_lower for ign in DEFAULT_IGNORE_PORTS) or port_lower.startswith("microsoft.office"):
            continue

        base_name = re.sub(r'\s*\(\s*copy(?:\s+of)?\s+\d+\s*\)', '', name, flags=re.IGNORECASE).strip()
        dedup_key = f"{port_lower}|{base_name.lower()}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        filtered.append({
            "name": base_name or name,
            "port": port,
            "status": p.get("status", "Idle"),
            "queue": int(p.get("queue", 0)),
            "is_offline": bool(p.get("is_offline", False)),
            "copies_count": int(p.get("copies_count", 1))
        })

    return filtered

@router.post("/register", response_model=AgentRegisterResponse)
def register_device(
    payload: AgentRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    now = datetime.now(timezone.utc)
    
    provided_key_hash = hash_secret(payload.enrollment_key)
    enrollment = db.query(EnrollmentKey).filter(
        EnrollmentKey.key_hash == provided_key_hash,
        EnrollmentKey.revoked == False
    ).first()

    if not enrollment:
        log_audit(
            db,
            actor_type="agent",
            actor=payload.device_id,
            action="register_failed_invalid_key",
            target="enrollment",
            ip=ip,
            detail_json={"device_id": payload.device_id}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked enrollment key"
        )

    store = enrollment.store
    raw_token = generate_device_token()
    token_h = hash_secret(raw_token)

    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if device:
        device.store_id = store.id
        device.computer_name = payload.computer_name
        device.device_type = payload.device_type
        device.ip_address = payload.ip_address
        device.os_version = payload.os_version
        device.agent_version = payload.agent_version
        device.token_hash = token_h
        device.status = "ONLINE"
        device.connection_status = "ONLINE"
        device.last_seen = now
        action_name = "device_re_enrolled"
    else:
        device = Device(
            device_id=payload.device_id,
            computer_name=payload.computer_name,
            store_id=store.id,
            device_type=payload.device_type,
            ip_address=payload.ip_address,
            os_version=payload.os_version,
            agent_version=payload.agent_version,
            token_hash=token_h,
            status="ONLINE",
            connection_status="ONLINE",
            last_seen=now,
            registered_at=now
        )
        db.add(device)
        action_name = "device_registered"

    db.commit()
    db.refresh(device)

    # Log ConnectionEvent
    conn_event = ConnectionEvent(
        device_pk=device.id,
        ts=now,
        type="ONLINE",
        reason_code="AGENT_REGISTERED",
        reason_text=f"Agent enrolled on {payload.computer_name} ({payload.agent_version})"
    )
    db.add(conn_event)
    db.commit()

    log_audit(
        db,
        actor_type="agent",
        actor=device.device_id,
        action=action_name,
        target=device.id,
        ip=ip,
        detail_json={"store_code": store.code, "agent_version": payload.agent_version}
    )

    return AgentRegisterResponse(
        device_token=raw_token,
        device_id=device.device_id,
        store_code=store.code,
        registered_at=device.registered_at
    )

@router.post("/goodbye")
def agent_goodbye(
    payload: AgentGoodbyeRequest,
    request: Request,
    device: Device = Depends(get_authenticated_device),
    db: Session = Depends(get_db)
):
    """
    Called on graceful / controlled agent shutdown.
    reason_code: SERVICE_STOPPED | SYSTEM_SHUTDOWN | ADMIN_STOP | RESTART_REQUESTED | CONSOLE_EXIT | UPDATE
    """
    now = datetime.now(timezone.utc)
    device.offline_since = now
    device.offline_reason_code = payload.reason_code
    device.offline_reason_text = payload.detail or f"Controlled shutdown: {payload.reason_code}"
    
    if payload.reason_code in ["SERVICE_STOPPED", "ADMIN_STOP"]:
        device.status = "STOPPED"
        device.connection_status = "STOPPED"
    else:
        device.status = "OFFLINE"
        device.connection_status = "OFFLINE"

    event = ConnectionEvent(
        device_pk=device.id,
        ts=now,
        type="STOPPED" if device.status == "STOPPED" else "OFFLINE",
        reason_code=payload.reason_code,
        reason_text=payload.detail or f"Agent reported controlled exit: {payload.reason_code}",
        details_json={"detail": payload.detail}
    )
    db.add(event)
    db.commit()

    log_audit(
        db,
        actor_type="agent",
        actor=device.device_id,
        action="agent_goodbye",
        target=device.id,
        ip=get_client_ip(request),
        detail_json={"reason_code": payload.reason_code, "detail": payload.detail}
    )
    return {"status": "ok", "recorded": payload.reason_code}

@router.post("/heartbeat")
def agent_heartbeat(
    payload: AgentHeartbeatRequest,
    device: Device = Depends(get_authenticated_device),
    db: Session = Depends(get_db)
):
    now_utc = datetime.now(timezone.utc)
    prev_status = device.status
    prev_offline_since = device.offline_since

    # Update basic network & version info
    if payload.ip_address and not payload.ip_address.startswith("127.") and not payload.ip_address.startswith("169.254."):
        device.ip_address = payload.ip_address

    device.agent_version = payload.agent_version
    device.last_seen = now_utc
    device.consecutive_heartbeats_ok = (device.consecutive_heartbeats_ok or 0) + 1

    # Clock calculation
    device.local_time = payload.local_time
    device.utc_time = payload.utc_time
    device.timezone_name = payload.timezone_name
    device.utc_offset_minutes = payload.utc_offset_minutes
    device.uptime_sec = payload.uptime_sec
    if payload.w32time_running is not None:
        device.w32time_running = payload.w32time_running

    if payload.utc_time:
        offset_sec = (payload.utc_time - now_utc).total_seconds()
        device.clock_offset_sec = round(offset_sec, 2)
        device.clock_raw_json = {
            "agent_local_time": payload.local_time,
            "agent_utc_time": payload.utc_time.isoformat() if hasattr(payload.utc_time, "isoformat") else str(payload.utc_time),
            "gateway_received_utc": now_utc.isoformat(),
            "offset_sec": round(offset_sec, 2),
            "timezone_name": payload.timezone_name
        }

    # Agent info & state
    if payload.agent_state:
        device.agent_state = payload.agent_state
    if payload.agent_info:
        device.capabilities_json = payload.agent_info.capabilities
        if payload.agent_info.last_error:
            device.last_error_text = payload.agent_info.last_error

    # FBR summary
    if payload.fbr:
        fbr_data = payload.fbr
        device.fbr_status = fbr_data.fbr_status
        device.fbr_ok = fbr_data.fbr_ok
        device.fbr_latency_ms = fbr_data.latency_ms
        device.fbr_http_status = fbr_data.http_status
        device.fbr_consecutive_failures = fbr_data.consecutive_failures
        device.fbr_error = fbr_data.error_text
        device.fbr_last_check = now_utc

        if fbr_data.local_ims_status:
            device.local_ims_status = fbr_data.local_ims_status
        if fbr_data.fbr_connectivity_status:
            device.fbr_connectivity_status = fbr_data.fbr_connectivity_status

        if fbr_data.fbr_ok:
            device.fbr_last_ok_time = now_utc
            device.fbr_consecutive_failures = 0

    # Ingest light sample (CPU, RAM, system disk %) downsampled to 1 per minute
    if payload.cpu_pct is not None and payload.ram_pct is not None:
        last_light = db.query(LightMetric).filter(
            LightMetric.device_pk == device.id
        ).order_by(desc(LightMetric.ts)).first()

        should_record = True
        if last_light and (now_utc - last_light.ts).total_seconds() < 55.0:
            should_record = False

        if should_record:
            light = LightMetric(
                device_pk=device.id,
                ts=now_utc,
                cpu_pct=payload.cpu_pct,
                ram_pct=payload.ram_pct,
                system_disk_pct=payload.system_disk_pct,
                internet_ok=payload.internet_ok if payload.internet_ok is not None else True
            )
            db.add(light)

    # Status restoration: coming back ONLINE immediately
    if device.status in ["OFFLINE", "STOPPED", "RECOVERING"]:
        outage_duration = (now_utc - prev_offline_since).total_seconds() if prev_offline_since else None
        device.status = "ONLINE"
        device.connection_status = "ONLINE"
        device.offline_reason_code = None
        device.offline_reason_text = None
        device.offline_since = None

        # Record RECONNECTED event
        reconn_event = ConnectionEvent(
            device_pk=device.id,
            ts=now_utc,
            type="RECONNECTED",
            reason_code=payload.outage.reason_code if payload.outage else "RECONNECTED",
            reason_text=(
                f"Reconnected after {int(outage_duration or 0)}s outage. "
                f"Agent recovered {payload.outage.buffered_readings if payload.outage else 0} buffered readings."
            ),
            duration_sec=outage_duration,
            details_json=payload.outage.model_dump() if payload.outage else None
        )
        db.add(reconn_event)

    # Resolving agent_offline requires 2 consecutive heartbeats
    if device.consecutive_heartbeats_ok >= 2:
        resolve_alert_if_active(db, device, "agent_offline")

    evaluate_device_time_alerts(db, device)
    evaluate_fbr_alerts(db, device)

    # Fetch pending tasks for this device
    pending_tasks = db.query(AgentTask).filter(
        AgentTask.device_pk == device.id,
        AgentTask.status == "PENDING"
    ).order_by(AgentTask.requested_at.asc()).all()

    dispatched_tasks = []
    for t in pending_tasks:
        t.status = "SENT"
        t.sent_at = now_utc
        dispatched_tasks.append({
            "id": t.id,
            "action": t.action
        })

    db.commit()

    return {
        "status": "ok",
        "device_status": device.status,
        "tasks": dispatched_tasks
    }

@router.post("/metrics")
def ingest_metrics(
    payload: Union[MetricSnapshot, List[MetricSnapshot]],
    device: Device = Depends(get_authenticated_device),
    db: Session = Depends(get_db)
):
    snapshots = [payload] if isinstance(payload, MetricSnapshot) else payload
    now = datetime.now(timezone.utc)
    device.last_seen = now

    for s in snapshots:
        real_printers = filter_real_printers_gateway(
            [p.model_dump() for p in s.printers] if s.printers else []
        )
        services_list = [srv.model_dump() for srv in s.services] if s.services else []

        metric = Metric(
            device_pk=device.id,
            ts=s.ts,
            cpu_pct=s.cpu_pct,
            ram_pct=s.ram_pct,
            ram_used_mb=s.ram_used_mb,
            disk_json=[d.model_dump() for d in s.disks],
            net_json=s.network.model_dump(),
            internet_ok=s.internet_ok,
            printers_json=real_printers,
            services_json=services_list
        )
        db.add(metric)

        # Store network topology on device
        device.network_details_json = s.network.model_dump()

        # Update primary IP if valid
        primary_adapter = next((a for a in s.network.adapters if a.is_primary), None)
        if primary_adapter and primary_adapter.ipv4:
            if not primary_adapter.ipv4.startswith("127.") and not primary_adapter.ipv4.startswith("169.254."):
                device.ip_address = primary_adapter.ipv4

        evaluate_metrics_snapshot(db, device, s)

    db.commit()
    return {"status": "ok", "ingested_count": len(snapshots)}

@router.post("/tasks/{task_id}/result")
def submit_task_result(
    task_id: int,
    payload: AgentTaskResultRequest,
    device: Device = Depends(get_authenticated_device),
    db: Session = Depends(get_db)
):
    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.device_pk == device.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task #{task_id} not found for device {device.device_id}"
        )

    task.status = payload.status
    task.result_text = payload.result_text
    task.finished_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "ok", "task_id": task.id, "final_status": task.status}
