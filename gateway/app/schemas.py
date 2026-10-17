from datetime import datetime
from typing import List, Optional, Union, Any, Dict
from pydantic import BaseModel, Field, ConfigDict, field_validator

# ----------------- AUTH & USER SCHEMAS -----------------

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = Field(default="viewer", pattern="^(admin|technician|viewer)$")

    @field_validator("password")
    @classmethod
    def validate_password_len(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Password must be at least 10 characters long")
        return v

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    assigned_store_ids: Optional[List[int]] = []

class UserUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern="^(admin|technician|viewer)$")
    is_active: Optional[bool] = None
    password: Optional[str] = None

class StoreAssign(BaseModel):
    store_ids: List[int]

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

# ----------------- STORE SCHEMAS -----------------

class StoreCreate(BaseModel):
    code: str
    name: str
    region: str
    expected_timezone: Optional[str] = "Pakistan Standard Time"

class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    region: str
    expected_timezone: Optional[str] = "Pakistan Standard Time"
    created_at: datetime

class StoreUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    expected_timezone: Optional[str] = None

# ----------------- AGENT INGESTION SCHEMAS -----------------

class AgentRegisterRequest(BaseModel):
    enrollment_key: str
    device_id: str
    computer_name: str
    device_type: str = Field(default="POS", pattern="^(POS|PC|PRINTER|SERVER)$")
    ip_address: str
    os_version: str
    agent_version: str

class AgentRegisterResponse(BaseModel):
    device_token: str
    device_id: str
    store_code: str
    registered_at: datetime

class FbrSummary(BaseModel):
    fbr_status: str = "NOT_CONFIGURED" # OK | DOWN | NOT_CONFIGURED
    fbr_ok: Optional[bool] = None
    latency_ms: Optional[float] = None
    http_status: Optional[int] = None
    last_ok_time: Optional[str] = None
    last_check_time: Optional[str] = None
    consecutive_failures: int = 0
    error_text: Optional[str] = None
    record_history: bool = False
    
    # Separation of Local IMS health and real FBR reachability
    local_ims_ok: Optional[bool] = None
    local_ims_status: Optional[str] = "UNKNOWN" # RUNNING | DOWN | UNKNOWN
    fbr_connectivity_status: Optional[str] = "UNKNOWN" # CONNECTED | DISCONNECTED | LOCAL_SERVICE_DOWN | UNKNOWN | CHECKING
    last_fiscal_sync: Optional[str] = None

class OutageSummary(BaseModel):
    from_utc: Optional[str] = None
    to_utc: Optional[str] = None
    duration_sec: Optional[float] = None
    reason_code: Optional[str] = None
    detail: Optional[str] = None
    failed_attempts: Optional[int] = 0
    buffered_readings: Optional[int] = 0

class AgentInfo(BaseModel):
    agent_version: str
    capabilities: List[str] = []
    agent_state: Optional[str] = "RUNNING"
    process_uptime_sec: Optional[float] = None
    last_error: Optional[str] = None
    heartbeats_ok: Optional[int] = 0
    heartbeats_failed: Optional[int] = 0

class AgentHeartbeatRequest(BaseModel):
    agent_version: str
    ip_address: str
    local_time: Optional[str] = None
    utc_time: Optional[datetime] = None
    timezone_name: Optional[str] = None
    utc_offset_minutes: Optional[int] = None
    uptime_sec: Optional[float] = None
    fbr: Optional[FbrSummary] = None
    agent_state: Optional[str] = "RUNNING"

    # Light sample in heartbeat for real-time 1-min gauges & charts
    cpu_pct: Optional[float] = None
    ram_pct: Optional[float] = None
    system_disk_pct: Optional[float] = None
    internet_ok: Optional[bool] = None

    # Reliability and status tracking
    agent_info: Optional[AgentInfo] = None
    outage: Optional[OutageSummary] = None
    previous_exit: Optional[str] = None # CLEAN | UNCLEAN
    w32time_running: Optional[bool] = None

class AgentGoodbyeRequest(BaseModel):
    reason_code: str # SERVICE_STOPPED | SYSTEM_SHUTDOWN | ADMIN_STOP | RESTART_REQUESTED | CONSOLE_EXIT | UPDATE
    detail: Optional[str] = None

class DiskMetric(BaseModel):
    mount: str
    total_gb: float
    used_gb: float
    free_gb: float
    pct: float

