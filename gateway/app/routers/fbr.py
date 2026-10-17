from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_

from app.database import get_db
from app.models import (
    Device, Store, FbrRegistration, PosInvoice, InvoiceFiscalAttempt, 
    CcoIntegrationConfig, AgentTask, User, FbrCheck
)
from app.schemas import (
    FbrRegistrationResponse, FbrRegistrationUpdate, PosInvoiceResponse,
    PosInvoiceRetryRequest, InvoiceFiscalAttemptResponse, InvoiceSummaryCounts
)
from app.deps import get_current_user, require_role, get_user_store_ids, check_store_access
from app.audit import log_audit, get_client_ip

router = APIRouter(prefix="/api/v1/fbr", tags=["FBR Monitoring & Invoice Recovery"])

def utc_now():
    return datetime.now(timezone.utc)

# ----------------- INITIAL REGISTRATIONS SEED DATA -----------------

SEED_BRANCHES = [
    {"code": "RNG-01", "name": "HBK Hypermarket Ring Road", "region": "Peshawar"},
    {"code": "CNT-01", "name": "HBK Supermarket Cantt", "region": "Peshawar"},
    {"code": "ISB-01", "name": "HBK Hypermarket I-8 Islamabad", "region": "Islamabad"},
]

# Registration data provided in specification:
SEED_REGISTRATIONS = [
    # Ring Road Branch
    {"pos_identification": "HYT-POS01", "fbr_pos_id": 149121, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS02", "fbr_pos_id": 149122, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS03", "fbr_pos_id": 149123, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS04", "fbr_pos_id": 149124, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS05", "fbr_pos_id": 149125, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS06", "fbr_pos_id": 149126, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS07", "fbr_pos_id": 149128, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS08", "fbr_pos_id": 149129, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS09", "fbr_pos_id": 149131, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS10", "fbr_pos_id": 149132, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS11", "fbr_pos_id": 149133, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS12", "fbr_pos_id": 149134, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS13", "fbr_pos_id": 149136, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS14", "fbr_pos_id": 149137, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS15", "fbr_pos_id": 149138, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS16", "fbr_pos_id": 149139, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS17", "fbr_pos_id": 149140, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS18", "fbr_pos_id": 149141, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS19 (Gold)", "fbr_pos_id": 149142, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS20 (Gold)", "fbr_pos_id": 149143, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS21 (Gold)", "fbr_pos_id": 149144, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS22", "fbr_pos_id": 149145, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS23 (Self-Checkout)", "fbr_pos_id": 149146, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS24 (Jewellery)", "fbr_pos_id": 149147, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS25 (Pharmacy)", "fbr_pos_id": 156465, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS-CS (Customer Service)", "fbr_pos_id": 156468, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "HYT-POS27 (Textile/Perfume)", "fbr_pos_id": 156469, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "Test", "fbr_pos_id": 156477, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    {"pos_identification": "ISB Self CheckOut", "fbr_pos_id": 189546, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01"},
    # Unidentified registrations (marked pending admin review, not automatically mapped)
    {"pos_identification": "----------", "fbr_pos_id": 156470, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01", "is_unidentified": True, "admin_notes": "Inactive registration shown as ----------. Pending administrator review."},
    {"pos_identification": "----------", "fbr_pos_id": 189547, "branch_name": "HBK Hypermarket Ring Road", "store_code": "RNG-01", "is_unidentified": True, "admin_notes": "Inactive registration shown as ----------. Pending administrator review."},

    # Cantt Branch
    {"pos_identification": "CNT-POS01", "fbr_pos_id": 161538, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},
    {"pos_identification": "CNT-POS02", "fbr_pos_id": 161540, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},
    {"pos_identification": "CNT-POS03", "fbr_pos_id": 161541, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},
    {"pos_identification": "CNT-POS04", "fbr_pos_id": 161542, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},
    {"pos_identification": "CNT-POS05", "fbr_pos_id": 161543, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},
    {"pos_identification": "CNT-POS06", "fbr_pos_id": 161544, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},
    {"pos_identification": "CNT-POS07", "fbr_pos_id": 161545, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},
    {"pos_identification": "CNT-POS08 Gold", "fbr_pos_id": 161546, "branch_name": "HBK Supermarket Cantt", "store_code": "CNT-01"},

    # I-8 Islamabad Branch
    {"pos_identification": "ISB POS01", "fbr_pos_id": 189912, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS02", "fbr_pos_id": 189913, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS03", "fbr_pos_id": 189914, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS04", "fbr_pos_id": 189915, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS05", "fbr_pos_id": 189916, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS06", "fbr_pos_id": 189917, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS07", "fbr_pos_id": 189979, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS08", "fbr_pos_id": 189991, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS09", "fbr_pos_id": 190000, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS10", "fbr_pos_id": 190001, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS11", "fbr_pos_id": 190041, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS12", "fbr_pos_id": 190042, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS13", "fbr_pos_id": 190117, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS14", "fbr_pos_id": 190381, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS15", "fbr_pos_id": 190148, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS16", "fbr_pos_id": 190149, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS17", "fbr_pos_id": 190151, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POS19", "fbr_pos_id": 190155, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "ISB POSCS", "fbr_pos_id": 190181, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
    {"pos_identification": "TEST POS", "fbr_pos_id": 196399, "branch_name": "HBK Hypermarket I-8 Islamabad", "store_code": "ISB-01"},
]

def ensure_fbr_seeds(db: Session):
    """
    Ensures the 3 registered stores exist and seeds initial FBR registration mappings.
    Safely matches existing devices without creating duplicates.
    Leaves unidentified entries (156470, 189547) unmapped.
    """
    now = utc_now()

    # 1. Ensure stores exist
    store_map: Dict[str, Store] = {}
    for sb in SEED_BRANCHES:
        store = db.query(Store).filter(Store.code == sb["code"]).first()
        if not store:
            store = Store(
                code=sb["code"],
                name=sb["name"],
                region=sb["region"],
                created_at=now
            )
            db.add(store)
            db.commit()
            db.refresh(store)
        store_map[sb["code"]] = store

        # Also ensure CCO config record exists with safe defaults
        cco_cfg = db.query(CcoIntegrationConfig).filter(CcoIntegrationConfig.store_id == store.id).first()
        if not cco_cfg:
            cco_cfg = CcoIntegrationConfig(
                store_id=store.id,
                cco_install_path=r"C:\SapCustomerCheckout\cco",
                cco_derby_path=r"C:\SapCustomerCheckout\cco\db\CCO",
                status="INVOICE SOURCE NOT CONFIGURED",
                notes="Embedded Derby database preserved untouched. Integration interface pending authorized CCO sync export."
            )
            db.add(cco_cfg)
            db.commit()

    # 2. Seed FBR Registrations
    for reg_item in SEED_REGISTRATIONS:
        existing = db.query(FbrRegistration).filter(FbrRegistration.fbr_pos_id == reg_item["fbr_pos_id"]).first()
        if not existing:
            st = store_map.get(reg_item["store_code"])
            store_id = st.id if st else None
            is_unid = reg_item.get("is_unidentified", False)

            # Look for existing device with matching identifier
            matched_device = None
            if not is_unid and store_id:
                clean_id = reg_item["pos_identification"].strip().upper().replace(" ", "").replace("-", "")
                devs = db.query(Device).filter(Device.store_id == store_id).all()
                for d in devs:
                    d_clean = (d.device_id or "").strip().upper().replace(" ", "").replace("-", "")
                    c_clean = (d.computer_name or "").strip().upper().replace(" ", "").replace("-", "")
                    if clean_id in [d_clean, c_clean] or (clean_id and clean_id == d_clean):
                        matched_device = d
                        break

            new_reg = FbrRegistration(
                fbr_pos_id=reg_item["fbr_pos_id"],
                pos_identification=reg_item["pos_identification"],
                branch_name=reg_item["branch_name"],
                store_id=store_id,
                device_pk=matched_device.id if matched_device else None,
                portal_status="Connected",
                connected_date="2026-01-15",
                code=str(reg_item["fbr_pos_id"]),
                pos_software_version="CCO 2.0 FP18",
                is_unidentified=is_unid,
                token_configured=True,
                admin_notes=reg_item.get("admin_notes"),
                created_at=now,
                updated_at=now
            )
            db.add(new_reg)
            db.commit()

            # If device was matched, sync fbr fields onto device
            if matched_device:
                matched_device.fbr_pos_id = reg_item["fbr_pos_id"]
                matched_device.fbr_pos_identification = reg_item["pos_identification"]
                db.commit()

# ----------------- FBR REGISTRATION ENDPOINTS -----------------

@router.get("/registrations")
def list_fbr_registrations(
    branch: Optional[str] = None,
    store_id: Optional[int] = None,
    unmapped: Optional[bool] = None,
    unidentified: Optional[bool] = None,
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List registered POS mappings with live connectivity telemetry.
    Token values are never returned to the frontend.
    """
    ensure_fbr_seeds(db)

    query = db.query(FbrRegistration)

    if user.role != "admin":
        accessible_store_ids = get_user_store_ids(user, db)
        query = query.filter(or_(
            FbrRegistration.store_id.in_(accessible_store_ids),
            FbrRegistration.store_id == None
        ))

    if branch:
        query = query.filter(FbrRegistration.branch_name.ilike(f"%{branch.strip()}%"))
    if store_id:
        query = query.filter(FbrRegistration.store_id == store_id)
    if unmapped is True:
        query = query.filter(FbrRegistration.device_pk == None)
    if unidentified is not None:
        query = query.filter(FbrRegistration.is_unidentified == unidentified)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(
            FbrRegistration.pos_identification.ilike(s),
            FbrRegistration.branch_name.ilike(s),
            FbrRegistration.code.ilike(s)
        ))

    registrations = query.order_by(FbrRegistration.branch_name, FbrRegistration.pos_identification).all()

    # Join with live device status
    results = []
    for reg in registrations:
        dev = reg.device
        item = {
            "id": reg.id,
            "fbr_pos_id": reg.fbr_pos_id,
            "pos_identification": reg.pos_identification,
            "branch_name": reg.branch_name,
            "store_code": reg.store.code if reg.store else None,
            "store_id": reg.store_id,
            "device_pk": reg.device_pk,
            "device_id": dev.device_id if dev else None,
            "portal_status": reg.portal_status,
            "connected_date": reg.connected_date,
            "code": reg.code,
            "pos_software_version": reg.pos_software_version,
            "is_unidentified": reg.is_unidentified,
            "token_configured": reg.token_configured,
            "admin_notes": reg.admin_notes,
            "created_at": reg.created_at.isoformat() if reg.created_at else None,
            "updated_at": reg.updated_at.isoformat() if reg.updated_at else None,
            # Live monitoring fields
            "device_status": dev.status if dev else "UNKNOWN",
            "local_ims_status": dev.local_ims_status if dev else "UNKNOWN",
            "fbr_connectivity_status": dev.fbr_connectivity_status if dev else "UNKNOWN",
            "fbr_last_check": dev.fbr_last_check.isoformat() if dev and dev.fbr_last_check else None,
            "fbr_last_ok_time": dev.fbr_last_ok_time.isoformat() if dev and dev.fbr_last_ok_time else None,
            "fbr_latency_ms": dev.fbr_latency_ms if dev else None,
            "fbr_consecutive_failures": dev.fbr_consecutive_failures if dev else 0,
            "fbr_error": dev.fbr_error if dev else None,
            "last_fiscal_sync": dev.last_fiscal_sync.isoformat() if dev and dev.last_fiscal_sync else None
        }
        results.append(item)

    return results

@router.put("/registrations/{registration_id}")
def update_fbr_registration(
    registration_id: int,
    payload: FbrRegistrationUpdate,
    request: Request,
    user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Allows authorized administrator to edit device mapping or admin notes.
    Prevents duplicate device associations and preserves separate identification.
    """
    reg = db.query(FbrRegistration).filter(FbrRegistration.id == registration_id).first()
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FBR Registration not found")

    old_device_pk = reg.device_pk

    if payload.device_pk is not None:
        if payload.device_pk == "" or payload.device_pk.strip().lower() in ["none", "null"]:
            # Unlink
            if reg.device:
                reg.device.fbr_pos_id = None
                reg.device.fbr_pos_identification = None
            reg.device_pk = None
        else:
            dev = db.query(Device).filter(Device.id == payload.device_pk).first()
            if not dev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target device not found")
            
            # Check if device is mapped to another FBR POS ID
            existing_reg = db.query(FbrRegistration).filter(
                FbrRegistration.device_pk == dev.id,
                FbrRegistration.id != reg.id
            ).first()
            if existing_reg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Device '{dev.device_id}' is already mapped to FBR POS ID {existing_reg.fbr_pos_id}"
                )
            
            # Unlink old device if changed
            if reg.device and reg.device.id != dev.id:
                reg.device.fbr_pos_id = None
                reg.device.fbr_pos_identification = None

            reg.device_pk = dev.id
            dev.fbr_pos_id = reg.fbr_pos_id
            dev.fbr_pos_identification = reg.pos_identification

    if payload.store_id is not None:
        st = db.query(Store).filter(Store.id == payload.store_id).first()
        if not st:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target store not found")
        reg.store_id = st.id

    if payload.admin_notes is not None:
        reg.admin_notes = payload.admin_notes.strip()

    reg.updated_at = utc_now()
    db.commit()
    db.refresh(reg)

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="fbr_mapping_updated",
        target=f"fbr_pos_{reg.fbr_pos_id}",
        ip=get_client_ip(request),
        detail_json={
            "fbr_pos_id": reg.fbr_pos_id,
            "old_device_pk": old_device_pk,
            "new_device_pk": reg.device_pk,
            "notes": reg.admin_notes
        }
    )

    return {
        "id": reg.id,
        "fbr_pos_id": reg.fbr_pos_id,
        "pos_identification": reg.pos_identification,
        "device_pk": reg.device_pk,
        "store_id": reg.store_id,
        "admin_notes": reg.admin_notes,
        "updated_at": reg.updated_at.isoformat()
    }

@router.post("/registrations/{registration_id}/check-now")
def trigger_registration_fbr_check(
    registration_id: int,
    request: Request,
    user: User = Depends(require_role(["admin", "technician"])),
    db: Session = Depends(get_db)
):
    """
    Queue an official fbr_check_now task for the mapped POS agent.
    Separates local IMS probe from FBR cloud probe without calling invoice submission.
    """
    reg = db.query(FbrRegistration).filter(FbrRegistration.id == registration_id).first()
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FBR Registration not found")

    if not reg.device_pk or not reg.device:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"FBR POS ID {reg.fbr_pos_id} is not mapped to an active terminal agent. Map a device first."
        )

    dev = reg.device
    check_store_access(user, dev.store_id, db)

    now = utc_now()
    dev.fbr_connectivity_status = "CHECKING"
    
    task = AgentTask(
        device_pk=dev.id,
        action="fbr_check_now",
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
        action="fbr_check_dispatched",
        target=dev.device_id,
        ip=get_client_ip(request),
        detail_json={
            "task_id": task.id,
            "device_id": dev.device_id,
            "fbr_pos_id": reg.fbr_pos_id
        }
    )

    return {
        "message": f"FBR probe task queued for {dev.device_id} (FBR POS {reg.fbr_pos_id})",
        "task_id": task.id,
        "status": "CHECKING"
    }

