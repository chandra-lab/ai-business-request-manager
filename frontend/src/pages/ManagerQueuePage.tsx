import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { routingApi } from "../api/routing";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../hooks/useAuth";
import type { RequestSummary } from "../types/requests";

export function ManagerQueuePage() {
  const { user } = useAuth();
  const [items, setItems] = useState<RequestSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [assigneeId, setAssigneeId] = useState(user?.id || "");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    const data = await routingApi.managerQueue();
    setItems(data);
  }

  useEffect(() => {
    if (user?.id) setAssigneeId(user.id);
    load().catch((err: Error) => setError(err.message));
  }, [user?.id]);

  async function onAssign(event: FormEvent, requestId: string) {
    event.preventDefault();
    if (!assigneeId) return;
    setBusyId(requestId);
    setError(null);
    try {
      await routingApi.assignEmployee(requestId, assigneeId, "Assigned from manager queue");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assign failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold">Manager assignment queue</h1>
      <p className="mt-1 text-ink-700">
        Department-routed requests waiting for an individual assignee.
      </p>

      <label className="mt-6 block max-w-xl text-sm">
        <span className="text-ink-700">Assignee user UUID (defaults to you)</span>
        <input
          className="mt-1 w-full border border-ink-900/15 px-3 py-2"
          value={assigneeId}
          onChange={(e) => setAssigneeId(e.target.value.trim())}
        />
      </label>

      {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}

      <ul className="mt-6 divide-y divide-ink-900/10 border border-ink-900/10 bg-white/80">
        {items.length === 0 ? (
          <li className="px-4 py-6 text-ink-700">No pending assignments.</li>
        ) : (
          items.map((item) => (
            <li key={item.id} className="px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Link className="font-medium text-brand-700 hover:underline" to={`/app/requests/${item.id}`}>
                    {item.title}
                  </Link>
                  <p className="text-xs text-ink-700">
                    Updated {new Date(item.updated_at).toLocaleString()}
                  </p>
                </div>
                <StatusBadge status={item.status} />
              </div>
              <form className="mt-3" onSubmit={(e) => void onAssign(e, item.id)}>
                <button
                  type="submit"
                  disabled={busyId === item.id || !assigneeId}
                  className="bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Assign to selected user
                </button>
              </form>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
