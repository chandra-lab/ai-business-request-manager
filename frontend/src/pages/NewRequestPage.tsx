import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { requestsApi } from "../api/requests";

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function NewRequestPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitNow, setSubmitNow] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const created = await requestsApi.create(
        {
          title: title.trim(),
          description: description.trim(),
          submit: submitNow,
        },
        newIdempotencyKey(),
      );
      if (file) {
        await requestsApi.upload(created.id, file);
      }
      navigate(`/app/requests/${created.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create request");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="font-display text-3xl font-semibold text-ink-900">New request</h1>
      <p className="mt-1 text-ink-700">
        Describe what you need. AI will recommend routing and priority after you submit.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-5 border border-ink-900/10 bg-white/80 p-6">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-ink-700">Title</span>
          <input
            required
            minLength={3}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full border border-ink-900/15 px-3 py-2 outline-none ring-brand-500 focus:ring-2"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-ink-700">Description</span>
          <textarea
            required
            minLength={10}
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full border border-ink-900/15 px-3 py-2 outline-none ring-brand-500 focus:ring-2"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-ink-700">Attachment (optional)</span>
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm"
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={submitNow}
            onChange={(e) => setSubmitNow(e.target.checked)}
          />
          Submit now (unchecked saves as draft)
        </label>

        {error ? (
          <p className="text-sm text-red-700" role="alert">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={saving}
          className="bg-brand-600 px-4 py-2.5 font-display text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {saving ? "Saving…" : submitNow ? "Submit request" : "Save draft"}
        </button>
      </form>
    </div>
  );
}
