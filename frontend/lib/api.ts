import { usePunji } from "@/store";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("punji_access_token");
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("punji_access_token", access);
  localStorage.setItem("punji_refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("punji_access_token");
  localStorage.removeItem("punji_refresh_token");
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    usePunji.getState().clearAuth();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }

  return res.json();
}

// Auth
export const api = {
  auth: {
    register: (data: { email: string; password: string; full_name?: string }) =>
      apiFetch<{ access_token: string; refresh_token: string; user: User }>("/api/auth/register", {
        method: "POST", body: JSON.stringify(data),
      }),
    login: (data: { email: string; password: string }) =>
      apiFetch<{ access_token: string; refresh_token: string; user: User }>("/api/auth/login", {
        method: "POST", body: JSON.stringify(data),
      }),
    setRiskProfile: (drawdown_response: string) =>
      apiFetch("/api/auth/onboarding/risk-profile", {
        method: "POST", body: JSON.stringify({ drawdown_response }),
      }),
    onboardingStatus: () => apiFetch<{ onboarding_step: number; is_complete: boolean }>("/api/auth/onboarding/status"),
  },

  portfolio: {
    summary: () => apiFetch<PortfolioSummary>("/api/portfolio/summary"),
    allocation: () => apiFetch("/api/portfolio/allocation"),
    performance: (period = "1y") => apiFetch(`/api/portfolio/performance?period=${period}`),
    concentration: () => apiFetch("/api/portfolio/concentration"),
    exposure: () => apiFetch<PortfolioExposure>("/api/portfolio/exposure"),
    refreshCompositions: () =>
      apiFetch<{ schemes_processed: number; total_rows: number }>("/api/portfolio/refresh-compositions", {
        method: "POST",
      }),
    snapshots: (from?: string, to?: string) => {
      const q = new URLSearchParams();
      if (from) q.set("from_date", from);
      if (to) q.set("to_date", to);
      return apiFetch(`/api/portfolio/snapshots?${q}`);
    },
  },

  holdings: {
    list: (filters?: { instrument_type?: string; asset_class?: string }) => {
      const q = new URLSearchParams(filters as Record<string, string>);
      return apiFetch<Holding[]>(`/api/holdings?${q}`);
    },
    get: (id: string) => apiFetch<Holding>(`/api/holdings/${id}`),
    create: (data: Partial<Holding>) =>
      apiFetch<Holding>("/api/holdings", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: Partial<Holding>) =>
      apiFetch<Holding>(`/api/holdings/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) => apiFetch(`/api/holdings/${id}`, { method: "DELETE" }),
    refresh: (id: string) => apiFetch(`/api/holdings/${id}/refresh`, { method: "POST" }),
  },

  transactions: {
    list: (params?: Record<string, string>) => {
      const q = new URLSearchParams(params);
      return apiFetch<Transaction[]>(`/api/transactions?${q}`);
    },
    create: (data: Partial<Transaction>) =>
      apiFetch<Transaction>("/api/transactions", { method: "POST", body: JSON.stringify(data) }),
  },

  goals: {
    list: () => apiFetch<Goal[]>("/api/goals"),
    create: (data: Partial<Goal>) =>
      apiFetch<Goal>("/api/goals", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: Partial<Goal>) =>
      apiFetch<Goal>(`/api/goals/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) => apiFetch(`/api/goals/${id}`, { method: "DELETE" }),
    simulate: (id: string) => apiFetch(`/api/goals/${id}/simulate`, { method: "POST" }),
    simulation: (id: string) => apiFetch(`/api/goals/${id}/simulation`),
  },

  alerts: {
    list: (params?: Record<string, string>) => {
      const q = new URLSearchParams(params);
      return apiFetch<Alert[]>(`/api/alerts?${q}`);
    },
    markRead: (id: string) => apiFetch(`/api/alerts/${id}/read`, { method: "PUT" }),
    markAllRead: () => apiFetch("/api/alerts/read-all", { method: "PUT" }),
    feedback: (id: string, feedback: string) =>
      apiFetch(`/api/alerts/${id}/feedback`, { method: "POST", body: JSON.stringify({ feedback }) }),
  },

  agent: {
    memories: () => apiFetch("/api/agent/memories"),
    deleteMemory: (id: string) => apiFetch(`/api/agent/memories/${id}`, { method: "DELETE" }),
    conversations: () => apiFetch("/api/agent/conversations"),
    conversation: (id: string) => apiFetch(`/api/agent/conversations/${id}`),
  },

  imports: {
    upload: (file: File, platform: string, password?: string) => {
      const form = new FormData();
      form.append("file", file);
      form.append("source_platform", platform);
      if (password) form.append("password", password);
      const token = getToken();
      return fetch(`${BASE}/api/imports/upload`, {
        method: "POST",
        headers: { "ngrok-skip-browser-warning": "true", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: form,
      }).then((r) => r.json());
    },
    preview: (jobId: string) => apiFetch(`/api/imports/${jobId}/preview`),
    confirm: (jobId: string, data: object) =>
      apiFetch(`/api/imports/${jobId}/confirm`, { method: "POST", body: JSON.stringify(data) }),
    history: () => apiFetch("/api/imports/history"),
  },

  market: {
    mf: (schemeCode: number) => apiFetch(`/api/market/mf/${schemeCode}`),
    stock: (symbol: string) => apiFetch(`/api/market/stock/${symbol}`),
    macro: () => apiFetch("/api/market/macro"),
    searchMf: (q: string) => apiFetch(`/api/market/mf/search?q=${encodeURIComponent(q)}`),
  },

  scenarios: {
    simulate: (data: object) =>
      apiFetch("/api/scenarios/simulate", { method: "POST", body: JSON.stringify(data) }),
  },
};

// SSE chat
export function streamChat(
  message: string,
  conversationId: string | null,
  onToken: (t: string) => void,
  onTrace: (trace: string[]) => void,
  onDone: (convId: string) => void,
  onError: (e: string) => void,
) {
  const token = getToken();
  fetch(`${BASE}/api/agent/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  }).then(async (res) => {
    if (!res.ok) { onError("Request failed"); return; }
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      for (const line of text.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "token") onToken(evt.data);
          else if (evt.type === "reasoning_trace") onTrace(evt.data);
          else if (evt.type === "done") onDone(evt.data.conversation_id);
          else if (evt.type === "error") onError(evt.data);
        } catch {}
      }
    }
  }).catch((e) => onError(String(e)));
}

// Types (minimal)
export interface User { id: string; email: string; full_name?: string; onboarding_step: number; }
export interface Holding { id: string; instrument_type: string; display_name: string; asset_class: string; invested_amount: number; current_value: number; unrealised_pnl: number; xirr?: number; metadata_: object; }
export interface Transaction { id: string; holding_id: string; transaction_date: string; transaction_type: string; amount: number; units?: number; price?: number; }
export interface Goal { id: string; name: string; target_amount: number; target_date: string; success_probability?: number; monthly_sip_allocated: number; }
export interface Alert { id: string; alert_type: string; severity: string; title: string; message: string; is_read: boolean; created_at: string; }
export interface PortfolioSummary { total_value: number; total_invested: number; total_pnl_amount: number; total_pnl_pct: number; portfolio_xirr?: number; allocation: object; drift: object; benchmarks: object; unread_alerts_count: number; }

export interface ExposureSource {
  label: string;
  pct: number;
  instrument_type: string;
}
export interface StockExposure {
  isin: string;
  name: string;
  sector: string;
  total_pct: number;
  direct_pct: number;
  indirect_pct: number;
  sources: ExposureSource[];
}
export interface SectorExposure {
  sector: string;
  total_pct: number;
  direct_pct: number;
  indirect_pct: number;
}
export interface PortfolioExposure {
  total_value: number;
  by_stock: StockExposure[];
  by_sector: SectorExposure[];
  mf_without_composition: Array<{ name: string; pct_of_portfolio: number }>;
  last_composition_date: string | null;
}
