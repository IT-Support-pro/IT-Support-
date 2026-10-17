import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Index,
    JSON
)
from sqlalchemy.orm import relationship
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer") # admin | technician | viewer
    is_active = Column(Boolean, default=True, nullable=False)
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    assigned_stores = relationship("UserStore", back_populates="user", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="author")

class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), unique=True, index=True, nullable=False) # e.g. "ISL-01"
    name = Column(String(150), nullable=False)
    region = Column(String(100), nullable=False)
    expected_timezone = Column(String(100), nullable=True, default="Pakistan Standard Time")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    users = relationship("UserStore", back_populates="store", cascade="all, delete-orphan")
    enrollment_keys = relationship("EnrollmentKey", back_populates="store", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="store")
    fbr_registrations = relationship("FbrRegistration", back_populates="store")
    invoices = relationship("PosInvoice", back_populates="store")

class UserStore(Base):
    __tablename__ = "user_stores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)

    user = relationship("User", back_populates="assigned_stores")
    store = relationship("Store", back_populates="users")

    __table_args__ = (
        Index("ix_user_stores_user_store", "user_id", "store_id", unique=True),
    )

class EnrollmentKey(Base):
    __tablename__ = "enrollment_keys"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    store = relationship("Store", back_populates="enrollment_keys")

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())) # UUID string
    device_id = Column(String(100), unique=True, index=True, nullable=False) # e.g. "POS-12"
    computer_name = Column(String(150), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True)
    device_type = Column(String(30), nullable=False, default="POS") # POS | PC | PRINTER | SERVER
    ip_address = Column(String(45), nullable=False)
    os_version = Column(String(150), nullable=False)
    agent_version = Column(String(50), nullable=False)
    token_hash = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="ONLINE") # ONLINE | OFFLINE | DEGRADED | PAUSED | STOPPED | RECOVERING
    last_seen = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    registered_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    notes = Column(Text, nullable=True)

    # POS Date, Time & Uptime
    local_time = Column(String(50), nullable=True) # ISO 8601 with offset
    utc_time = Column(DateTime(timezone=True), nullable=True)
    timezone_name = Column(String(100), nullable=True) # e.g. "Pakistan Standard Time"
    utc_offset_minutes = Column(Integer, nullable=True)
    uptime_sec = Column(Float, nullable=True)
    clock_offset_sec = Column(Float, nullable=True) # agent utc_time minus gateway UTC receipt time
    clock_raw_json = Column(JSON, nullable=True) # {agent_local_time, agent_utc_time, gateway_received_utc, offset_sec, timezone_name}

    # Configuration overrides
    expected_timezone = Column(String(100), nullable=True) # Overrides store/global
    muted_rules_json = Column(JSON, nullable=True) # [{rule_key, until, reason}]

    # Connection Reliability & Offline Reason
    connection_status = Column(String(20), default="ONLINE", nullable=False) # ONLINE | OFFLINE | PAUSED | STOPPED | RECOVERING
    offline_reason_code = Column(String(50), nullable=True)
    offline_reason_text = Column(Text, nullable=True)
    offline_since = Column(DateTime(timezone=True), nullable=True)
    consecutive_heartbeats_ok = Column(Integer, default=0, nullable=False)
    reading_stale = Column(Boolean, default=False, nullable=False)
    w32time_running = Column(Boolean, nullable=True)

    # FBR Fiscal Connectivity & Registration State
    fbr_status = Column(String(50), nullable=True, default="NOT_CONFIGURED") # OK | DOWN | NOT_CONFIGURED
    fbr_ok = Column(Boolean, nullable=True)
    fbr_latency_ms = Column(Float, nullable=True)
    fbr_http_status = Column(Integer, nullable=True)
    fbr_last_check = Column(DateTime(timezone=True), nullable=True)
    fbr_last_ok_time = Column(DateTime(timezone=True), nullable=True)
    fbr_consecutive_failures = Column(Integer, default=0, nullable=False)
    fbr_error = Column(String(255), nullable=True)
    
    # Real per-POS FBR & Local PRAL/IMS separation
    fbr_pos_id = Column(Integer, nullable=True, index=True) # e.g. 149121
    fbr_pos_identification = Column(String(100), nullable=True) # e.g. "HYT-POS01"
    local_ims_status = Column(String(50), default="UNKNOWN", nullable=False) # RUNNING | DOWN | UNKNOWN
    fbr_connectivity_status = Column(String(50), default="UNKNOWN", nullable=False) # CONNECTED | DISCONNECTED | LOCAL_SERVICE_DOWN | UNKNOWN | CHECKING
    last_fiscal_sync = Column(DateTime(timezone=True), nullable=True)

    # Network topology details
    network_details_json = Column(JSON, nullable=True)

    # Remote Agent Control & Capabilities
    agent_state = Column(String(20), default="RUNNING", nullable=False) # RUNNING | PAUSED | STOPPED
    capabilities_json = Column(JSON, nullable=True)
    last_error_text = Column(Text, nullable=True)

    store = relationship("Store", back_populates="devices")
    metrics = relationship("Metric", back_populates="device", cascade="all, delete-orphan")
    light_metrics = relationship("LightMetric", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    device_notes = relationship("Note", back_populates="device", cascade="all, delete-orphan")
    fbr_checks = relationship("FbrCheck", back_populates="device", cascade="all, delete-orphan")
    tasks = relationship("AgentTask", back_populates="device", cascade="all, delete-orphan")
    fbr_registration = relationship("FbrRegistration", back_populates="device", uselist=False)
    invoices = relationship("PosInvoice", back_populates="device", cascade="all, delete-orphan")
    connection_events = relationship("ConnectionEvent", back_populates="device", cascade="all, delete-orphan")

class ConnectionEvent(Base):
    __tablename__ = "connection_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    type = Column(String(30), nullable=False, index=True) # ONLINE, OFFLINE, RECONNECTED, PAUSED, RESUMED, STOPPED, RESTARTED, AGENT_UPDATED, GATEWAY_DOWN, CLOCK_CHANGE
    reason_code = Column(String(50), nullable=True)
    reason_text = Column(Text, nullable=True)
    duration_sec = Column(Float, nullable=True)
    details_json = Column(JSON, nullable=True)

    device = relationship("Device", back_populates="connection_events")

    __table_args__ = (
        Index("ix_connection_events_device_ts", "device_pk", "ts"),
    )

class GatewayState(Base):
    __tablename__ = "gateway_state"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    last_alive = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at_utc = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    version = Column(String(50), default="1.1.0", nullable=False)

class LightMetric(Base):
    __tablename__ = "light_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    cpu_pct = Column(Float, nullable=False)
    ram_pct = Column(Float, nullable=False)
    system_disk_pct = Column(Float, nullable=True)
    internet_ok = Column(Boolean, default=True, nullable=False)

    device = relationship("Device", back_populates="light_metrics")

    __table_args__ = (
        Index("ix_light_metrics_device_ts", "device_pk", "ts"),
    )

class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(50), nullable=False) # pause | resume | collect_now | fbr_check_now | restart_agent | stop_agent | recheck
    status = Column(String(20), nullable=False, default="PENDING", index=True) # PENDING | SENT | RUNNING | DONE | FAILED | EXPIRED
    requested_by = Column(String(100), nullable=False)
    requested_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    result_text = Column(Text, nullable=True)

    device = relationship("Device", back_populates="tasks")

