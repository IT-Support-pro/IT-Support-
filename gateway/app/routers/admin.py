from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Store, UserStore, EnrollmentKey, Device
from app.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    AssignStoresRequest,
    StoreCreate,
    StoreUpdate,
    StoreResponse,
    EnrollmentKeyCreatedResponse,
    DeviceResponse
)
from app.security import (
    hash_password,
    generate_enrollment_key,
    hash_secret,
)
from app.deps import require_role
from app.audit import log_audit, get_client_ip
from app.config import settings

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"], dependencies=[Depends(require_role(["admin"]))])

# ----------------- USER CRUD -----------------

@router.get("/users", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    results = []
    for u in users:
        assigned = db.query(UserStore.store_id).filter(UserStore.user_id == u.id).all()
        results.append(UserResponse(
            id=u.id,
            username=u.username,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            assigned_store_ids=[s[0] for s in assigned]
        ))
    return results

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    existing = db.query(User).filter(User.username == payload.username.strip()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    new_user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="create_user",
        target=new_user.username,
        ip=ip,
        detail_json={"role": new_user.role, "user_id": new_user.id}
    )

    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        assigned_store_ids=[]
    )

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.password:
        target.password_hash = hash_password(payload.password)
    if payload.role:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active

    db.commit()
    db.refresh(target)

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="update_user",
        target=target.username,
        ip=ip,
        detail_json={"user_id": target.id, "role": target.role, "is_active": target.is_active}
    )

    assigned = db.query(UserStore.store_id).filter(UserStore.user_id == target.id).all()
    return UserResponse(
        id=target.id,
        username=target.username,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        assigned_store_ids=[s[0] for s in assigned]
    )

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    if admin_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own active admin account")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    username = target.username
    db.delete(target)
    db.commit()

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="delete_user",
        target=username,
        ip=ip,
        detail_json={"user_id": user_id}
    )
    return None

# ----------------- STORE ASSIGNMENT -----------------

@router.post("/users/{user_id}/assign-stores", response_model=UserResponse)
def assign_technician_stores(
    user_id: int,
    payload: AssignStoresRequest,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Clear existing store assignments
    db.query(UserStore).filter(UserStore.user_id == user_id).delete()

    # Re-assign
    for s_id in payload.store_ids:
        store = db.query(Store).filter(Store.id == s_id).first()
        if store:
            db.add(UserStore(user_id=user_id, store_id=s_id))

    db.commit()
    db.refresh(target)

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="assign_stores",
        target=target.username,
        ip=ip,
        detail_json={"assigned_stores": payload.store_ids}
    )

    return UserResponse(
        id=target.id,
        username=target.username,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        assigned_store_ids=payload.store_ids
    )

# ----------------- STORE CRUD -----------------

@router.get("/stores", response_model=List[StoreResponse])
def list_stores(db: Session = Depends(get_db)):
    return db.query(Store).all()

@router.post("/stores", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
def create_store(
    payload: StoreCreate,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    code_clean = payload.code.strip().upper()
    existing = db.query(Store).filter(Store.code == code_clean).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Store code {code_clean} already exists")

    store = Store(
        code=code_clean,
        name=payload.name.strip(),
        region=payload.region.strip(),
        created_at=datetime.now(timezone.utc)
    )
    db.add(store)
    db.commit()
    db.refresh(store)

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="create_store",
        target=store.code,
        ip=ip,
        detail_json={"store_id": store.id, "name": store.name, "region": store.region}
    )
    return store

@router.put("/stores/{store_id}", response_model=StoreResponse)
def update_store(
    store_id: int,
    payload: StoreUpdate,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    if payload.name:
        store.name = payload.name.strip()
    if payload.region:
        store.region = payload.region.strip()

    db.commit()
    db.refresh(store)

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="update_store",
        target=store.code,
        ip=ip,
        detail_json={"store_id": store.id}
    )
    return store

@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store(
    store_id: int,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    code = store.code
    db.delete(store)
    db.commit()

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="delete_store",
        target=code,
        ip=ip,
        detail_json={"store_id": store_id}
    )
    return None

# ----------------- ENROLLMENT KEYS -----------------

@router.post("/stores/{store_id}/enrollment-key", response_model=EnrollmentKeyCreatedResponse)
def create_enrollment_key(
    store_id: int,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    raw_key = generate_enrollment_key(length=settings.ENROLLMENT_KEY_LENGTH)
    key_hash = hash_secret(raw_key)

    key_record = EnrollmentKey(
        store_id=store.id,
        key_hash=key_hash,
        created_by=admin_user.id,
        created_at=datetime.now(timezone.utc),
        revoked=False
    )
    db.add(key_record)
    db.commit()
    db.refresh(key_record)

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="generate_enrollment_key",
        target=store.code,
        ip=ip,
        detail_json={"key_id": key_record.id, "store_id": store.id}
    )

    return EnrollmentKeyCreatedResponse(
        enrollment_key=raw_key,
        store_id=store.id,
        created_at=key_record.created_at,
        revoked=key_record.revoked
    )

@router.post("/enrollment-keys/{key_id}/revoke")
def revoke_enrollment_key(
    key_id: int,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    key_record = db.query(EnrollmentKey).filter(EnrollmentKey.id == key_id).first()
    if not key_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment key not found")

    key_record.revoked = True
    db.commit()

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="revoke_enrollment_key",
        target=f"key_{key_id}",
        ip=ip,
        detail_json={"key_id": key_id, "store_id": key_record.store_id}
    )
    return {"status": "ok", "message": f"Enrollment key #{key_id} has been revoked"}

# ----------------- TOKEN REVOCATION -----------------

@router.post("/devices/{device_id}/revoke-token")
def revoke_device_token(
    device_id: str,
    request: Request,
    admin_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    device = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # Invalidate token by setting a dummy unmatchable hash
    device.token_hash = "REVOKED_" + datetime.now(timezone.utc).isoformat()
    device.status = "DEGRADED"
    db.commit()

    log_audit(
        db,
        actor_type="user",
        actor=admin_user.username,
        action="revoke_device_token",
        target=device.device_id,
        ip=ip,
        detail_json={"device_id": device.device_id}
    )

    return {"status": "ok", "message": f"Device token for {device.device_id} revoked"}
