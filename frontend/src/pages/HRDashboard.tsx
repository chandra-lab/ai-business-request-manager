import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { dashboardsApi, type HRDashboard as HRData } from "../api/dashboards";
import { getAccessToken } from "../lib/storage";
import { MetricGrid } from "../components/MetricGrid";
import { RequestList } from "../components/RequestList";

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

interface Note {
  id: string;
  content: string;
  author_id: string;
  created_at: string;
}

export function HRDashboard() {
  const [data, setData] = useState<HRData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [noteText, setNoteText] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const d = await dashboardsApi.hr();
    setData(d);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, []);

  async function openCase(id: string) {
    setSelectedId(id);
    setError(null);
    const headers = { Authorization: `Bearer ${getAccessToken() || ""}` };
    const resp = await fetch(`${API_BASE}/api/v1/requests/${id}/hr-notes`, { headers });
    if (!resp.ok) {
      setNotes([]);
      setError("Could not load HR notes (need HR role).");
      return;
    }
    setNotes((await resp.json()) as Note[]);
  }

  async function addNote(event: FormEvent) {
    event.preventDefault();
    if (!selectedId || !noteText.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/requests/${selectedId}/hr-notes`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getAccessToken() || ""}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ content: noteText.trim() }),
      });
      if (!resp.ok) throw new Error("Failed to add note");
      setNoteText("");
      await openCase(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !data) return <p className="text-red-700">{error}</p>;
  if (!data) return <p className="animate-pulse text-ink-700">Loading HR dashboard…</p>;

  return (
    <div>
      <div className="mb-8">
        <p className="text-xs uppercase tracking-[0.2em] text-brand-700">HR</p>
        <h1 className="font-display text-3xl font-semibold">HR case desk</h1>
        <p className="mt-1 text-ink-700">
          Highly confidential cases. Internal notes are isolated from requesters and non-HR admins.
        </p>
      </div>

      <MetricGrid
        metrics={[
          { label: "Open HR cases", value: data.case_count },
          { label: "Highly confidential", value: data.highly_confidential_count },
          { label: "Listed", value: data.recent.length },
          { label: "Notes panel", value: selectedId ? notes.length : 0 },
        ]}
      />

      {error ? <p className="mb-4 text-sm text-red-700">{error}</p> : null}

      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 font-display text-lg font-semibold">Cases</h2>
          <ul className="divide-y divide-ink-900/10 border border-ink-900/10 bg-white/70">
            {data.recent.length === 0 ? (
              <li className="px-4 py-6 text-ink-700">No HR-sensitive cases.</li>
            ) : (
              data.recent.map((req) => (
                <li key={req.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Link className="font-medium text-brand-700 hover:underline" to={`/app/requests/${req.id}`}>
                      {req.title}
                    </Link>
                    <button
                      type="button"
                      className="text-sm text-ink-700 underline"
                      onClick={() => void openCase(req.id)}
                    >
                      Notes
                    </button>
                  </div>
                  <p className="text-xs text-ink-700">{req.status}</p>
                </li>
              ))
            )}
          </ul>
        </div>

        <div>
          <h2 className="mb-3 font-display text-lg font-semibold">Internal notes</h2>
          {!selectedId ? (
            <p className="text-ink-700">Select a case to view or add HR notes.</p>
          ) : (
            <>
              <ul className="mb-4 max-h-64 space-y-2 overflow-auto border border-ink-900/10 bg-white/80 p-3 text-sm">
                {notes.length === 0 ? (
                  <li className="text-ink-700">No notes yet.</li>
                ) : (
                  notes.map((n) => (
                    <li key={n.id} className="border-l-2 border-brand-500/40 pl-2">
                      <p>{n.content}</p>
                      <p className="text-xs text-ink-700">{new Date(n.created_at).toLocaleString()}</p>
                    </li>
                  ))
                )}
              </ul>
              <form onSubmit={(e) => void addNote(e)}>
                <textarea
                  className="w-full border border-ink-900/15 px-3 py-2 text-sm"
                  rows={3}
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Add confidential HR note…"
                />
                <button
                  type="submit"
                  disabled={busy || !noteText.trim()}
                  className="mt-2 bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Save note
                </button>
              </form>
            </>
          )}
        </div>
      </div>

      <div className="mt-10">
        <h2 className="mb-3 font-display text-lg font-semibold">All listed cases</h2>
        <RequestList items={data.recent} empty="No cases." />
      </div>
    </div>
  );
}
