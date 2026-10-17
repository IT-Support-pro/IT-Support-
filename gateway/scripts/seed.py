#!/usr/bin/env python3
"""
Seed script for HBK IT Monitoring System Gateway.
Creates initial admin user, default store 'ISL-01', enrollment key,
and seeds the default Alert Rules.
"""
import os
import sys
import secrets
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, Base, engine
from app.models import User, Store, EnrollmentKey, AlertRule
from app.security import hash_password, generate_enrollment_key, hash_secret
from app.config import settings

DEFAULT_ALERT_RULES = [
    {
        "rule_key": "cpu_high",
        "name": "High CPU Usage",
        "severity": "warning",
        "threshold_value": 90.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "CPU usage exceeds 90% for 2 consecutive readings"
    },
    {
        "rule_key": "ram_high",
        "name": "High Memory Usage",
        "severity": "warning",
        "threshold_value": 85.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "RAM usage exceeds 85% for 2 consecutive readings"
    },
    {
        "rule_key": "disk_low",
        "name": "Low Disk Space",
        "severity": "critical",
        "threshold_value": 90.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "Any mounted storage drive exceeds 90% disk capacity"
    },
    {
        "rule_key": "service_down",
        "name": "Critical Service Stopped",
        "severity": "critical",
        "threshold_value": 0.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "Any monitored POS/Windows service is not in Running state"
    },
    {
        "rule_key": "printer_offline",
        "name": "Printer Offline or Error",
        "severity": "warning",
        "threshold_value": 0.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "Any receipt/kitchen printer reports Offline or Error state"
    },
    {
        "rule_key": "internet_down",
        "name": "Internet Connectivity Lost",
        "severity": "critical",
        "threshold_value": 2.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "Internet connectivity fails for 2 consecutive metrics snapshots"
    },
    {
        "rule_key": "agent_offline",
        "name": "Agent / Terminal Offline",
        "severity": "critical",
        "threshold_value": float(settings.OFFLINE_AFTER_SEC),
        "duration_seconds": settings.OFFLINE_AFTER_SEC,
        "enabled": True,
        "description": "Terminal sent no heartbeat or telemetry for over OFFLINE_AFTER_SEC seconds"
    },
    {
        "rule_key": "clock_drift",
        "name": "POS Clock Drift",
        "severity": "warning",
        "threshold_value": 120.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "POS system clock drifts > 120s (warning) or > 600s (critical) from gateway UTC time"
    },
    {
        "rule_key": "timezone_mismatch",
        "name": "Timezone Configuration Mismatch",
        "severity": "warning",
        "threshold_value": 0.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "POS timezone differs from EXPECTED_TIMEZONE setting"
    },
    {
        "rule_key": "fbr_down",
        "name": "FBR Fiscal Portal Unreachable",
        "severity": "critical",
        "threshold_value": 2.0,
        "duration_seconds": 0,
        "enabled": True,
        "description": "FBR fiscal invoice portal unreachable for 2 consecutive checks"
    }
]

def seed():
    print("=" * 65)
    print(" HBK IT Monitoring Gateway - Database Seeder (Stage 2)")
    print("=" * 65)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Admin User
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD")
        password_generated = False

        if not admin_password:
            admin_password = f"HBK-Admin-{secrets.token_hex(4)}!"
            password_generated = True

        existing_admin = db.query(User).filter(User.username == admin_username).first()
        if not existing_admin:
            admin_user = User(
                username=admin_username,
                password_hash=hash_password(admin_password),
                role="admin",
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print(f"[✓] Created Admin User:")
            print(f"    - Username: {admin_username}")
            print(f"    - Password: {admin_password}" + (" (GENERATED - SAVE THIS!)" if password_generated else " (from env)"))
        else:
            admin_user = existing_admin
            print(f"[-] Admin user '{admin_username}' already exists.")

        # 2. Store ISL-01
        store_code = "ISL-01"
        existing_store = db.query(Store).filter(Store.code == store_code).first()
        if not existing_store:
            store = Store(
                code=store_code,
                name="Islamabad Flagship Hypermarket",
                region="North Region",
                created_at=datetime.now(timezone.utc)
            )
            db.add(store)
            db.commit()
            db.refresh(store)
            print(f"[✓] Created Store: {store.code} ({store.name})")
        else:
            store = existing_store
            print(f"[-] Store '{store_code}' already exists.")

        # 3. Store Enrollment Key
        existing_key = db.query(EnrollmentKey).filter(
            EnrollmentKey.store_id == store.id,
            EnrollmentKey.revoked == False
        ).first()

        if not existing_key:
            raw_key = generate_enrollment_key(length=settings.ENROLLMENT_KEY_LENGTH)
            key_hash = hash_secret(raw_key)

            enrollment = EnrollmentKey(
                store_id=store.id,
                key_hash=key_hash,
                created_by=admin_user.id,
                created_at=datetime.now(timezone.utc),
                revoked=False
            )
            db.add(enrollment)
            db.commit()
            db.refresh(enrollment)
            print(f"[✓] Generated Active Enrollment Key: {raw_key}")
        else:
            print(f"[-] Active enrollment key exists for {store.code}.")

        # 4. Seed Default Alert Rules
        print("-" * 65)
        print("[✓] Checking and Seeding Default Alert Rules:")
        for r_spec in DEFAULT_ALERT_RULES:
            rule_exists = db.query(AlertRule).filter(AlertRule.rule_key == r_spec["rule_key"]).first()
            if not rule_exists:
                rule = AlertRule(**r_spec)
                db.add(rule)
                print(f"    + Created rule: {r_spec['rule_key']} ({r_spec['severity']})")
            else:
                print(f"    - Rule exists:  {r_spec['rule_key']}")

        db.commit()
        print("=" * 65)
        print("Seeding complete. Ready to run alert engine & gateway!")
        print("=" * 65)

    finally:
        db.close()

if __name__ == "__main__":
    seed()
