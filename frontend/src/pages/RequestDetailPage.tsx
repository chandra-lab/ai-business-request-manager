import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { requestsApi } from "../api/requests";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../hooks/useAuth";
import { useRequestLiveUpdates } from "../hooks/useRequestLiveUpdates";
import type { AIAnalysis } from "../types/analysis";
import type { RequestDetail, RequestHistoryItem } from "../types/requests";

interface Comment {
  id: string;
  author_id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}

interface AssignableUser {
  id: string;
  email: string;
  full_name: string;
}

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasRole, user } = useAuth();
  const isStaff = hasRole("admin", "department_manager", "reviewer", "hr");
  const canAssign = hasRole("admin", "department_manager", "reviewer");

  const [request, setRequest] = useState<RequestDetail | null>(null);
  const [history, setHistory] = useState<RequestHistoryItem[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [analysisPending, setAnalysisPending] = useState(true);
  const [liveMode, setLiveMode] = useState<"sse+poll" | "idle">("idle");
  const [error, setError] = useState<string | null>(null);
  const [clarify, setClarify] = useState("");
  const [commentText, setCommentText] = useState("");
  const [busy, setBusy] = useState(false);
  const [assignable, setAssignable] = useState<AssignableUser[]>([]);
  const [assigneeId, setAssigneeId] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    const [detail, hist, analysisResult, commentList] = await Promise.all([
      requestsApi.get(id),
      requestsApi.history(id),
      requestsApi.analysis(id),
      requestsApi.comments(id),
    ]);
    setRequest(detail);
    setHistory(hist);
    setAnalysis(analysisResult);
    setAnalysisPending(analysisResult === null);
    setComments(commentList);

    if (
      canAssign &&
      detail.department_id &&
      ["pending_assignment", "assigned", "in_progress"].includes(detail.status)
    ) {
      try {
        const users = await requestsApi.assignableUsers(id);
        setAssignable(users);
        setAssigneeId((current) => current || users[0]?.id || "");
      } catch {
        setAssignable([]);
      }
    }
  }, [id, canAssign]);

  useEffect(() => {
    let cancelled = false;
    load().catch((err: Error) => {
      if (!cancelled) setError(err.message);
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const liveEnabled = Boolean(
    request &&
      !["cancelled", "closed"].includes(request.status) &&
      (analysisPending ||
        ["submitted", "ai_processing", "pending_review", "pending_assignment"].includes(
          request.status,
        )),
  );

  useRequestLiveUpdates(id, load, { enabled: liveEnabled });

  useEffect(() => {
    setLiveMode(liveEnabled ? "sse+poll" : "idle");
  }, [liveEnabled]);

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

  async function onComment(event: FormEvent) {
    event.preventDefault();
    if (!id || !commentText.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await requestsApi.addComment(id, commentText.trim());
      setCommentText("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comment failed");
    } finally {
      setBusy(false);
    }
  }

  async function onAssign(event: FormEvent) {
    event.preventDefault();
    if (!id || !assigneeId) return;
    setBusy(true);
    setError(null);
    try {
      await requestsApi.assign(id, assigneeId, "Assigned from ticket detail");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assign failed");
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

  const isRequester = user?.id === request.requester_id;

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
          {isRequester ? (
            <p className="mt-2 text-sm text-brand-700">
              Ticket received. Current status is shown below. Use comments to talk with reviewers
              and the assignee.
            </p>
          ) : null}
        </div>
        <StatusBadge status={request.status} />
      </div>

      {liveMode === "sse+poll" ? (
        <p className="mt-4 border border-brand-500/20 bg-brand-50 px-3 py-2 text-sm text-brand-700">
          Live updates on ({analysisPending ? "waiting for AI analysis" : "status changes"}) —
          SSE with polling fallback.
        </p>
      ) : null}

      <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Description</h2>
        <p className="mt-2 whitespace-pre-wrap text-ink-900">{request.description}</p>
      </section>

      {isStaff ? (
        <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">AI analysis</h2>
          {analysis ? (
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
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
            </dl>
          ) : (
            <p className="mt-2 text-sm text-ink-700">No analysis yet.</p>
          )}
        </section>
      ) : null}

      <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Comments</h2>
        <ul className="mt-3 space-y-3">
          {comments.length === 0 ? (
            <li className="text-sm text-ink-700">No comments yet.</li>
          ) : (
            comments.map((c) => (
              <li key={c.id} className="border-l-2 border-brand-500/40 pl-3 text-sm">
                <p className="font-medium">{c.author_name || c.author_id}</p>
                <p className="whitespace-pre-wrap text-ink-900">{c.body}</p>
                <p className="text-xs text-ink-700">{new Date(c.created_at).toLocaleString()}</p>
              </li>
            ))
          )}
        </ul>
        <form onSubmit={(e) => void onComment(e)} className="mt-4">
          <textarea
            className="w-full border border-ink-900/15 px-3 py-2 text-sm"
            rows={3}
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Write a comment…"
          />
          <button
            type="submit"
            disabled={busy || !commentText.trim()}
            className="mt-2 bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Post comment
          </button>
        </form>
      </section>

      {canAssign &&
      request.department_id &&
      ["pending_assignment", "assigned", "in_progress"].includes(request.status) ? (
        <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">Assign / reassign person</h2>
          <p className="mt-1 text-sm text-ink-700">
            Managers and reviewers can assign an individual in the request department.
          </p>
          <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={(e) => void onAssign(e)}>
            <label className="text-sm">
              <span className="text-ink-700">Assignee</span>
              <select
                className="mt-1 block min-w-[16rem] border border-ink-900/15 px-2 py-1.5"
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
              >
                {assignable.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              disabled={busy || !assigneeId}
              className="bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Save assignment
            </button>
          </form>
        </section>
      ) : null}

      {isStaff && history.length > 0 ? (
        <section className="mt-6 border border-ink-900/10 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">Internal history</h2>
          <ol className="mt-3 space-y-3">
            {history.map((h) => (
              <li key={h.id} className="border-l-2 border-ink-900/20 pl-3 text-sm">
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
      ) : null}

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

      {request.status === "submitted" && isRequester ? (
        <form onSubmit={(e) => void onClarify(e)} className="mt-6 border border-ink-900/10 bg-white/80 p-5">
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
