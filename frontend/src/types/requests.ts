export type RequestStatus =
  | "draft"
  | "submitted"
  | "ai_processing"
  | "pending_review"
  | "assigned"
  | "in_progress"
  | "resolved"
  | "closed"
  | "cancelled";

export type RequestPriority = "low" | "medium" | "high" | "urgent";

export interface RequestSummary {
  id: string;
  title: string;
  status: RequestStatus;
  priority: RequestPriority;
  requester_id: string;
  department_id: string | null;
  is_hr_sensitive: boolean;
  created_at: string;
  updated_at: string;
}

export interface Attachment {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface RequestDetail extends RequestSummary {
  description: string;
  attachments: Attachment[];
}

export interface RequestListResponse {
  items: RequestSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface RequestHistoryItem {
  id: string;
  action: string;
  from_status: string | null;
  to_status: string | null;
  details: string | null;
  actor_id: string | null;
  created_at: string;
}

export interface EmployeeDashboard {
  open_count: number;
  submitted_count: number;
  in_progress_count: number;
  resolved_count: number;
  recent: RequestSummary[];
}
