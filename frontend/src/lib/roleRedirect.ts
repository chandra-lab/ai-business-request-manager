import type { UserMe } from "../types/auth";

/** Route users to the most relevant Phase 6 dashboard for their roles. */
export function homePathForUser(user: UserMe): string {
  const roles = new Set(user.roles);
  if (roles.has("hr")) return "/app/hr";
  if (roles.has("reviewer")) return "/app/review";
  if (roles.has("department_manager")) return "/app/department";
  if (roles.has("admin")) return "/app";
  return "/app";
}
