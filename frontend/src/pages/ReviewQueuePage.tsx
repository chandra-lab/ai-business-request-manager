import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAccessToken } from "../lib/storage";
import { routingApi, type ReviewQueueItem } from "../api/routing";
import { StatusBadge } from "../components/StatusBadge";

interface Dept {
  id: string;
  code: string;
  name: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

export function ReviewQueuePage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [departments, setDepartments] = useState<Dept[]>([]);
  const [selectedDept, setSelectedDept] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    const [queue, deps] = await Promise.all([
      routingApi.reviewQueue(),
      fetch(`${API_BASE}/api/v1/departments`, {
        headers: { Authorization: `Bearer ${getAccessToken() || ""}` },
      }).then(async (r) => {
        if (!r.ok) throw new Error("Failed to load departments");
        return r.json() as Promise<Dept[]>;
      }),
    ]);
    setItems(queue);
    setDepartments(deps);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, []);

  async function assign(item: ReviewQueueItem) {
    const departmentId = selectedDept[item.id] || departments.find((d) => d.code === "IT")?.id;
    if (!departmentId) {
      setError("Select a department");
      return;
    }
    setBusyId(item.id);
    setError(null);
    try {
      await routingApi.assignDepartment(item.id, {
        department_id: departmentId,
        decision_reason: `Assigned to department after review (${item.reason})`,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assign failed");
    } finally {
      setBusyId(null);
    }
  }

  async function askInfo(item: ReviewQueueItem) {
    setBusyId(item.id);
    setError(null);
    try {
      await routingApi.requestInformation(
        item.id,
        "Please clarify what system or process is affected and the business impact.",
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold">Review queue</h1>
      <p className="mt-1 text-ink-700">
        Medium/low confidence and AI failures land here. Assign a department or request information.
      </p>

      {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}

      <ul className="mt-6 divide-y divide-ink-900/10 border border-ink-900/10 bg-white/80">
        {items.length === 0 ? (
          <li className="px-4 py-6 text-ink-700">Queue is empty.</li>
        ) : (
          items.map((item) => (
            <li key={item.id} className="px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium">
                    {item.request ? (
                      <Link
                        className="text-brand-700 hover:underline"
                        to={`/app/requests/${item.request_id}`}
                      >
                        {item.request.title}
                      </Link>
                    ) : (
                      item.request_id
                    )}
                  </p>
                  <p className="text-sm text-ink-700">
                    Reason: {item.reason}
                    {item.clarification_required ? " · clarification required" : ""}
                  </p>
                  {item.details ? <p className="text-xs text-ink-700">{item.details}</p> : null}
                </div>
                {item.request ? <StatusBadge status={item.request.status} /> : null}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <select
                  className="border border-ink-900/15 px-2 py-1.5 text-sm"
                  value={selectedDept[item.id] || ""}
                  onChange={(e) =>
                    setSelectedDept((s) => ({ ...s, [item.id]: e.target.value }))
                  }
                >
                  <option value="">Select department</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.code} — {d.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={busyId === item.id}
                  onClick={() => void assign(item)}
                  className="bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Assign department
                </button>
                <button
                  type="button"
                  disabled={busyId === item.id}
                  onClick={() => void askInfo(item)}
                  className="border border-ink-900/20 px-3 py-1.5 text-sm"
                >
                  Request information
                </button>
              </div>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
