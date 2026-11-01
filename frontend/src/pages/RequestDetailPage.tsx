import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { requestsApi } from "../api/requests";
import { StatusBadge } from "../components/StatusBadge";
import type { AIAnalysis } from "../types/analysis";
import type { RequestDetail, RequestHistoryItem } from "../types/requests";

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [request, setRequest] = useState<RequestDetail | null>(null);
  const [history, setHistory] = useState<RequestHistoryItem[]>([]);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [analysisPending, setAnalysisPending] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clarify, setClarify] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    const [detail, hist, analysisResult] = await Promise.all([
      requestsApi.get(id),
      requestsApi.history(id),
      requestsApi.analysis(id),
    ]);
    setRequest(detail);
    setHistory(hist);
    setAnalysis(analysisResult);
    setAnalysisPending(analysisResult === null);
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
    // Poll until analysis is present (or request leaves early statuses)
    if (!request) return;
    if (analysis) return;
    if (!["submitted", "ai_processing", "draft"].includes(request.status) && request.status !== "cancelled") {
      // still allow poll briefly after submit path
    }
    if (request.status === "cancelled" || request.status === "closed") return;

    const timer = window.setInterval(() => {
      void load().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [request?.status, analysis, load, request]);

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

      {analysisPending && request.status !== "cancelled" ? (
        <p className="mt-4 border border-brand-500/20 bg-brand-50 px-3 py-2 text-sm text-brand-700">
          Waiting for AI analysis… polling every 3s (Mock by default; no API key required).
        </p>
      ) : null}

      <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Description</h2>
        <p className="mt-2 whitespace-pre-wrap text-ink-900">{request.description}</p>
      </section>

      <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">AI analysis</h2>
        {analysis ? (
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-700">Status</dt>
              <dd className="font-medium">{analysis.status}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-700">Provider / model</dt>
              <dd className="font-medium">
                {analysis.provider}
                {analysis.model_id ? ` · ${analysis.model_id}` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-700">Recommended department</dt>
              <dd className="font-medium">
                {analysis.recommended_department_code || "— (uncertain)"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-700">Confidence</dt>
              <dd className="font-medium">
                {analysis.confidence != null ? `${(analysis.confidence * 100).toFixed(0)}%` : "—"}
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-ink-700">Rationale</dt>
              <dd className="mt-1 text-ink-900">{analysis.rationale}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-700">Prompt version</dt>
              <dd>{analysis.prompt_version || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-700">Duration</dt>
              <dd>{analysis.duration_ms != null ? `${analysis.duration_ms} ms` : "—"}</dd>
            </div>
          </dl>
        ) : (
          <p className="mt-2 text-sm text-ink-700">No analysis yet.</p>
        )}
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
