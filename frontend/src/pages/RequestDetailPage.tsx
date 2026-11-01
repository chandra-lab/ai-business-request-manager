import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { requestsApi } from "../api/requests";
import { routingApi, type ReviewQueueItem } from "../api/routing";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../hooks/useAuth";
import { useRequestLiveUpdates } from "../hooks/useRequestLiveUpdates";
import type { AIAnalysis } from "../types/analysis";
import type { RequestDetail, RequestHistoryItem, RequestPriority } from "../types/requests";

const PRIORITIES: RequestPriority[] = ["low", "medium", "high", "urgent"];

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

interface DeptOption {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasRole, user } = useAuth();
  const isStaff = hasRole("admin", "department_manager", "reviewer", "hr");
  const canReviewRoute = hasRole("admin", "reviewer");
  const canAssignPerson = hasRole("admin", "department_manager", "reviewer");
  const canSetPriority = hasRole("admin", "reviewer", "department_manager");

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
  const [departments, setDepartments] = useState<DeptOption[]>([]);
  const [selectedDeptId, setSelectedDeptId] = useState("");
  const [deptMembers, setDeptMembers] = useState<AssignableUser[]>([]);
  const [openReview, setOpenReview] = useState<ReviewQueueItem | null>(null);
  const [infoMessage, setInfoMessage] = useState("");
  const [editPriority, setEditPriority] = useState<RequestPriority>("medium");

  const load = useCallback(async () => {
    if (!id) return;
    const [detail, hist, analysisResult, commentList] = await Promise.all([
      requestsApi.get(id),
      requestsApi.history(id),
      requestsApi.analysis(id),
      requestsApi.comments(id),
    ]);
    setRequest(detail);
    setEditPriority(detail.priority);
    setHistory(hist);
    setAnalysis(analysisResult);
    setAnalysisPending(analysisResult === null);
    setComments(commentList);

    if (canReviewRoute || canAssignPerson) {
      try {
        const deps = await routingApi.departments();
        setDepartments(deps.filter((d) => d.is_active !== false));
      } catch {
        setDepartments([]);
      }
    }

    if (canReviewRoute && detail.status === "pending_review") {
      try {
        const review = await routingApi.openReviewForRequest(id);
        setOpenReview(review);
      } catch {
        setOpenReview(null);
      }
      if (analysisResult?.recommended_department_id) {
        setSelectedDeptId((cur) => cur || analysisResult.recommended_department_id || "");
      }
    } else {
      setOpenReview(null);
    }

    if (
      canAssignPerson &&
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
    } else {
      setAssignable([]);
    }
  }, [id, canReviewRoute, canAssignPerson]);

  useEffect(() => {
    let cancelled = false;
    load().catch((err: Error) => {
      if (!cancelled) setError(err.message);
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  // Reviewer Actions: filter assignee picker to active members of the selected department
  useEffect(() => {
    if (!canReviewRoute || !selectedDeptId) {
      setDeptMembers([]);
      return;
    }
    let cancelled = false;
    routingApi
      .departmentMembers(selectedDeptId)
      .then((members) => {
        if (cancelled) return;
        setDeptMembers(members);
        setAssigneeId((cur) =>
          cur && members.some((m) => m.id === cur) ? cur : members[0]?.id || "",
        );
      })
      .catch(() => {
        if (!cancelled) setDeptMembers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [canReviewRoute, selectedDeptId]);

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

  async function onAssignPerson(event: FormEvent) {
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

  async function onSavePriority(event: FormEvent) {
    event.preventDefault();
    if (!id || !editPriority) return;
    setBusy(true);
    setError(null);
    try {
      await requestsApi.update(id, { priority: editPriority });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Priority update failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRouteDepartment(event: FormEvent) {
    event.preventDefault();
    if (!id || !selectedDeptId) {
      setError("Select a department to route");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await routingApi.assignDepartmentForRequest(id, {
        department_id: selectedDeptId,
        decision_reason: "Routed from ticket detail",
      });
      // Optionally assign a member of that department in the same Actions flow
      if (assigneeId && deptMembers.some((m) => m.id === assigneeId)) {
        await requestsApi.assign(id, assigneeId, "Assigned with department from ticket detail");
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Route failed");
    } finally {
      setBusy(false);
    }
  }

  async function onStatus(next: string) {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await requestsApi.update(id, { status: next });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status update failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRequestInfo(event: FormEvent) {
    event.preventDefault();
    if (!id || !infoMessage.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await routingApi.requestInformationForRequest(id, infoMessage.trim());
      setInfoMessage("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request information failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !request) {
    return <p className="text-red-700">{error}</p>;
  }
  if (!request) {
    return <p className="text-ink-700">Loading ticket…</p>;
  }

  const isRequester = user?.id === request.requester_id;
  const isDeptMember = Boolean(
    user?.department_id &&
      request.department_id &&
      user.department_id === request.department_id,
  );
  const canWorkTicket =
    isStaff ||
    (isDeptMember &&
      ["pending_assignment", "assigned", "in_progress", "resolved"].includes(request.status));
  const showStaffActions = isStaff || canWorkTicket;
  const showReviewActions = canReviewRoute && request.status === "pending_review";
  const showPersonAssign =
    canAssignPerson &&
    Boolean(request.department_id) &&
    ["pending_assignment", "assigned", "in_progress"].includes(request.status);
  const showWorkStatus =
    canWorkTicket &&
    ["pending_assignment", "assigned", "in_progress", "resolved"].includes(request.status);

  const deptName = (deptId: string | null) => {
    if (!deptId) return "—";
    const d = departments.find((x) => x.id === deptId);
    return d ? `${d.code} — ${d.name}` : deptId;
  };

  const commentsBlock = (
    <section className="border border-ink-900/10 bg-white/80 p-5">
      <h2 className="font-display text-lg font-semibold">Comments</h2>
      <ul className="mt-3 max-h-80 space-y-3 overflow-y-auto">
        {comments.length === 0 ? (
          <li className="text-sm text-ink-700">No comments yet. Start the thread below.</li>
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
      <form onSubmit={(e) => void onComment(e)} className="mt-4 border-t border-ink-900/10 pt-4">
        <label className="block text-sm">
          <span className="text-ink-700">Add a comment</span>
          <textarea
            className="mt-1 w-full border border-ink-900/15 px-3 py-2 text-sm"
            rows={3}
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Write a comment for the requester and handlers…"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !commentText.trim()}
          className="mt-2 bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          Post comment
        </button>
      </form>
    </section>
  );

  const actionsSidebar = showStaffActions ? (
    <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
      <section className="border border-ink-900/10 bg-white/90 p-4">
        <h2 className="font-display text-base font-semibold">Details</h2>
        <dl className="mt-3 space-y-3 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-700">Status</dt>
            <dd className="mt-1">
              <StatusBadge status={request.status} />
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-700">Priority</dt>
            <dd className="mt-0.5 font-medium capitalize">{request.priority}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-700">Department</dt>
            <dd className="mt-0.5 font-medium">{deptName(request.department_id)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-700">AI recommended</dt>
            <dd className="mt-0.5 font-medium">
              {analysis?.recommended_department_code || "—"}
              {analysis?.confidence != null
                ? ` · ${(analysis.confidence * 100).toFixed(0)}%`
                : ""}
              {analysis?.recommended_priority
                ? ` · priority ${analysis.recommended_priority}`
                : ""}
            </dd>
          </div>
          {openReview ? (
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-700">Review reason</dt>
              <dd className="mt-0.5 text-ink-900">{openReview.reason}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      {canSetPriority && !["closed", "cancelled"].includes(request.status) ? (
        <section className="border border-brand-600/30 bg-white/90 p-4">
          <h2 className="font-display text-base font-semibold">Priority</h2>
          <p className="mt-1 text-xs text-ink-700">
            AI sets the initial priority. Reviewers, admins, and managers can override it.
          </p>
          <form className="mt-3 space-y-3" onSubmit={(e) => void onSavePriority(e)}>
            <label className="block text-sm">
              <span className="text-ink-700">System priority</span>
              <select
                className="mt-1 w-full border border-ink-900/15 px-2 py-1.5 capitalize"
                value={editPriority}
                onChange={(e) => setEditPriority(e.target.value as RequestPriority)}
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              disabled={busy || editPriority === request.priority}
              className="w-full bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Update priority
            </button>
          </form>
        </section>
      ) : null}

      {showReviewActions ? (
        <section className="border border-brand-600/30 bg-white/90 p-4">
          <h2 className="font-display text-base font-semibold">Actions</h2>
          <p className="mt-1 text-xs text-ink-700">
            Assign a department, then optionally a member of that department (active users only).
          </p>
          <form className="mt-3 space-y-3" onSubmit={(e) => void onRouteDepartment(e)}>
            <label className="block text-sm">
              <span className="text-ink-700">Department</span>
              <select
                className="mt-1 w-full border border-ink-900/15 px-2 py-1.5"
                value={selectedDeptId}
                onChange={(e) => {
                  setSelectedDeptId(e.target.value);
                  setAssigneeId("");
                }}
                required
              >
                <option value="">Select department</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code} — {d.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-ink-700">Assignee (department member)</span>
              <select
                className="mt-1 w-full border border-ink-900/15 px-2 py-1.5"
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
                disabled={!selectedDeptId}
              >
                {!selectedDeptId ? (
                  <option value="">Select a department first</option>
                ) : deptMembers.length === 0 ? (
                  <option value="">No active members in this department</option>
                ) : (
                  <>
                    <option value="">Department only (assign person later)</option>
                    {deptMembers.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name} ({u.email})
                      </option>
                    ))}
                  </>
                )}
              </select>
            </label>
            <button
              type="submit"
              disabled={busy || !selectedDeptId}
              className="w-full bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {assigneeId ? "Assign department & person" : "Assign department"}
            </button>
          </form>
          <form className="mt-4 space-y-2 border-t border-ink-900/10 pt-3" onSubmit={(e) => void onRequestInfo(e)}>
            <label className="block text-sm">
              <span className="text-ink-700">Ask requester for information</span>
              <textarea
                className="mt-1 w-full border border-ink-900/15 px-2 py-1.5 text-sm"
                rows={2}
                value={infoMessage}
                onChange={(e) => setInfoMessage(e.target.value)}
                placeholder="What do you need clarified?"
              />
            </label>
            <button
              type="submit"
              disabled={busy || infoMessage.trim().length < 3}
              className="w-full border border-ink-900/20 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Request information
            </button>
          </form>
        </section>
      ) : null}

      {showPersonAssign ? (
        <section className="border border-brand-600/30 bg-white/90 p-4">
          <h2 className="font-display text-base font-semibold">Assign person</h2>
          <p className="mt-1 text-xs text-ink-700">
            Active users in this ticket&apos;s department only.
          </p>
          <form className="mt-3 space-y-3" onSubmit={(e) => void onAssignPerson(e)}>
            <label className="block text-sm">
              <span className="text-ink-700">Assignee</span>
              <select
                className="mt-1 w-full border border-ink-900/15 px-2 py-1.5"
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
              >
                {assignable.length === 0 ? (
                  <option value="">No assignable users</option>
                ) : (
                  assignable.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email})
                    </option>
                  ))
                )}
              </select>
            </label>
            <button
              type="submit"
              disabled={busy || !assigneeId}
              className="w-full bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {request.status === "pending_assignment" ? "Assign" : "Reassign"}
            </button>
          </form>
        </section>
      ) : null}

      {showWorkStatus ? (
        <section className="border border-ink-900/10 bg-white/90 p-4">
          <h2 className="font-display text-base font-semibold">Work ticket</h2>
          <p className="mt-1 text-xs text-ink-700">
            Department members can view and progress tickets routed to their team.
          </p>
          <div className="mt-3 flex flex-col gap-2">
            {request.status === "pending_assignment" && isDeptMember && user ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  void (async () => {
                    if (!id || !user) return;
                    setBusy(true);
                    setError(null);
                    try {
                      await requestsApi.assign(id, user.id, "Claimed by department member");
                      await requestsApi.update(id, { status: "in_progress" });
                      await load();
                    } catch (err) {
                      setError(err instanceof Error ? err.message : "Claim failed");
                    } finally {
                      setBusy(false);
                    }
                  })();
                }}
                className="bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                Claim & start
              </button>
            ) : null}
            {request.status === "assigned" ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void onStatus("in_progress")}
                className="bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                Start work
              </button>
            ) : null}
            {request.status === "in_progress" ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void onStatus("resolved")}
                className="bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                Mark resolved
              </button>
            ) : null}
            {request.status === "resolved" ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void onStatus("closed")}
                className="border border-ink-900/20 px-3 py-2 text-sm disabled:opacity-50"
              >
                Close ticket
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      {request.status === "draft" || request.status === "submitted" ? (
        <section className="border border-ink-900/10 bg-white/90 p-4">
          <h2 className="font-display text-base font-semibold">Lifecycle</h2>
          <div className="mt-3 flex flex-col gap-2">
            {request.status === "draft" ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void submitDraft()}
                className="bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                Submit
              </button>
            ) : null}
            <button
              type="button"
              disabled={busy}
              onClick={() => void cancelRequest()}
              className="border border-ink-900/20 px-3 py-2 text-sm disabled:opacity-60"
            >
              Cancel request
            </button>
          </div>
        </section>
      ) : null}
    </aside>
  ) : null;

  return (
    <div>
      <p className="mb-4 text-sm">
        <Link
          to={canReviewRoute ? "/app/review" : "/app"}
          className="text-brand-700 hover:underline"
        >
          ← {canReviewRoute ? "Review queue" : "My tickets"}
        </Link>
      </p>

      <div className={showStaffActions ? "grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]" : ""}>
        <div className="min-w-0 space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="font-display text-3xl font-semibold text-ink-900">{request.title}</h1>
              <p className="mt-2 text-sm text-ink-700">
                Updated {new Date(request.updated_at).toLocaleString()}
                {!showStaffActions ? ` · Priority: ${request.priority}` : ""}
              </p>
              {isRequester && !isStaff ? (
                <p className="mt-2 text-sm text-brand-700">
                  Ticket received. Status is shown below — use comments to talk with reviewers and
                  the assignee.
                </p>
              ) : null}
            </div>
            {!showStaffActions ? <StatusBadge status={request.status} /> : null}
          </div>

          {liveMode === "sse+poll" ? (
            <p className="border border-brand-500/20 bg-brand-50 px-3 py-2 text-sm text-brand-700">
              Live updates on ({analysisPending ? "waiting for AI analysis" : "status changes"}) —
              SSE with polling fallback.
            </p>
          ) : null}

          {error ? <p className="text-sm text-red-700">{error}</p> : null}

          <section className="border border-ink-900/10 bg-white/80 p-5">
            <h2 className="font-display text-lg font-semibold">Description</h2>
            {request.description_redacted ? (
              <p className="mt-2 border border-ink-900/10 bg-ink-50 px-3 py-2 text-sm text-ink-700">
                Confidential HR case content is only visible to HR and reviewers. You can still track
                status and use comments for updates.
              </p>
            ) : (
              <p className="mt-2 whitespace-pre-wrap text-ink-900">{request.description}</p>
            )}
          </section>

          {isStaff && (hasRole("hr") || hasRole("reviewer") || !request.is_hr_sensitive) ? (
            <section className="border border-ink-900/10 bg-white/80 p-5">
              <h2 className="font-display text-lg font-semibold">AI analysis</h2>
              {analysis ? (
                <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-ink-700">
                      Recommended department
                    </dt>
                    <dd className="font-medium">
                      {analysis.recommended_department_code || "— (uncertain)"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-ink-700">Confidence</dt>
                    <dd className="font-medium">
                      {analysis.confidence != null
                        ? `${(analysis.confidence * 100).toFixed(0)}%`
                        : "—"}
                    </dd>
                  </div>
                  {analysis.rationale ? (
                    <div className="sm:col-span-2">
                      <dt className="text-xs uppercase tracking-wide text-ink-700">Rationale</dt>
                      <dd className="mt-1 text-ink-900">{analysis.rationale}</dd>
                    </div>
                  ) : null}
                </dl>
              ) : (
                <p className="mt-2 text-sm text-ink-700">No analysis yet.</p>
              )}
            </section>
          ) : null}

          {commentsBlock}

          {isStaff && history.length > 0 ? (
            <section className="border border-ink-900/10 bg-white/80 p-5">
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

          {!showStaffActions ? (
            <section className="flex flex-wrap gap-3">
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
          ) : null}

          {request.status === "submitted" && isRequester ? (
            <form
              onSubmit={(e) => void onClarify(e)}
              className="border border-ink-900/10 bg-white/80 p-5"
            >
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
        </div>

        {actionsSidebar}
      </div>
    </div>
  );
}
