import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useSession } from "../context/SessionContext";
import { FullPageSpinner } from "../components/ui";
import type { Role } from "../types/api";

/**
 * Route guards.
 *
 * The backend enforces every permission — these guards only give the user a
 * smooth experience (redirects instead of raw 401/403 error pages).
 */

/** Requires any signed-in workspace member; optionally restricted to roles. */
export function RequireAuth({ roles }: { roles?: Role[] }) {
  const { user, booting } = useSession();
  const location = useLocation();

  if (booting) {
    return <FullPageSpinner />;
  }

  if (!user) {
    return (
      <Navigate
        to={roles?.includes("teacher") ? "/teacher/login" : "/login"}
        state={{ from: location.pathname }}
        replace
      />
    );
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

/** Students must also be approved — pending/rejected accounts have no session, so RequireAuth with ["student"] is typically enough. This guard keeps future-proofing simple. */
export function RequireApprovedStudent() {
  const { user, booting } = useSession();
  const location = useLocation();

  if (booting) {
    return <FullPageSpinner />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  if (user.role !== "student" || user.approval_status !== "approved") {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
