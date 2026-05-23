const BASE = import.meta.env.VITE_API_URL ?? "";

let _token: string | null = localStorage.getItem("gh_token");

export function setToken(t: string) {
  _token = t;
  localStorage.setItem("gh_token", t);
}

export function clearToken() {
  _token = null;
  localStorage.removeItem("gh_token");
}

export function hasToken() {
  return Boolean(_token);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "API error");
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export const api = {
  setup: {
    status: () => request<SetupStatus>("/api/setup/status"),
    setPassword: (password: string) =>
      request<{ access_token: string }>("/api/setup/password", {
        method: "POST",
        body: JSON.stringify({ password }),
      }),
    setNetworkName: (name: string) =>
      request("/api/setup/network", { method: "POST", body: JSON.stringify({ network_name: name }) }),
    bulkAddChildren: (children: WizardChild[]) =>
      request("/api/setup/children/bulk", { method: "POST", body: JSON.stringify(children) }),
    complete: () => request("/api/setup/complete", { method: "POST" }),
  },

  auth: {
    login: (password: string) =>
      request<{ access_token: string }>("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `username=parent&password=${encodeURIComponent(password)}`,
      }),
  },

  children: {
    list: () => request<Child[]>("/api/children"),
    get: (id: number) => request<Child>(`/api/children/${id}`),
    create: (data: Partial<Child>) =>
      request<Child>("/api/children", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<Child>) =>
      request<Child>(`/api/children/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: number) => request(`/api/children/${id}`, { method: "DELETE" }),
    getCategories: (id: number) => request<Record<string, boolean>>(`/api/children/${id}/categories`),
    setCategory: (id: number, category: string, blocked: boolean) =>
      request(`/api/children/${id}/categories?category=${encodeURIComponent(category)}&blocked=${blocked}`, {
        method: "PUT",
      }),
  },

  devices: {
    list: () => request<Device[]>("/api/devices"),
    scan: () => request<{ scanned: number; devices: Device[] }>("/api/devices/scan"),
    assign: (id: number, child_id: number | null, label?: string) =>
      request<Device>(`/api/devices/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ child_id, label }),
      }),
    pause: (id: number) => request(`/api/devices/${id}/pause`, { method: "POST" }),
    resume: (id: number) => request(`/api/devices/${id}/resume`, { method: "POST" }),
  },

  rules: {
    getSchedules: (childId: number) => request<Schedule[]>(`/api/rules/${childId}/schedules`),
    createSchedule: (childId: number, data: Partial<Schedule>) =>
      request<Schedule>(`/api/rules/${childId}/schedules`, { method: "POST", body: JSON.stringify(data) }),
    deleteSchedule: (childId: number, scheduleId: number) =>
      request(`/api/rules/${childId}/schedules/${scheduleId}`, { method: "DELETE" }),
    getExceptions: (childId: number) => request<AllowException[]>(`/api/rules/${childId}/exceptions`),
    addException: (childId: number, domain: string, label?: string) =>
      request<AllowException>(`/api/rules/${childId}/exceptions`, {
        method: "POST",
        body: JSON.stringify({ domain, label }),
      }),
    removeException: (childId: number, exceptionId: number) =>
      request(`/api/rules/${childId}/exceptions/${exceptionId}`, { method: "DELETE" }),
  },

  reports: {
    log: (params?: { child_id?: number; blocked_only?: boolean; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.child_id) qs.set("child_id", String(params.child_id));
      if (params?.blocked_only) qs.set("blocked_only", "true");
      if (params?.limit) qs.set("limit", String(params.limit));
      return request<DnsLogEntry[]>(`/api/reports/log?${qs}`);
    },
    summary: (child_id?: number, days = 7) => {
      const qs = new URLSearchParams({ days: String(days) });
      if (child_id) qs.set("child_id", String(child_id));
      return request<DaySummary[]>(`/api/reports/summary?${qs}`);
    },
    topDomains: (child_id?: number, hours = 24) => {
      const qs = new URLSearchParams({ hours: String(hours) });
      if (child_id) qs.set("child_id", String(child_id));
      return request<{ top_allowed: TopDomain[]; top_blocked: TopDomain[] }>(`/api/reports/top-domains?${qs}`);
    },
    coverage: (childId: number) => request<CoverageReport>(`/api/reports/coverage?child_id=${childId}`),
  },

  alerts: {
    list: (params?: { child_id?: number; unread_only?: boolean }) => {
      const qs = new URLSearchParams();
      if (params?.child_id) qs.set("child_id", String(params.child_id));
      if (params?.unread_only) qs.set("unread_only", "true");
      return request<Alert[]>(`/api/alerts?${qs}`);
    },
    unreadCount: () => request<{ count: number }>("/api/alerts/unread-count"),
    markRead: (id: number) => request(`/api/alerts/${id}/read`, { method: "POST" }),
    markAllRead: () => request("/api/alerts/read-all", { method: "POST" }),
  },

  agents: {
    iosProfileUrl: (childId: number) => `${BASE}/api/agents/${childId}/ios-profile`,
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SetupStatus {
  wizard_complete: boolean;
  password_set: boolean;
  network_name: string;
  children_count: number;
  devices_assigned: number;
}

export interface Child {
  id: number;
  name: string;
  age: number | null;
  birthday: string | null;
  preset: string;
  avatar: string | null;
  created_at: string;
}

export interface Device {
  id: number;
  mac: string;
  hostname: string | null;
  ip: string | null;
  label: string | null;
  device_type: string | null;
  child_id: number | null;
  last_seen: string | null;
}

export interface Schedule {
  id: number;
  name: string;
  days: string[];
  start_time: string;
  end_time: string;
  action: string;
  enabled: boolean;
}

export interface AllowException {
  id: number;
  domain: string;
  label: string | null;
}

export interface DnsLogEntry {
  id: number;
  ts: string;
  client_ip: string | null;
  domain: string;
  blocked: boolean;
  rule: string | null;
  child_id: number | null;
}

export interface DaySummary {
  date: string;
  total: number;
  blocked: number;
}

export interface TopDomain {
  domain: string;
  hits: number;
}

export interface Alert {
  id: number;
  ts: string;
  child_id: number | null;
  alert_type: string;
  title: string;
  detail: string | null;
  read: boolean;
}

export interface CoverageReport {
  child_id: number;
  devices: {
    device: string;
    device_type: string;
    can_see: string[];
    cannot_see: string[];
  }[];
  universal_gaps: string[];
}

export interface WizardChild {
  name: string;
  age: number;
  birthday?: string;
  preset: string;
}
