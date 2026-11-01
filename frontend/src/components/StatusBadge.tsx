import type { RequestStatus } from "../types/requests";

const STYLES: Record<RequestStatus, string> = {
  draft: "bg-ink-900/10 text-ink-700",
  submitted: "bg-brand-100 text-brand-700",
  ai_processing: "bg-amber-100 text-amber-900",
  pending_review: "bg-orange-100 text-orange-900",
  pending_assignment: "bg-sky-100 text-sky-900",
  assigned: "bg-sky-100 text-sky-900",
  in_progress: "bg-sky-100 text-sky-900",
  resolved: "bg-emerald-100 text-emerald-900",
  closed: "bg-ink-900/10 text-ink-700",
  cancelled: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: RequestStatus }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${STYLES[status] || "bg-ink-900/10"}`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}
