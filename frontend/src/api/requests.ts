import { getAccessToken } from "../lib/storage";
import type { AIAnalysis } from "../types/analysis";
import type {
  EmployeeDashboard,
  RequestDetail,
  RequestHistoryItem,
  RequestListResponse,
  RequestPriority,
} from "../types/requests";

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const requestsApi = {
  list(params?: { status?: string; page?: number }) {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.page) q.set("page", String(params.page));
    const qs = q.toString();
    return api<RequestListResponse>(`/api/v1/requests${qs ? `?${qs}` : ""}`);
  },

  get(id: string) {
    return api<RequestDetail>(`/api/v1/requests/${id}`);
  },

  create(
    body: {
      title: string;
      description: string;
      priority: RequestPriority;
      submit: boolean;
      is_hr_sensitive?: boolean;
    },
    idempotencyKey?: string,
  ) {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return api<RequestDetail>("/api/v1/requests", {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
  },

  update(
    id: string,
    body: Partial<{
      title: string;
      description: string;
      priority: RequestPriority;
      status: string;
    }>,
  ) {
    return api<RequestDetail>(`/api/v1/requests/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  history(id: string) {
    return api<RequestHistoryItem[]>(`/api/v1/requests/${id}/history`);
  },

  async analysis(id: string): Promise<AIAnalysis | null> {
    const headers = new Headers();
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(
      `${API_BASE}/api/v1/requests/${id}/analysis`,
      { headers },
    );
    if (response.status === 404) return null;
    if (!response.ok) {
      throw new Error(response.statusText || "Failed to load analysis");
    }
    return response.json() as Promise<AIAnalysis>;
  },

  dashboard() {
    return api<EmployeeDashboard>("/api/v1/dashboard/employee");
  },

  async upload(id: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    return api<import("../types/requests").Attachment>(`/api/v1/requests/${id}/attachments`, {
      method: "POST",
      body: form,
    });
  },
};
