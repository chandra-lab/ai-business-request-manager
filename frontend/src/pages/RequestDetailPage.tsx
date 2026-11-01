import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { requestsApi } from "../api/requests";
import { StatusBadge } from "../components/StatusBadge";
import type { RequestDetail, RequestHistoryItem } from "../types/requests";

const POLL_STATUSES = new Set(["submitted", "ai_processing", "pending_review"]);

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [request, setRequest] = useState<RequestDetail | null>(null);
  const [history, setHistory] = useState<RequestHistoryItem[]>([]);
  const [analysisNote, setAnalysisNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clarify, setClarify] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    const [detail, hist] = await Promise.all([
      requestsApi.get(id),
      requestsApi.history(id),
    ]);
    setRequest(detail);
    setHistory(hist);
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || ""}/api/v1/requests/${id}/analysis`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("aibrm_access_token") || ""}`,
          },
        },
      );
      if (res.status === 404) {
        setAnalysisNote("AI analysis not available yet (Phase 3).");
      } else if (res.ok) {
        const data = await res.json();
        setAnalysisNote(data.rationale || `Analysis status: ${data.status}`);
      }
    } catch {
      setAnalysisNote("AI analysis not available yet (Phase 3).");
    }
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    load().catch((err: Error) => {
      if (!cancelled) setError(err.message);
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  useEffect(() => {
    if (!request || !POLL_STATUSES.has(request.status)) return;
    const timer = window.setInterval(() => {
      void load().catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [request?.status, load, request]);

  async function submitDraft() {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await requestsApi.update(id, { status: "submitted" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  async function cancelRequest() {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await requestsApi.update(id, { status: "cancelled" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setBusy(false);
    }
  }

  async function onClarify(event: FormEvent) {
    event.preventDefault();
    if (!id || !clarify.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await requestsApi.update(id, { description: clarify.trim() });
      setClarify("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !request) {
    return <p className="text-red-700">{error}</p>;
  }
  if (!request) {
    return <p className="text-ink-700">Loading request…</p>;
  }

  return (
    <div>
      <p className="mb-4 text-sm">
        <Link to="/app" className="text-brand-700 hover:underline">
          ← Dashboard
        </Link>
      </p>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink-900">{request.title}</h1>
          <p className="mt-2 text-sm text-ink-700">
            Priority: {request.priority} · Updated {new Date(request.updated_at).toLocaleString()}
          </p>
        </div>
        <StatusBadge status={request.status} />
      </div>

      {POLL_STATUSES.has(request.status) ? (
        <p className="mt-4 border border-brand-500/20 bg-brand-50 px-3 py-2 text-sm text-brand-700">
          Status is <strong>{request.status.replaceAll("_", " ")}</strong>. Refreshing every 5s
          while waiting for routing (Phase 3+).
        </p>
      ) : null}

      <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Description</h2>
        <p className="mt-2 whitespace-pre-wrap text-ink-900">{request.description}</p>
      </section>

      <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">AI analysis</h2>
        <p className="mt-2 text-sm text-ink-700">{analysisNote}</p>
      </section>

      {request.attachments.length > 0 ? (
        <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">Attachments</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {request.attachments.map((a) => (
              <li key={a.id}>
                {a.filename}{" "}
                <span className="text-ink-700">
                  ({a.content_type}, {a.size_bytes} bytes)
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">History</h2>
        <ol className="mt-3 space-y-3">
          {history.map((h) => (
            <li key={h.id} className="border-l-2 border-brand-500/40 pl-3 text-sm">
              <p className="font-medium">{h.action}</p>
              <p className="text-ink-700">
                {h.from_status || "—"} → {h.to_status || "—"} ·{" "}
                {new Date(h.created_at).toLocaleString()}
              </p>
              {h.details ? <p className="text-ink-700">{h.details}</p> : null}
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-6 flex flex-wrap gap-3">
        {request.status === "draft" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void submitDraft()}
            className="bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            Submit
          </button>
        ) : null}
        {request.status === "draft" || request.status === "submitted" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void cancelRequest()}
            className="border border-ink-900/20 px-4 py-2 text-sm hover:bg-ink-900/5 disabled:opacity-60"
          >
            Cancel request
          </button>
        ) : null}
      </section>

      {request.status === "submitted" ? (
        <form onSubmit={onClarify} className="mt-6 border border-ink-900/10 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">Clarify description</h2>
          <textarea
            className="mt-2 w-full border border-ink-900/15 px-3 py-2"
            rows={4}
            value={clarify}
            onChange={(e) => setClarify(e.target.value)}
            placeholder="Add clarification details…"
          />
          <button
            type="submit"
            disabled={busy || !clarify.trim()}
            className="mt-3 bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            Save clarification
          </button>
        </form>
      ) : null}

      {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}
    </div>
  );
}
