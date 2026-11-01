import { Link } from "react-router-dom";
import { StatusBadge } from "./StatusBadge";
import type { RequestSummary } from "../types/requests";

export function RequestList({
  items,
  empty = "No requests.",
}: {
  items: RequestSummary[];
  empty?: string;
}) {
  if (items.length === 0) {
    return <p className="text-ink-700">{empty}</p>;
  }
  return (
    <ul className="divide-y divide-ink-900/10 border border-ink-900/10 bg-white/70">
      {items.map((req) => (
        <li key={req.id}>
          <Link
            to={`/app/requests/${req.id}`}
            className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-brand-50/60"
          >
            <div>
              <p className="font-medium text-ink-900">{req.title}</p>
              <p className="text-xs text-ink-700">
                {req.is_hr_sensitive ? "HR case · " : ""}
                Updated {new Date(req.updated_at).toLocaleString()}
              </p>
            </div>
            <StatusBadge status={req.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