# ----------------- POS INVOICE & SAFE RETRY ENDPOINTS -----------------

@router.get("/invoices/summary", response_model=InvoiceSummaryCounts)
def get_invoice_summary_counts(
    store_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns summary counts of invoices partitioned by fiscal status:
    accepted, rejected, pending, unknown, reconciliation-required, and safely retryable.
    Also returns CCO configuration state ('INVOICE SOURCE NOT CONFIGURED' until connected).
    """
    query = db.query(PosInvoice)
    if user.role != "admin":
        accessible_store_ids = get_user_store_ids(user, db)
        query = query.filter(PosInvoice.store_id.in_(accessible_store_ids))

    if store_id:
        query = query.filter(PosInvoice.store_id == store_id)

    total = query.count()
    accepted = query.filter(PosInvoice.fiscal_status == "ACCEPTED").count()
    rejected = query.filter(PosInvoice.fiscal_status == "REJECTED").count()
    pending = query.filter(PosInvoice.fiscal_status == "PENDING").count()
    unknown = query.filter(PosInvoice.fiscal_status == "UNKNOWN").count()
    recon_req = query.filter(PosInvoice.fiscal_status == "RECONCILIATION_REQUIRED").count()
    safely_retryable = query.filter(PosInvoice.is_retry_eligible == True, PosInvoice.fiscal_status != "ACCEPTED").count()

    # Check CCO integration status
    cco_cfg = db.query(CcoIntegrationConfig).first()
    source_configured = False
    cco_path = r"C:\SapCustomerCheckout\cco\db\CCO"
    if cco_cfg and cco_cfg.status == "CONFIGURED":
        source_configured = True

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "pending": pending,
        "unknown": unknown,
        "reconciliation_required": recon_req,
        "safely_retryable": safely_retryable,
        "source_configured": source_configured,
        "cco_path": cco_path
    }

@router.get("/invoices")
def list_pos_invoices(
    store_id: Optional[int] = None,
    device_id: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists invoices created locally during FBR outages or pending posting.
    Supports filtering by store, POS, invoice number, date range, and status.
    """
    query = db.query(PosInvoice)

    if user.role != "admin":
        accessible_store_ids = get_user_store_ids(user, db)
        query = query.filter(PosInvoice.store_id.in_(accessible_store_ids))

    if store_id:
        query = query.filter(PosInvoice.store_id == store_id)
    if device_id:
        dev = db.query(Device).filter(Device.device_id == device_id.strip()).first()
        if dev:
            query = query.filter(PosInvoice.device_pk == dev.id)
    if status and status.strip() != "ALL":
        query = query.filter(PosInvoice.fiscal_status == status.strip().upper())
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(
            PosInvoice.original_invoice_no.ilike(s),
            PosInvoice.internal_invoice_id.ilike(s),
            PosInvoice.fbr_invoice_number.ilike(s)
        ))

    invoices = query.order_by(desc(PosInvoice.invoice_datetime)).offset(offset).limit(limit).all()

    results = []
    for inv in invoices:
        results.append({
            "id": inv.id,
            "internal_invoice_id": inv.internal_invoice_id,
            "original_invoice_no": inv.original_invoice_no,
            "store_id": inv.store_id,
            "store_code": inv.store.code if inv.store else None,
            "store_name": inv.store.name if inv.store else None,
            "device_pk": inv.device_pk,
            "device_id": inv.device.device_id if inv.device else None,
            "fbr_pos_id": inv.fbr_pos_id,
            "invoice_datetime": inv.invoice_datetime.isoformat() if inv.invoice_datetime else None,
            "total_amount": inv.total_amount,
            "tax_amount": inv.tax_amount,
            "currency": inv.currency,
            "fiscal_status": inv.fiscal_status,
            "fbr_invoice_number": inv.fbr_invoice_number,
            "qr_code": inv.qr_code,
            "attempts_count": inv.attempts_count,
            "last_attempt_at": inv.last_attempt_at.isoformat() if inv.last_attempt_at else None,
            "last_response_code": inv.last_response_code,
            "last_response_text": inv.last_response_text,
            "is_retry_eligible": inv.is_retry_eligible,
            "reconciliation_status": inv.reconciliation_status,
            "blocked_reason": inv.blocked_reason,
            "active_retry_task_id": inv.active_retry_task_id,
            "locked_at": inv.locked_at.isoformat() if inv.locked_at else None,
            "locked_by": inv.locked_by,
            "created_at": inv.created_at.isoformat() if inv.created_at else None
        })

    return results

