export type Role = 'admin' | 'technician' | 'viewer';

export interface User {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  assigned_store_ids?: number[];
}

export interface Store {
  id: number;
  code: string;
  name: string;
  region: string;
  created_at: string;
  devices_total?: number;
  online_count?: number;
  offline_count?: number;
  firing_alerts?: number;
}

export type AgentTaskAction = 'pause' | 'resume' | 'collect_now' | 'fbr_check_now' | 'restart_agent';
export type AgentTaskStatus = 'PENDING' | 'SENT' | 'DONE' | 'FAILED' | 'EXPIRED';

export interface AgentTask {
  id: number;
  device_pk: string;
  action: AgentTaskAction;
  status: AgentTaskStatus;
  requested_by: string;
  requested_at: string;
  sent_at?: string | null;
  finished_at?: string | null;
  result_text?: string | null;
}

export interface Device {
  id: string;
  device_id: string;
  computer_name: string;
  store_id: number;
  store_code: string;
  store_name?: string;
  device_type: 'POS' | 'PC' | 'PRINTER' | 'SERVER';
  ip_address: string;
  os_version: string;
  agent_version: string;
  status: 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'PAUSED';
  agent_state?: 'RUNNING' | 'PAUSED';
  last_seen: string | null;
  registered_at: string;
  active_alerts_count?: number;
  notes_snippet?: string | null;
  local_time?: string | null;
  utc_time?: string | null;
  timezone_name?: string | null;
  utc_offset_minutes?: number | null;
  uptime_sec?: number | null;
  clock_offset_sec?: number | null;
  fbr_status?: string | null;
  fbr_ok?: boolean | null;
  fbr_pos_id?: number | null;
  fbr_pos_identification?: string | null;
  local_ims_status?: string | null;
  fbr_connectivity_status?: 'CONNECTED' | 'DISCONNECTED' | 'LOCAL_SERVICE_DOWN' | 'UNKNOWN' | 'CHECKING' | string | null;
  last_fiscal_sync?: string | null;
  tasks?: AgentTask[];
  fbr?: {
    status: string;
    ok?: boolean | null;
    pos_id?: number | null;
    pos_identification?: string | null;
    local_ims_status?: string | null;
    fbr_connectivity_status?: 'CONNECTED' | 'DISCONNECTED' | 'LOCAL_SERVICE_DOWN' | 'UNKNOWN' | 'CHECKING' | string | null;
    latency_ms?: number | null;
    http_status?: number | null;
    last_check?: string | null;
    last_ok_time?: string | null;
    last_fiscal_sync?: string | null;
    consecutive_failures: number;
    error?: string | null;
  };
  fbr_history?: Array<{
    id: number;
    ts: string;
    ok: boolean;
    latency_ms?: number | null;
    http_status?: number | null;
    error?: string | null;
  }>;
}

export interface FbrRegistration {
  id: number;
  fbr_pos_id: number;
  pos_identification: string;
  branch_name: string;
  store_code?: string | null;
  store_id?: number | null;
  device_pk?: string | null;
  device_id?: string | null;
  portal_status: string;
  connected_date?: string | null;
  code?: string | null;
  pos_software_version?: string | null;
  is_unidentified: boolean;
  token_configured: boolean;
  admin_notes?: string | null;
  created_at: string;
  updated_at: string;
  // Live monitoring fields
  device_status?: 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'PAUSED' | 'UNKNOWN';
  local_ims_status?: string;
  fbr_connectivity_status?: string;
  fbr_last_check?: string | null;
  fbr_last_ok_time?: string | null;
  fbr_latency_ms?: number | null;
  fbr_consecutive_failures?: number;
  fbr_error?: string | null;
  last_fiscal_sync?: string | null;
}

export interface PosInvoice {
  id: number;
  internal_invoice_id: string;
  original_invoice_no: string;
  store_id: number;
  store_code?: string | null;
  store_name?: string | null;
  device_pk: string;
  device_id?: string | null;
  fbr_pos_id?: number | null;
  invoice_datetime: string;
  total_amount?: number | null;
  tax_amount?: number | null;
  currency: string;
  fiscal_status: string;
  fbr_invoice_number?: string | null;
  qr_code?: string | null;
  attempts_count: number;
  last_attempt_at?: string | null;
  last_response_code?: number | null;
  last_response_text?: string | null;
  is_retry_eligible: boolean;
  reconciliation_status: string;
  blocked_reason?: string | null;
  active_retry_task_id?: number | null;
  locked_at?: string | null;
  locked_by?: string | null;
  created_at: string;
}

export interface InvoiceFiscalAttempt {
  id: number;
  invoice_id: number;
  task_id?: number | null;
  attempt_number: number;
  attempt_type: string;
  initiated_by: string;
  initiated_at: string;
  completed_at?: string | null;
  response_code?: number | null;
  response_body_text?: string | null;
  outcome: string;
  fbr_invoice_number?: string | null;
  error_message?: string | null;
}

export interface InvoiceSummaryCounts {
  total: number;
  accepted: number;
  rejected: number;
  pending: number;
  unknown: number;
  reconciliation_required: number;
  safely_retryable: number;
  source_configured: boolean;
  cco_path: string;
}

export interface DiskMetric {
  mount: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  pct: number;
}

export interface NetworkAdapter {
  name: string;
  description?: string | null;
  mac?: string | null;
  ipv4?: string | null;
  ip: string;
  subnet_mask?: string | null;
  default_gateway?: string | null;
  gateway?: string | null;
  dns_servers?: string[] | null;
  dns?: string[] | null;
  dhcp_enabled?: boolean | null;
  link_speed_mbps?: number | null;
  bytes_in?: number;
  bytes_out?: number;
  is_virtual?: boolean;
  is_primary?: boolean;
}

export interface PrinterMetric {
  name: string;
  status: string;
  queue: number;
  port?: string | null;
  is_offline?: boolean;
}

export interface ServiceMetric {
  name: string;
  state: string;
}

export interface MetricSnapshot {
  ts: string;
  cpu_pct: number;
  ram_pct: number;
  ram_used_mb: number;
  disks: DiskMetric[];
  network: {
    adapters: NetworkAdapter[];
    gateway_ping_ms?: number | null;
    dns_ok?: boolean | null;
  };
  internet_ok: boolean;
  printers: PrinterMetric[];
  services: ServiceMetric[];
}

export interface MetricPoint {
  ts: string;
  time_label: string;
  cpu_pct: number;
  ram_pct: number;
  ram_used_mb: number;
  disk_pct?: number | null;
  internet_ok: boolean;
}

export interface Alert {
  id: number;
  device_pk: string;
  device_id?: string;
  store_code?: string;
  rule_key: string;
  severity: 'warning' | 'critical';
  state: 'FIRING' | 'ACKNOWLEDGED' | 'RESOLVED';
  message: string;
  value?: string | null;
  fired_at: string;
  acked_by?: number | null;
  acked_at?: string | null;
  resolved_at?: string | null;
}

export interface Note {
  id: number;
  device_pk: string;
  alert_id?: number | null;
  author_id: number;
  author_username?: string;
  text: string;
  created_at: string;
}

export interface OverviewCounts {
  devices_total: number;
  online: number;
  offline: number;
  degraded: number;
  paused?: number;
  fbr_down?: number;
  firing_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  stores_count: number;
  generated_at: string;
}

export interface AlertRule {
  id: number;
  rule_key: string;
  name: string;
  severity: 'warning' | 'critical';
  threshold_value?: number | null;
  duration_seconds: number;
  enabled: boolean;
  description?: string | null;
}
