import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { dashboardsApi, type DepartmentDashboard as DeptData } from "../api/dashboards";
import { MetricGrid } from "../components/MetricGrid";
import { RequestList } from "../components/RequestList";

export function DepartmentDashboard() {
  const [data, setData] = useState<DeptData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    dashboardsApi
      .department()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    const timer = window.setInterval(() => {
      void dashboardsApi.department().then((d) => {
        if (!cancelled) setData(d);
      });
    }, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (error) return <p className="text-red-700">{error}</p>;
  if (!data) return <p className="animate-pulse text-ink-700">Loading department dashboard…</p>;

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Team queue</p>
          <h1 className="font-display text-3xl font-semibold">Team workload</h1>
          <p className="mt-1 text-ink-700">
            Non-HR requests routed to your department — visible to all team members, not only
            managers.
          </p>
        </div>
      </div>

      <MetricGrid
        metrics={[
          { label: "Pending assignment", value: data.pending_assignment_count },
          { label: "Assigned", value: data.assigned_count },
          { label: "In progress", value: data.in_progress_count },
          { label: "Resolved", value: data.resolved_count },
        ]}
      />

      <h2 className="mb-3 font-display text-lg font-semibold">Recent department requests</h2>
      <RequestList items={data.recent} empty="No department requests yet." />
    </div>
  );
}