@router.get("/invoices/{invoice_id}")
def get_invoice_detail(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves full invoice record along with complete attempt history.
    """
    inv = db.query(PosInvoice).filter(PosInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    check_store_access(user, inv.store_id, db)

    attempts = [
        {
            "id": att.id,
            "invoice_id": att.invoice_id,
            "task_id": att.task_id,
            "attempt_number": att.attempt_number,
            "attempt_type": att.attempt_type,
            "initiated_by": att.initiated_by,
            "initiated_at": att.initiated_at.isoformat() if att.initiated_at else None,
            "completed_at": att.completed_at.isoformat() if att.completed_at else None,
            "response_code": att.response_code,
            "response_body_text": att.response_body_text,
            "outcome": att.outcome,
            "fbr_invoice_number": att.fbr_invoice_number,
            "error_message": att.error_message
        }
        for att in inv.attempts
    ]

    return {
        "invoice": {
            "id": inv.id,
            "internal_invoice_id": inv.internal_invoice_id,
            "original_invoice_no": inv.original_invoice_no,
            "store_id": inv.store_id,
            "store_code": inv.store.code if inv.store else None,
            "store_name": inv.store.name if inv.store else None,
            "device_pk": inv.device_pk,
            "device_id": inv.device.device_id if inv.device else None,
            "fbr_pos_id": inv.fbr_pos_id,
            "invoice_datetime": inv.invoice_datetime.isoformat() if inv.invoice_datetime else None,
            "total_amount": inv.total_amount,
            "tax_amount": inv.tax_amount,
            "currency": inv.currency,
            "fiscal_status": inv.fiscal_status,
            "fbr_invoice_number": inv.fbr_invoice_number,
            "qr_code": inv.qr_code,
            "attempts_count": inv.attempts_count,
            "last_attempt_at": inv.last_attempt_at.isoformat() if inv.last_attempt_at else None,
            "last_response_code": inv.last_response_code,
            "last_response_text": inv.last_response_text,
            "is_retry_eligible": inv.is_retry_eligible,
            "reconciliation_status": inv.reconciliation_status,
            "blocked_reason": inv.blocked_reason,
            "active_retry_task_id": inv.active_retry_task_id,
            "locked_at": inv.locked_at.isoformat() if inv.locked_at else None,
            "locked_by": inv.locked_by,
            "created_at": inv.created_at.isoformat() if inv.created_at else None
        },
        "attempts": attempts
    }

@router.post("/invoices/{invoice_id}/retry")
def retry_invoice_fiscalization(
    invoice_id: int,
    payload: PosInvoiceRetryRequest,
    request: Request,
    user: User = Depends(require_role(["admin", "technician"])),
    db: Session = Depends(get_db)
):
    """
    Mandatory 14-step safe manual retry pipeline:
    1. Verify authoritative source identity
    2. Check if already accepted
    3. Check reconciliation status (blocks if RECONCILIATION_REQUIRED)
    4. Guard against concurrent in-flight retries
    5. Persist attempt record BEFORE submitting
    6. Queue task to agent for authorized submission to local PRAL
    """
    now = utc_now()
    ip = get_client_ip(request)

    inv = db.query(PosInvoice).filter(PosInvoice.id == invoice_id).with_for_update().first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice record not found")

    check_store_access(user, inv.store_id, db)

    # Rule 1: Never submit already posted invoices
    if inv.fiscal_status == "ACCEPTED" or inv.fbr_invoice_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice '{inv.original_invoice_no}' has already been accepted with FBR # {inv.fbr_invoice_number}."
        )

    # Rule 2: Uncertain responses require manual reconciliation first
    if inv.fiscal_status == "RECONCILIATION_REQUIRED" or inv.reconciliation_status == "RECONCILIATION_REQUIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is marked RECONCILIATION_REQUIRED. Previous attempt outcome is uncertain. Reconcile status before retrying."
        )

    # Rule 3: Concurrent lock check
    if inv.locked_at and (now - inv.locked_at) < timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Retry is already in progress for invoice '{inv.original_invoice_no}' by {inv.locked_by}."
        )

    # Acquire lock and increment attempt count
    inv.locked_at = now
    inv.locked_by = user.username
    inv.attempts_count += 1
    attempt_num = inv.attempts_count

    # Persist attempt record BEFORE submission
    attempt = InvoiceFiscalAttempt(
        invoice_id=inv.id,
        attempt_number=attempt_num,
        attempt_type="MANUAL_RETRY",
        initiated_by=user.username,
        initiated_at=now,
        outcome="IN_FLIGHT",
        request_payload_json={
            "original_invoice_no": inv.original_invoice_no,
            "fbr_pos_id": inv.fbr_pos_id,
            "total_amount": inv.total_amount,
            "reason": payload.reason
        }
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Queue retry task to agent
    task = AgentTask(
        device_pk=inv.device_pk,
        action="retry_invoice",
        status="PENDING",
        requested_by=user.username,
        requested_at=now
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    attempt.task_id = task.id
    inv.active_retry_task_id = task.id
    inv.last_attempt_at = now
    db.commit()

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="invoice_fiscal_retry_initiated",
        target=inv.original_invoice_no,
        ip=ip,
        detail_json={
            "invoice_id": inv.id,
            "original_invoice_no": inv.original_invoice_no,
            "attempt_number": attempt_num,
            "task_id": task.id,
            "reason": payload.reason
        }
    )

    return {
        "message": f"Safe retry attempt #{attempt_num} persisted and queued for {inv.original_invoice_no}",
        "attempt_id": attempt.id,
        "task_id": task.id,
        "status": "IN_FLIGHT"
    }

@router.post("/invoices/{invoice_id}/reconcile")
def reconcile_invoice_status(
    invoice_id: int,
    payload: Dict[str, Any],
    request: Request,
    user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Allows administrator to establish fiscalization status after verification with PRAL portal:
    - ACCEPTED: records verified FBR invoice number and marks invoice settled.
    - NOT_POSTED: clears ambiguity and enables safe manual retry.
    """
    now = utc_now()
    ip = get_client_ip(request)

    inv = db.query(PosInvoice).filter(PosInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice record not found")

    new_status = (payload.get("status") or "").strip().upper()
    fbr_inv_no = (payload.get("fbr_invoice_number") or "").strip()
    notes = (payload.get("notes") or "").strip()

    if not notes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reconciliation notes are mandatory")

    if new_status == "ACCEPTED":
        if not fbr_inv_no:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="FBR Invoice Number is required to reconcile as ACCEPTED")
        inv.fiscal_status = "ACCEPTED"
        inv.fbr_invoice_number = fbr_inv_no
        inv.reconciliation_status = "RECONCILED_ACCEPTED"
        inv.is_retry_eligible = False
        inv.blocked_reason = None
    elif new_status in ["NOT_POSTED", "REJECTED"]:
        inv.fiscal_status = "REJECTED" if new_status == "REJECTED" else "PENDING"
        inv.reconciliation_status = "RECONCILED_NOT_POSTED"
        inv.is_retry_eligible = True
        inv.blocked_reason = None
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status must be ACCEPTED, NOT_POSTED, or REJECTED")

    # Release any lock
    inv.locked_at = None
    inv.locked_by = None
    inv.updated_at = now

    # Record reconciliation audit
    attempt = InvoiceFiscalAttempt(
        invoice_id=inv.id,
        attempt_number=inv.attempts_count + 1,
        attempt_type="RECONCILIATION",
        initiated_by=user.username,
        initiated_at=now,
        completed_at=now,
        outcome=inv.fiscal_status,
        fbr_invoice_number=inv.fbr_invoice_number,
        response_body_text=f"Manual Reconciliation by {user.username}: {notes}"
    )
    inv.attempts_count += 1
    db.add(attempt)
    db.commit()

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="invoice_reconciled",
        target=inv.original_invoice_no,
        ip=ip,
        detail_json={
            "invoice_id": inv.id,
            "status": inv.fiscal_status,
            "fbr_invoice_number": inv.fbr_invoice_number,
            "notes": notes
        }
    )

    return {
        "message": f"Invoice {inv.original_invoice_no} successfully reconciled as {inv.fiscal_status}",
        "invoice_id": inv.id,
        "fiscal_status": inv.fiscal_status,
        "fbr_invoice_number": inv.fbr_invoice_number,
        "is_retry_eligible": inv.is_retry_eligible
    }
