import { useEffect, useState, type FormEvent } from "react";
import { getAccessToken } from "../lib/storage";

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

interface Dept {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  manager_user_id: string | null;
}

interface UserBrief {
  id: string;
  email: string;
  full_name: string;
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function AdminDepartmentsPage() {
  const [items, setItems] = useState<Dept[]>([]);
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [managerId, setManagerId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editManagerId, setEditManagerId] = useState("");

  async function load() {
    const [deps, us] = await Promise.all([
      api<Dept[]>("/api/v1/departments"),
      api<UserBrief[]>("/api/v1/users"),
    ]);
    setItems(deps);
    setUsers(us);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, []);

  function userLabel(id: string | null): string {
    if (!id) return "";
    const u = users.find((x) => x.id === id);
    return u ? `${u.full_name} (${u.email})` : id;
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api<Dept>("/api/v1/departments", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          manager_user_id: managerId || null,
        }),
      });
      setName("");
      setDescription("");
      setManagerId("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(d: Dept) {
    setEditingId(d.id);
    setEditName(d.name);
    setEditDescription(d.description || "");
    setEditManagerId(d.manager_user_id || "");
    setError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditName("");
    setEditDescription("");
    setEditManagerId("");
  }

  async function saveEdit(departmentId: string) {
    if (!editName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api<Dept>(`/api/v1/departments/${departmentId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editName.trim(),
          description: editDescription.trim() || null,
          manager_user_id: editManagerId || null,
        }),
      });
      cancelEdit();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(d: Dept) {
    const next = !d.is_active;
    const verb = next ? "activate" : "deactivate";
    if (!window.confirm(`${verb} “${d.name}”? Inactive teams are excluded from new auto-routing.`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api<Dept>(`/api/v1/departments/${d.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: next }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status update failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(d: Dept) {
    const ok = window.confirm(
      `Delete “${d.name}”?\n\nIf any requests or assignments reference this team, it will be soft-deleted (set inactive) so history stays visible. Otherwise it is removed permanently.`,
    );
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await api<{ deletion: string }>(`/api/v1/departments/${d.id}`, {
        method: "DELETE",
      });
      if (editingId === d.id) cancelEdit();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-8">
        <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Admin</p>
        <h1 className="font-display text-3xl font-semibold">Departments / teams</h1>
        <p className="mt-1 text-ink-700">
          Create and manage teams such as IT Support, Finance, Operations, HR Operations,
          Restricted HR Review, General Administration, or Manual Review. Inactive teams stay
          visible here but are not used for new auto-routing.
        </p>
      </div>

      <form
        onSubmit={(e) => void onCreate(e)}
        className="mb-8 border border-ink-900/10 bg-white/80 p-5"
      >
        <h2 className="font-display text-lg font-semibold">Create department</h2>
        <label className="mt-4 block text-sm">
          <span className="text-ink-700">Name (unique)</span>
          <input
            className="mt-1 w-full border border-ink-900/15 px-3 py-2"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. IT Support"
            required
            minLength={2}
          />
        </label>
        <label className="mt-3 block text-sm">
          <span className="text-ink-700">Description</span>
          <textarea
            className="mt-1 w-full border border-ink-900/15 px-3 py-2"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
          />
        </label>
        <label className="mt-3 block text-sm">
          <span className="text-ink-700">Manager (optional)</span>
          <select
            className="mt-1 w-full border border-ink-900/15 px-3 py-2"
            value={managerId}
            onChange={(e) => setManagerId(e.target.value)}
          >
            <option value="">None</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="mt-4 bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          Create
        </button>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      </form>

      <h2 className="mb-3 font-display text-lg font-semibold">Existing</h2>
      <ul className="divide-y divide-ink-900/10 border border-ink-900/10 bg-white/80">
        {items.map((d) => (
          <li key={d.id} className="px-4 py-3">
            {editingId === d.id ? (
              <div className="space-y-3">
                <label className="block text-sm">
                  <span className="text-ink-700">Name</span>
                  <input
                    className="mt-1 w-full border border-ink-900/15 px-3 py-2"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    minLength={2}
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-ink-700">Description</span>
                  <textarea
                    className="mt-1 w-full border border-ink-900/15 px-3 py-2"
                    rows={2}
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-ink-700">Manager</span>
                  <select
                    className="mt-1 w-full border border-ink-900/15 px-3 py-2"
                    value={editManagerId}
                    onChange={(e) => setEditManagerId(e.target.value)}
                  >
                    <option value="">None</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name} ({u.email})
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy || !editName.trim()}
                    onClick={() => void saveEdit(d.id)}
                    className="bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={cancelEdit}
                    className="border border-ink-900/20 px-3 py-1.5 text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">
                      {d.name}{" "}
                      <span className="text-xs font-normal text-ink-700">({d.code})</span>
                    </p>
                    {d.description ? (
                      <p className="text-sm text-ink-700">{d.description}</p>
                    ) : null}
                    <p className="text-xs text-ink-700">
                      {d.is_active ? "active" : "inactive"}
                      {d.manager_user_id ? ` · manager ${userLabel(d.manager_user_id)}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => startEdit(d)}
                      className="border border-ink-900/20 px-3 py-1.5 text-sm"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void toggleActive(d)}
                      className="border border-ink-900/20 px-3 py-1.5 text-sm"
                    >
                      {d.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onDelete(d)}
                      className="border border-red-700/40 px-3 py-1.5 text-sm text-red-800"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