class FbrCheck(Base):
    __tablename__ = "fbr_checks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    ok = Column(Boolean, nullable=False)
    latency_ms = Column(Float, nullable=True)
    http_status = Column(Integer, nullable=True)
    error = Column(String(255), nullable=True)

    device = relationship("Device", back_populates="fbr_checks")

class FbrRegistration(Base):
    __tablename__ = "fbr_registrations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fbr_pos_id = Column(Integer, unique=True, index=True, nullable=False)
    pos_identification = Column(String(100), nullable=False, index=True)
    branch_name = Column(String(150), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)

    portal_status = Column(String(50), default="Connected", nullable=False)
    connected_date = Column(String(50), nullable=True)
    code = Column(String(50), nullable=True)
    pos_software_version = Column(String(50), nullable=True)
    
    is_unidentified = Column(Boolean, default=False, nullable=False)
    token_configured = Column(Boolean, default=False, nullable=False)
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    store = relationship("Store", back_populates="fbr_registrations")
    device = relationship("Device", back_populates="fbr_registration")

class PosInvoice(Base):
    __tablename__ = "pos_invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    internal_invoice_id = Column(String(100), unique=True, index=True, nullable=False)
    original_invoice_no = Column(String(100), unique=True, index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False, index=True)
    fbr_pos_id = Column(Integer, nullable=True, index=True)
    invoice_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    total_amount = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    currency = Column(String(10), default="PKR", nullable=False)
    fiscal_status = Column(String(40), default="PENDING", nullable=False, index=True) # ACCEPTED | REJECTED | PENDING | UNKNOWN | RECONCILIATION_REQUIRED | RETRYABLE
    fbr_invoice_number = Column(String(100), nullable=True, index=True)
    qr_code = Column(Text, nullable=True)
    attempts_count = Column(Integer, default=0, nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_response_code = Column(Integer, nullable=True)
    last_response_text = Column(Text, nullable=True)
    is_retry_eligible = Column(Boolean, default=False, nullable=False)
    reconciliation_status = Column(String(50), default="NOT_RECONCILED", nullable=False)
    blocked_reason = Column(String(255), nullable=True)
    active_retry_task_id = Column(Integer, nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    store = relationship("Store", back_populates="invoices")
    device = relationship("Device", back_populates="invoices")
    attempts = relationship("InvoiceFiscalAttempt", back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceFiscalAttempt.attempt_number.desc()")

    __table_args__ = (
        Index("ix_pos_invoices_store_status", "store_id", "fiscal_status"),
        Index("ix_pos_invoices_datetime", "invoice_datetime"),
    )

class InvoiceFiscalAttempt(Base):
    __tablename__ = "invoice_fiscal_attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("pos_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, nullable=True)
    attempt_number = Column(Integer, nullable=False)
    attempt_type = Column(String(30), default="MANUAL_RETRY", nullable=False) # INITIAL | MANUAL_RETRY | RECONCILIATION
    initiated_by = Column(String(100), nullable=False)
    initiated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    request_payload_json = Column(JSON, nullable=True)
    response_code = Column(Integer, nullable=True)
    response_body_text = Column(Text, nullable=True)
    outcome = Column(String(40), nullable=False) # IN_FLIGHT | ACCEPTED | REJECTED | TIMEOUT | AMBIGUOUS
    fbr_invoice_number = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    invoice = relationship("PosInvoice", back_populates="attempts")

class CcoIntegrationConfig(Base):
    __tablename__ = "cco_integration_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, unique=True)
    cco_install_path = Column(String(255), default=r"C:\SapCustomerCheckout\cco", nullable=False)
    cco_derby_path = Column(String(255), default=r"C:\SapCustomerCheckout\cco\db\CCO", nullable=False)
    export_folder = Column(String(255), nullable=True)
    status = Column(String(50), default="INVOICE SOURCE NOT CONFIGURED", nullable=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_count = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)

class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    cpu_pct = Column(Float, nullable=False)
    ram_pct = Column(Float, nullable=False)
    ram_used_mb = Column(Float, nullable=False)
    disk_json = Column(JSON, nullable=False)
    net_json = Column(JSON, nullable=False)
    internet_ok = Column(Boolean, default=True, nullable=False)
    printers_json = Column(JSON, nullable=True)
    services_json = Column(JSON, nullable=True)

    device = relationship("Device", back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_device_ts", "device_pk", "ts"),
    )

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rule_key = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False)
    severity = Column(String(20), nullable=False, default="warning") # warning | critical
    threshold_value = Column(Float, nullable=True)
    duration_seconds = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    description = Column(String(255), nullable=True)

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_key = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False) # warning | critical
    state = Column(String(20), nullable=False, default="FIRING") # FIRING | ACKNOWLEDGED | RESOLVED
    message = Column(Text, nullable=False)
    value = Column(String(100), nullable=True)
    fired_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    acked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acked_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution = Column(String(30), nullable=True) # VERIFIED_FIXED | AUTO_CLEARED
    resolved_by = Column(String(100), nullable=True)

    device = relationship("Device", back_populates="alerts")
    notes = relationship("Note", back_populates="alert")
    checks = relationship("AlertCheck", back_populates="alert", cascade="all, delete-orphan", order_by="AlertCheck.ts.desc()")

class AlertCheck(Base):
    __tablename__ = "alert_checks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    by = Column(String(100), nullable=False)
    result = Column(String(30), nullable=False) # FIXED | NOT_RESOLVED | CANNOT_VERIFY
    observed_value = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)

    alert = relationship("Alert", back_populates="checks")

class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_pk = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    device = relationship("Device", back_populates="device_notes")
    alert = relationship("Alert", back_populates="notes")
    author = relationship("User", back_populates="notes")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    actor_type = Column(String(20), nullable=False) # user | agent | hermes
    actor = Column(String(150), nullable=False) # username, device_id, or "hermes"
    action = Column(String(100), nullable=False) # login, register, token_revoke, alert_ack, etc.
    target = Column(String(150), nullable=True)
    ip = Column(String(45), nullable=True)
    detail_json = Column(JSON, nullable=True)