class NetworkAdapter(BaseModel):
    name: str
    description: Optional[str] = None
    mac: Optional[str] = None
    ipv4: Optional[str] = None
    ip: Optional[str] = None
    subnet_mask: Optional[str] = None
    default_gateway: Optional[str] = None
    gateway: Optional[str] = None
    dns_servers: Optional[List[str]] = None
    dns: Optional[List[str]] = None
    dhcp_enabled: Optional[bool] = True
    link_speed_mbps: Optional[int] = 1000
    bytes_in: Optional[int] = 0
    bytes_out: Optional[int] = 0
    is_virtual: Optional[bool] = False
    is_primary: Optional[bool] = False

class NetworkMetric(BaseModel):
    adapters: List[NetworkAdapter] = []
    default_gateway: Optional[str] = None
    gateway_ping_ms: Optional[float] = None
    gateway_icmp: Optional[str] = None # OK | NO_REPLY
    dns_ok: Optional[bool] = None
    dns_latency_ms: Optional[float] = None
    dns_server_used: Optional[str] = None
    gateway_tcp_ok: Optional[bool] = None
    gateway_tcp_latency_ms: Optional[float] = None
    internet_latency_ms: Optional[float] = None
    internet_fail_reason: Optional[str] = None

class PrinterMetric(BaseModel):
    name: str
    status: str
    queue: int = 0
    port: Optional[str] = None
    is_offline: Optional[bool] = False
    copies_count: Optional[int] = 1

class ServiceMetric(BaseModel):
    name: str
    state: str

class MetricSnapshot(BaseModel):
    ts: datetime
    cpu_pct: float
    ram_pct: float
    ram_used_mb: float
    disks: List[DiskMetric] = []
    network: NetworkMetric = Field(default_factory=NetworkMetric)
    internet_ok: bool = True
    printers: Optional[List[PrinterMetric]] = []
    services: Optional[List[ServiceMetric]] = []
    local_time: Optional[str] = None
    utc_time: Optional[datetime] = None
    timezone_name: Optional[str] = None
    utc_offset_minutes: Optional[int] = None
    uptime_sec: Optional[float] = None
    fbr: Optional[FbrSummary] = None
    collector_errors: Optional[List[str]] = None

# ----------------- ALERT ENGINE SCHEMAS -----------------

class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rule_key: str
    name: str
    severity: str
    threshold_value: Optional[float] = None
    duration_seconds: int
    enabled: bool
    description: Optional[str] = None

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    severity: Optional[str] = Field(None, pattern="^(warning|critical)$")
    threshold_value: Optional[float] = None
    duration_seconds: Optional[int] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None

class AlertCheckItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_id: int
    ts: datetime
    by: str
    result: str # FIXED | NOT_RESOLVED | CANNOT_VERIFY
    observed_value: Optional[str] = None
    message: str

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_pk: str
    device_id: Optional[str] = None
    store_code: Optional[str] = None
    rule_key: str
    rule_name: Optional[str] = None
    severity: str
    state: str
    message: str
    value: Optional[str] = None
    fired_at: datetime
    acked_by: Optional[int] = None
    acked_by_name: Optional[str] = None
    acked_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None # VERIFIED_FIXED | AUTO_CLEARED
    resolved_by: Optional[str] = None

class AlertAckRequest(BaseModel):
    note: Optional[str] = None

class AlertResolveResponse(BaseModel):
    result: str # FIXED | NOT_RESOLVED | CANNOT_VERIFY
    message: str
    current_value: Optional[str] = None
    checked_at: Optional[datetime] = None
    alert: Optional[AlertResponse] = None

class AlertDetailResponse(BaseModel):
    alert: AlertResponse
    explanation: str
    error_details: Dict[str, Any]
    current_value: Optional[str] = None
    threshold: Optional[str] = None
    how_to_fix: List[str]
    timeline: List[Dict[str, Any]]
    checks: List[AlertCheckItem] = []
    related_events: List[Dict[str, Any]] = []

# ----------------- NOTE SCHEMAS -----------------

class NoteCreate(BaseModel):
    text: str
    alert_id: Optional[int] = None

class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_pk: str
    alert_id: Optional[int] = None
    author_id: int
    author_username: Optional[str] = None
    text: str
    created_at: datetime

# ----------------- AUDIT LOG SCHEMA -----------------

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    actor_type: str
    actor: str
    action: str
    target: Optional[str] = None
    ip: Optional[str] = None
    detail_json: Optional[Any] = None

# ----------------- AGENT TASK SCHEMAS -----------------

ALLOWED_AGENT_ACTIONS = {
    "pause", "resume", "collect_now", "fbr_check_now", 
    "restart_agent", "stop_agent", "recheck", "retry_invoice", "check_invoices"
}

