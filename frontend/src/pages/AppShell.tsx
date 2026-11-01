import { useAuth } from "../hooks/useAuth";

export function AppShell() {
  const { user, logout, hasRole } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="border-b border-ink-900/10 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <div>
            <p className="font-display text-xl font-bold text-brand-700">AIBRM</p>
            <p className="text-xs text-ink-700">Phase 1 foundation shell</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right text-sm">
              <p className="font-medium text-ink-900">{user?.full_name}</p>
              <p className="text-ink-700">{user?.roles.join(", ")}</p>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              className="border border-ink-900/20 px-3 py-1.5 text-sm hover:bg-ink-900/5"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-10">
        <h1 className="font-display text-3xl font-semibold text-ink-900">Welcome</h1>
        <p className="mt-2 max-w-2xl text-ink-700">
          You are authenticated. Role-based dashboards arrive in later phases. This shell
          confirms JWT login, <code className="text-sm">/me</code>, and protected routing.
        </p>

        <dl className="mt-8 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-700">Email</dt>
            <dd className="mt-1 font-medium">{user?.email}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-700">Primary role check</dt>
            <dd className="mt-1 font-medium">
              {hasRole("admin")
                ? "Admin"
                : hasRole("hr")
                  ? "HR"
                  : hasRole("reviewer")
                    ? "Reviewer"
                    : hasRole("department_manager")
                      ? "Department manager"
                      : "Employee"}
            </dd>
          </div>
        </dl>
      </main>
    </div>
  );
}
