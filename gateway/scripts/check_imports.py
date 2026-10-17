#!/usr/bin/env python3
"""
Validation script for HBK IT Monitoring Gateway.
Verifies that all models, schemas, routers, dependencies, and app.main import cleanly
without missing classes, functions, or circular dependency errors.
"""
import sys
import os

# Ensure gateway root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GATEWAY_DIR = os.path.dirname(SCRIPT_DIR)
if GATEWAY_DIR not in sys.path:
    sys.path.insert(0, GATEWAY_DIR)

def verify_all_imports():
    print("Testing imports for HBK IT Monitoring Gateway...")

    try:
        from app.database import Base, get_db, SessionLocal, engine
        print("✓ app.database imports OK")
    except Exception as e:
        print(f"✗ app.database failed: {e}")
        return False

    try:
        from app.models import (
            User, Store, UserStore, EnrollmentKey, Device, AgentTask,
            FbrCheck, FbrRegistration, PosInvoice, InvoiceFiscalAttempt,
            CcoIntegrationConfig, Metric, AlertRule, Alert, AlertCheck,
            Note, AuditLog, ConnectionEvent, GatewayState, LightMetric
        )
        print("✓ app.models imports OK")
    except Exception as e:
        print(f"✗ app.models failed: {e}")
        return False

    try:
        from app.schemas import (
            UserLogin, UserCreate, UserResponse, UserUpdate, StoreAssign,
            TokenResponse, RefreshRequest, StoreCreate, StoreResponse, StoreUpdate,
            AgentRegisterRequest, AgentRegisterResponse, FbrSummary,
            AgentHeartbeatRequest, AgentGoodbyeRequest, DiskMetric,
            NetworkAdapter, NetworkMetric, PrinterMetric, ServiceMetric,
            MetricSnapshot, AlertRuleResponse, AlertRuleUpdate, AlertResponse,
            AlertAckRequest, AlertResolveResponse, AlertDetailResponse,
            AlertCheckItem, NoteCreate, NoteResponse, AuditLogResponse,
            AgentTaskCreate, AgentTaskResponse, AgentTaskResultRequest,
            HeartbeatTaskItem, ConnectionEventResponse, GatewayStatusResponse,
            DeviceSettingsUpdate, SeriesDataPoint, SeriesResponse,
            FbrRegistrationResponse, FbrRegistrationUpdate,
            PosInvoiceResponse, PosInvoiceRetryRequest,
            InvoiceFiscalAttemptResponse, InvoiceSummaryCounts,
            CcoConfigResponse
        )
        print("✓ app.schemas imports OK")
    except Exception as e:
        print(f"✗ app.schemas failed: {e}")
        return False

    try:
        from app.routers import (
            health, auth, agent, admin, hermes, alerts, dashboard, fbr
        )
        print("✓ app.routers imports OK")
    except Exception as e:
        print(f"✗ app.routers failed: {e}")
        return False

    try:
        from app.main import app
        print("✓ app.main application instance initialized OK")
    except Exception as e:
        print(f"✗ app.main failed: {e}")
        return False

    print("\nIMPORT OK")
    return True

if __name__ == "__main__":
    success = verify_all_imports()
    if not success:
        sys.exit(1)