class AgentTaskCreate(BaseModel):
    action: str
    rule_key: Optional[str] = None # For recheck action
    confirm_device_id: Optional[str] = None # Required for stop_agent

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        act = v.strip().lower()
        if act not in ALLOWED_AGENT_ACTIONS:
            raise ValueError(f"Action '{v}' not allowed. Must be one of: {', '.join(sorted(ALLOWED_AGENT_ACTIONS))}")
        return act

class AgentTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_pk: str
    action: str
    status: str
    requested_by: str
    requested_at: datetime
    sent_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result_text: Optional[str] = None

class AgentTaskResultRequest(BaseModel):
    status: str = Field(pattern="^(DONE|FAILED)$")
    result_text: Optional[str] = None

class HeartbeatTaskItem(BaseModel):
    id: int
    action: str
    rule_key: Optional[str] = None

# ----------------- CONNECTION EVENTS & GATEWAY STATUS -----------------

class ConnectionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_pk: str
    device_id: Optional[str] = None
    store_code: Optional[str] = None
    ts: datetime
    type: str # ONLINE, OFFLINE, RECONNECTED, PAUSED, RESUMED, STOPPED, RESTARTED, AGENT_UPDATED, GATEWAY_DOWN, CLOCK_CHANGE
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None
    duration_sec: Optional[float] = None
    details_json: Optional[Dict[str, Any]] = None

class GatewayStatusResponse(BaseModel):
    started_at_utc: datetime
    uptime_sec: float
    version: str
    last_downtime_event: Optional[Dict[str, Any]] = None
    device_counts: Dict[str, int]
    public_gateway_url: Optional[str] = None

class DeviceSettingsUpdate(BaseModel):
    expected_timezone: Optional[str] = None
    muted_rules: Optional[List[Dict[str, Any]]] = None # [{rule_key, until, reason}]

# ----------------- SERIES FOR CHARTS -----------------

class SeriesDataPoint(BaseModel):
    ts: str # UTC ISO timestamp
    value: Optional[float] # null where device was offline (no interpolation)

class SeriesResponse(BaseModel):
    device_id: str
    metric: str
    range: str
    points: List[SeriesDataPoint]

# ----------------- FBR REGISTRATION SCHEMAS -----------------

class FbrRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fbr_pos_id: int
    pos_identification: str
    branch_name: str
    store_code: Optional[str] = None
    store_id: Optional[int] = None
    device_pk: Optional[str] = None
    device_id: Optional[str] = None
    portal_status: str
    connected_date: Optional[str] = None
    code: Optional[str] = None
    pos_software_version: Optional[str] = None
    is_unidentified: bool
    token_configured: bool
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class FbrRegistrationUpdate(BaseModel):
    device_pk: Optional[str] = None
    store_id: Optional[int] = None
    admin_notes: Optional[str] = None

# ----------------- POS INVOICE & SAFE RETRY SCHEMAS -----------------

class PosInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    internal_invoice_id: str
    original_invoice_no: str
    store_id: int
    store_code: Optional[str] = None
    device_pk: str
    device_id: Optional[str] = None
    fbr_pos_id: Optional[int] = None
    invoice_datetime: datetime
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    currency: str
    fiscal_status: str
    fbr_invoice_number: Optional[str] = None
    qr_code: Optional[str] = None
    attempts_count: int
    last_attempt_at: Optional[datetime] = None
    last_response_code: Optional[int] = None
    last_response_text: Optional[str] = None
    is_retry_eligible: bool
    reconciliation_status: str
    blocked_reason: Optional[str] = None
    active_retry_task_id: Optional[int] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    created_at: datetime

class PosInvoiceRetryRequest(BaseModel):
    reason: str
    reconciled_outcome: Optional[str] = None

class InvoiceFiscalAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_id: int
    task_id: Optional[int] = None
    attempt_number: int
    attempt_type: str
    initiated_by: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    response_code: Optional[int] = None
    response_body_text: Optional[str] = None
    outcome: str
    fbr_invoice_number: Optional[str] = None
    error_message: Optional[str] = None

class InvoiceSummaryCounts(BaseModel):
    total: int
    accepted: int
    rejected: int
    pending: int
    unknown: int
    reconciliation_required: int
    safely_retryable: int
    source_configured: bool
    cco_path: str

class CcoConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    store_id: int
    cco_install_path: str
    cco_derby_path: str
    export_folder: Optional[str] = None
    status: str
    last_sync_at: Optional[datetime] = None
    last_sync_count: int
    notes: Optional[str] = None
