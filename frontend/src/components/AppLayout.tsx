import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function AppLayout() {
  const { user, logout, hasRole } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="border-b border-ink-900/10 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-6">
            <Link to="/app" className="font-display text-xl font-bold text-brand-700">
              AIBRM
            </Link>
            <nav className="flex flex-wrap gap-4 text-sm text-ink-700">
              <Link className="hover:text-brand-700" to="/app">
                Dashboard
              </Link>
              <Link className="hover:text-brand-700" to="/app/requests/new">
                New request
              </Link>
              {hasRole("reviewer", "admin") ? (
                <Link className="hover:text-brand-700" to="/app/review">
                  Review queue
                </Link>
              ) : null}
              {hasRole("department_manager", "admin") ? (
                <Link className="hover:text-brand-700" to="/app/manager">
                  Manager queue
                </Link>
              ) : null}
            </nav>
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
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
