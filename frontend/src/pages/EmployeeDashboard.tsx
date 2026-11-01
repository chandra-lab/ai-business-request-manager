import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { requestsApi } from "../api/requests";
import { StatusBadge } from "../components/StatusBadge";
import type { EmployeeDashboard as DashboardData } from "../types/requests";

export function EmployeeDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    requestsApi
      .dashboard()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <p className="text-ink-700">Loading dashboard…</p>;
  if (error) return <p className="text-red-700">{error}</p>;
  if (!data) return null;

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink-900">My requests</h1>
          <p className="mt-1 text-ink-700">Track submissions and status updates.</p>
        </div>
        <Link
          to="/app/requests/new"
          className="bg-brand-600 px-4 py-2.5 font-display text-sm font-semibold text-white hover:bg-brand-700"
        >
          New request
        </Link>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Open", data.open_count],
          ["Submitted / reviewing", data.submitted_count],
          ["In progress", data.in_progress_count],
          ["Resolved", data.resolved_count],
        ].map(([label, value]) => (
          <div key={label as string} className="border border-ink-900/10 bg-white/70 p-4">
            <p className="text-xs uppercase tracking-wide text-ink-700">{label}</p>
            <p className="mt-1 font-display text-2xl font-semibold">{value as number}</p>
          </div>
        ))}
      </div>

      <h2 className="mb-3 font-display text-lg font-semibold">Recent</h2>
      {data.recent.length === 0 ? (
        <p className="text-ink-700">No requests yet. Create one to get started.</p>
      ) : (
        <ul className="divide-y divide-ink-900/10 border border-ink-900/10 bg-white/70">
          {data.recent.map((req) => (
            <li key={req.id}>
              <Link
                to={`/app/requests/${req.id}`}
                className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-brand-50/60"
              >
                <div>
                  <p className="font-medium text-ink-900">{req.title}</p>
                  <p className="text-xs text-ink-700">
                    Updated {new Date(req.updated_at).toLocaleString()}
                  </p>
                </div>
                <StatusBadge status={req.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
