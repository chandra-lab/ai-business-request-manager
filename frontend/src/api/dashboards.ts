import { getAccessToken } from "../lib/storage";
import type { EmployeeDashboard, RequestSummary } from "../types/requests";
import type { ReviewQueueItem } from "./routing";

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

async function api<T>(path: string): Promise<T> {
  const headers = new Headers();
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { headers });
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
  return response.json() as Promise<T>;
}

export interface DepartmentDashboard {
  pending_assignment_count: number;
  assigned_count: number;
  in_progress_count: number;
  resolved_count: number;
  recent: RequestSummary[];
}

export interface ReviewDashboard {
  open_count: number;
  in_review_count: number;
  items: ReviewQueueItem[];
}

export interface HRDashboard {
  case_count: number;
  highly_confidential_count: number;
  recent: RequestSummary[];
}

export const dashboardsApi = {
  employee: () => api<EmployeeDashboard>("/api/v1/dashboard/employee"),
  department: () => api<DepartmentDashboard>("/api/v1/dashboard/department"),
  review: () => api<ReviewDashboard>("/api/v1/dashboard/review"),
  hr: () => api<HRDashboard>("/api/v1/dashboard/hr"),
};
