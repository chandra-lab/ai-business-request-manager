import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { homePathForUser } from "../lib/roleRedirect";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("employee@aibrm.example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to={homePathForUser(user)} replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const me = await login(email.trim(), password);
      navigate(homePathForUser(me), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-10">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-brand-500/15 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-96 w-96 rounded-full bg-ink-900/10 blur-3xl" />
      </div>

      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <p className="font-display text-4xl font-bold tracking-tight text-brand-700">AIBRM</p>
          <p className="mt-2 text-sm text-ink-700">
            AI Business Request Manager — sign in to continue
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="border border-brand-700/10 bg-white/80 p-8 shadow-sm backdrop-blur"
        >
          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium text-ink-700">Email</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-ink-900/15 bg-white px-3 py-2 text-ink-900 outline-none ring-brand-500 focus:ring-2"
            />
          </label>

          <label className="mb-6 block">
            <span className="mb-1 block text-sm font-medium text-ink-700">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-ink-900/15 bg-white px-3 py-2 text-ink-900 outline-none ring-brand-500 focus:ring-2"
            />
          </label>

          {error ? (
            <p className="mb-4 text-sm text-red-700" role="alert">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-brand-600 px-4 py-2.5 font-display text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-60"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
