import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { dashboardsApi } from "../api/dashboards";
import { MetricGrid } from "../components/MetricGrid";
import { RequestList } from "../components/RequestList";
import type { EmployeeDashboard as DashboardData } from "../types/requests";

export function EmployeeDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    dashboardsApi
      .employee()
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

  if (loading) return <p className="animate-pulse text-ink-700">Loading dashboard…</p>;
  if (error) return <p className="text-red-700">{error}</p>;
  if (!data) return null;

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Employee</p>
          <h1 className="font-display text-3xl font-semibold text-ink-900">My tickets</h1>
          <p className="mt-1 text-ink-700">Track submissions, AI routing, and status updates.</p>
        </div>
        <Link
          to="/app/requests/new"
          className="bg-brand-600 px-4 py-2.5 font-display text-sm font-semibold text-white transition hover:bg-brand-700"
        >
          New request
        </Link>
      </div>

      <MetricGrid
        metrics={[
          { label: "Open", value: data.open_count },
          { label: "Submitted / reviewing", value: data.submitted_count },
          { label: "In progress", value: data.in_progress_count },
          { label: "Resolved", value: data.resolved_count },
        ]}
      />

      <h2 className="mb-3 font-display text-lg font-semibold">Recent</h2>
      <RequestList items={data.recent} empty="No requests yet. Create one to get started." />
    </div>
  );
}
