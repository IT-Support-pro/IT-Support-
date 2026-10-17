import { 
  OverviewCounts, 
  Store, 
  Device, 
  Alert, 
  Note, 
  User, 
  MetricPoint, 
  AlertRule,
  AgentTask,
  FbrRegistration,
  PosInvoice,
  InvoiceFiscalAttempt,
  InvoiceSummaryCounts
} from './types';

export const getBaseApiUrl = (): string => {
  const custom = localStorage.getItem('hbk_custom_gateway_url');
  if (custom && custom.trim()) {
    return custom.trim().replace(/\/+$/, '');
  }
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  return 'http://localhost:8000';
};

export const setCustomApiUrl = (url: string) => {
  if (url) {
    localStorage.setItem('hbk_custom_gateway_url', url.trim());
  } else {
    localStorage.removeItem('hbk_custom_gateway_url');
  }
};

const TOKEN_KEY = 'hbk_access_token';
const REFRESH_KEY = 'hbk_refresh_token';

export const getAccessToken = () => localStorage.getItem(TOKEN_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY);

export const setAuthTokens = (access: string, refresh: string) => {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
};

export const clearAuthTokens = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
};

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = getBaseApiUrl();
  const url = `${baseUrl}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  const token = getAccessToken();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(url, { ...options, headers });
  } catch (err: any) {
    throw new ApiError(0, `Cannot connect to HBK Gateway at ${baseUrl}. Ensure gateway is running. (${err.message})`);
  }

  // Handle 401: attempt token refresh once
  if (res.status === 401 && !path.includes('/auth/login') && !path.includes('/auth/refresh')) {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken })
        });

        if (refreshRes.ok) {
          const tokenData = await refreshRes.json();
          setAuthTokens(tokenData.access_token, tokenData.refresh_token);
          // Retry original request with new token
          headers['Authorization'] = `Bearer ${tokenData.access_token}`;
          res = await fetch(url, { ...options, headers });
        } else {
          clearAuthTokens();
          throw new ApiError(401, 'Session expired. Please log in again.');
        }
      } catch (e) {
        clearAuthTokens();
        throw new ApiError(401, 'Session expired. Please log in again.');
      }
    } else {
      clearAuthTokens();
      throw new ApiError(401, 'Authentication required.');
    }
  }

  if (!res.ok) {
    let errMsg = `Request failed (${res.status})`;
    let errData = null;
    try {
      errData = await res.json();
      if (errData && errData.detail) {
        errMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch {
      // Not JSON
    }
    throw new ApiError(res.status, errMsg, errData);
  }

  if (res.status === 204) {
    return null as any;
  }

  return res.json();
}

// ----------------- API METHODS -----------------

export const api = {
  // Health
  checkHealth: async () => {
    return request<{ status: string; version: string; service: string }>('/api/v1/health');
  },

  // Auth
  login: async (username: string, password: string) => {
    const data = await request<{ access_token: string; refresh_token: string; token_type: string }>(
      '/api/v1/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ username, password })
      }
    );
    setAuthTokens(data.access_token, data.refresh_token);
    return data;
  },

  getMe: async (): Promise<User> => {
    return request<User>('/api/v1/auth/me');
  },

  logout: () => {
    clearAuthTokens();
  },

  // Overview
  getOverview: async (): Promise<OverviewCounts> => {
    return request<OverviewCounts>('/api/v1/overview');
  },

  // Stores
  getStores: async (): Promise<Store[]> => {
    return request<Store[]>('/api/v1/stores');
  },

  // Devices
  getDevices: async (filters: {
    store?: string;
    status?: string;
    type?: string;
    search?: string;
    limit?: number;
  } = {}): Promise<Device[]> => {
    const params = new URLSearchParams();
    if (filters.store) params.append('store', filters.store);
    if (filters.status) params.append('status', filters.status);
    if (filters.type) params.append('type', filters.type);
    if (filters.search) params.append('search', filters.search);
    if (filters.limit) params.append('limit', String(filters.limit));

    const qs = params.toString();
    return request<Device[]>(`/api/v1/devices${qs ? `?${qs}` : ''}`);
  },

  getDeviceDetail: async (deviceId: string): Promise<any> => {
    return request<any>(`/api/v1/devices/${encodeURIComponent(deviceId)}`);
  },

  getDeviceMetrics: async (deviceId: string, minutes: number = 60): Promise<{
    device_id: string;
    window_minutes: number;
    points_count: number;
    series: MetricPoint[];
  }> => {
    return request(`/api/v1/devices/${encodeURIComponent(deviceId)}/metrics?minutes=${minutes}`);
  },

  getDeviceNotes: async (deviceId: string): Promise<Note[]> => {
    return request<Note[]>(`/api/v1/devices/${encodeURIComponent(deviceId)}/notes`);
  },

  addDeviceNote: async (deviceId: string, text: string, alertId?: number | null): Promise<Note> => {
    return request<Note>(`/api/v1/devices/${encodeURIComponent(deviceId)}/notes`, {
      method: 'POST',
      body: JSON.stringify({ text, alert_id: alertId || null })
    });
  },

  // Remote Control Tasks
  getDeviceTasks: async (deviceId: string): Promise<AgentTask[]> => {
    return request<AgentTask[]>(`/api/v1/devices/${encodeURIComponent(deviceId)}/tasks`);
  },

  sendDeviceTask: async (deviceId: string, action: string): Promise<AgentTask> => {
    return request<AgentTask>(`/api/v1/devices/${encodeURIComponent(deviceId)}/tasks`, {
      method: 'POST',
      body: JSON.stringify({ action })
    });
  },

  // Alerts
  getAlerts: async (filters: {
    state?: string;
    severity?: string;
    store?: string;
    device?: string;
  } = {}): Promise<Alert[]> => {
    const params = new URLSearchParams();
    if (filters.state) params.append('state', filters.state);
    if (filters.severity) params.append('severity', filters.severity);
    if (filters.store) params.append('store', filters.store);
    if (filters.device) params.append('device', filters.device);

    const qs = params.toString();
    return request<Alert[]>(`/api/v1/alerts${qs ? `?${qs}` : ''}`);
  },

  ackAlert: async (alertId: number): Promise<Alert> => {
    return request<Alert>(`/api/v1/alerts/${alertId}/ack`, { method: 'POST' });
  },

  resolveAlert: async (alertId: number): Promise<Alert> => {
    return request<Alert>(`/api/v1/alerts/${alertId}/resolve`, { method: 'POST' });
  },

  // Admin APIs
  createEnrollmentKey: async (storeId: number): Promise<{
    enrollment_key: string;
    store_id: number;
    created_at: string;
    revoked: boolean;
  }> => {
    return request(`/api/v1/admin/stores/${storeId}/enrollment-key`, { method: 'POST' });
  },

  getUsers: async (): Promise<User[]> => {
    return request<User[]>('/api/v1/admin/users');
  },

  createUser: async (payload: { username: string; password: string; role: string }): Promise<User> => {
    return request<User>('/api/v1/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  assignUserStores: async (userId: number, storeIds: number[]): Promise<User> => {
    return request<User>(`/api/v1/admin/users/${userId}/assign-stores`, {
      method: 'POST',
      body: JSON.stringify({ store_ids: storeIds })
    });
  },

  getAlertRules: async (): Promise<AlertRule[]> => {
    return request<AlertRule[]>('/api/v1/alert-rules');
  },

  updateAlertRule: async (ruleKey: string, payload: Partial<AlertRule>): Promise<AlertRule> => {
    return request<AlertRule>(`/api/v1/alert-rules/${encodeURIComponent(ruleKey)}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  // FBR Registrations & Live Monitoring
  getFbrRegistrations: async (filters: {
    branch?: string;
    store_id?: number;
    unmapped?: boolean;
    unidentified?: boolean;
    search?: string;
  } = {}): Promise<FbrRegistration[]> => {
    const params = new URLSearchParams();
    if (filters.branch) params.append('branch', filters.branch);
    if (filters.store_id) params.append('store_id', String(filters.store_id));
    if (filters.unmapped !== undefined) params.append('unmapped', String(filters.unmapped));
    if (filters.unidentified !== undefined) params.append('unidentified', String(filters.unidentified));
    if (filters.search) params.append('search', filters.search);

    const qs = params.toString();
    return request<FbrRegistration[]>(`/api/v1/fbr/registrations${qs ? `?${qs}` : ''}`);
  },

  updateFbrRegistration: async (
    registrationId: number, 
    payload: { device_pk?: string | null; store_id?: number | null; admin_notes?: string | null }
  ): Promise<any> => {
    return request(`/api/v1/fbr/registrations/${registrationId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  },

  checkFbrNow: async (registrationId: number): Promise<{ message: string; task_id?: number; status: string }> => {
    return request(`/api/v1/fbr/registrations/${registrationId}/check-now`, {
      method: 'POST'
    });
  },

  // POS Invoices & Safe Fiscalization Recovery
  getInvoiceSummary: async (storeId?: number): Promise<InvoiceSummaryCounts> => {
    const qs = storeId ? `?store_id=${storeId}` : '';
    return request<InvoiceSummaryCounts>(`/api/v1/fbr/invoices/summary${qs}`);
  },

  getPosInvoices: async (filters: {
    store_id?: number;
    device_id?: string;
    status?: string;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<PosInvoice[]> => {
    const params = new URLSearchParams();
    if (filters.store_id) params.append('store_id', String(filters.store_id));
    if (filters.device_id) params.append('device_id', filters.device_id);
    if (filters.status) params.append('status', filters.status);
    if (filters.search) params.append('search', filters.search);
    if (filters.limit) params.append('limit', String(filters.limit));
    if (filters.offset) params.append('offset', String(filters.offset));

    const qs = params.toString();
    return request<PosInvoice[]>(`/api/v1/fbr/invoices${qs ? `?${qs}` : ''}`);
  },

  getInvoiceDetail: async (invoiceId: number): Promise<{ invoice: PosInvoice; attempts: InvoiceFiscalAttempt[] }> => {
    return request(`/api/v1/fbr/invoices/${invoiceId}`);
  },

  retryInvoiceFiscalization: async (invoiceId: number, reason: string): Promise<any> => {
    return request(`/api/v1/fbr/invoices/${invoiceId}/retry`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  },

  reconcileInvoice: async (
    invoiceId: number, 
    payload: { status: string; fbr_invoice_number?: string; notes: string }
  ): Promise<any> => {
    return request(`/api/v1/fbr/invoices/${invoiceId}/reconcile`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }
};
