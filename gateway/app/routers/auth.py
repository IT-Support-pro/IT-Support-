from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserStore
from app.schemas import UserLogin, TokenResponse, RefreshRequest, UserResponse
from app.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.audit import log_audit, get_client_ip
from app.deps import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 5

@router.post("/login", response_model=TokenResponse)
def login(login_req: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    now = datetime.now(timezone.utc)
    
    user = db.query(User).filter(User.username == login_req.username.strip()).first()
    
    if not user:
        # Audit failed login for non-existent user
        log_audit(
            db,
            actor_type="user",
            actor=login_req.username.strip(),
            action="login_failed",
            target="auth",
            ip=ip,
            detail_json={"reason": "user_not_found"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Check if locked out
    if user.locked_until:
        # Ensure locked_until is tz-aware for comparison
        locked_until_tz = user.locked_until
        if locked_until_tz.tzinfo is None:
            locked_until_tz = locked_until_tz.replace(tzinfo=timezone.utc)
        
        if now < locked_until_tz:
            remaining = int((locked_until_tz - now).total_seconds())
            log_audit(
                db,
                actor_type="user",
                actor=user.username,
                action="login_rejected_locked",
                target="auth",
                ip=ip,
                detail_json={"locked_remaining_sec": remaining}
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked due to consecutive failed attempts. Try again in {remaining} seconds."
            )
        else:
            # Lock has expired, reset counter
            user.locked_until = None
            user.failed_login_count = 0
            db.commit()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact system administrator."
        )

    # Verify password
    if not verify_password(login_req.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= LOCKOUT_THRESHOLD:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            db.commit()
            log_audit(
                db,
                actor_type="user",
                actor=user.username,
                action="account_locked",
                target="auth",
                ip=ip,
                detail_json={"attempts": user.failed_login_count, "lockout_minutes": LOCKOUT_MINUTES}
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked for {LOCKOUT_MINUTES} minutes due to 5 failed attempts."
            )
        db.commit()
        log_audit(
            db,
            actor_type="user",
            actor=user.username,
            action="login_failed",
            target="auth",
            ip=ip,
            detail_json={"attempt": user.failed_login_count}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Login successful: reset failed attempts
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()

    # Create tokens
    token_claims = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role
    }
    access_token = create_access_token(token_claims, expires_delta=timedelta(minutes=15))
    refresh_token = create_refresh_token(token_claims, expires_delta=timedelta(days=7))

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="login_success",
        target="auth",
        ip=ip,
        detail_json={"role": user.role}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in_sec=900
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh_token_endpoint(refresh_req: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    try:
        payload = decode_token(refresh_req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable or deactivated")

    token_claims = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role
    }
    new_access = create_access_token(token_claims, expires_delta=timedelta(minutes=15))
    new_refresh = create_refresh_token(token_claims, expires_delta=timedelta(days=7))

    log_audit(
        db,
        actor_type="user",
        actor=user.username,
        action="token_refreshed",
        target="auth",
        ip=ip
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in_sec=900
    )

@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assigned_store_ids = []
    if user.role != "admin":
        stores = db.query(UserStore.store_id).filter(UserStore.user_id == user.id).all()
        assigned_store_ids = [s[0] for s in stores]
    
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        assigned_store_ids=assigned_store_ids
    )
