import { getAccessToken } from "../lib/storage";
import type { RequestSummary } from "../types/requests";

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !headers.has("Content-Type")) {
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
  return response.json() as Promise<T>;
}

export interface ReviewQueueItem {
  id: string;
  request_id: string;
  reason: string;
  details: string | null;
  clarification_required: boolean;
  status: string;
  decision: string | null;
  decision_reason: string | null;
  assigned_department_id: string | null;
  created_at: string;
  request: RequestSummary | null;
}

export const routingApi = {
  reviewQueue() {
    return api<ReviewQueueItem[]>("/api/v1/review-queue");
  },
  openReviewForRequest(requestId: string) {
    return api<ReviewQueueItem>(`/api/v1/review-queue/by-request/${requestId}`);
  },
  assignDepartment(reviewId: string, body: { department_id: string; decision_reason: string }) {
    return api<RequestSummary>(`/api/v1/review-queue/${reviewId}/assign-department`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  assignDepartmentForRequest(
    requestId: string,
    body: { department_id: string; decision_reason: string; final_priority?: string },
  ) {
    return api<RequestSummary>(`/api/v1/review-queue/by-request/${requestId}/assign-department`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  requestInformation(reviewId: string, message: string) {
    return api<RequestSummary>(`/api/v1/review-queue/${reviewId}/request-information`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
  },
  requestInformationForRequest(requestId: string, message: string) {
    return api<RequestSummary>(
      `/api/v1/review-queue/by-request/${requestId}/request-information`,
      {
        method: "POST",
        body: JSON.stringify({ message }),
      },
    );
  },
  managerQueue() {
    return api<RequestSummary[]>("/api/v1/manager/queue");
  },
  assignEmployee(requestId: string, assigneeId: string, notes?: string) {
    return api(`/api/v1/requests/${requestId}/assign`, {
      method: "POST",
      body: JSON.stringify({ assignee_id: assigneeId, notes }),
    });
  },
  departments() {
    return api<{ id: string; code: string; name: string; is_active: boolean }[]>(
      "/api/v1/departments",
    );
  },
  departmentMembers(departmentId: string) {
    return api<{ id: string; email: string; full_name: string; department_id: string | null }[]>(
      `/api/v1/departments/${departmentId}/members`,
    );
  },
};
