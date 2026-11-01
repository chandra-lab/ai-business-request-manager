import type { UserMe } from "../types/auth";

/** Phase 1 stub — later phases route to role-specific dashboards. */
export function homePathForUser(user: UserMe): string {
  const roles = new Set(user.roles);
  if (roles.has("admin")) return "/app";
  if (roles.has("hr")) return "/app";
  if (roles.has("reviewer")) return "/app";
  if (roles.has("department_manager")) return "/app";
  return "/app";
}
