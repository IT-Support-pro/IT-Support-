from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from fastapi import Request
from app.models import AuditLog

def log_audit(
    db: Session,
    actor_type: str,
    actor: str,
    action: str,
    target: Optional[str] = None,
    ip: Optional[str] = None,
    detail_json: Optional[Dict[str, Any]] = None,
    commit: bool = True
) -> AuditLog:
    """Helper to persist audit logs consistently across endpoints"""
    audit_entry = AuditLog(
        actor_type=actor_type,
        actor=actor,
        action=action,
        target=target,
        ip=ip,
        detail_json=detail_json or {}
    )
    db.add(audit_entry)
    if commit:
        db.commit()
    return audit_entry

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
