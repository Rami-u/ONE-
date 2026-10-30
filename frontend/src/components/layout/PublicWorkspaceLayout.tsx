import { Link, Outlet } from "react-router-dom";

import { ThemeToggle } from "../ThemeToggle";
import { Button, Spinner, WorkspaceLogo } from "../ui";
import { useSession } from "../../context/SessionContext";

/**
 * Chrome for public workspace sub-domain pages (home, registration, login).
 * Same warm landing canvas as the main site; branding comes from the session context.
 */
export function PublicWorkspaceLayout() {
  const { workspace, user, booting } = useSession();

  if (booting) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-landing">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-landing text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-[1160px] items-center justify-between gap-4 px-6">
          <Link to="/" className="flex items-center gap-3">
            {workspace && <WorkspaceLogo src={workspace.logo} name={workspace.name} size={34} />}
            <span className="text-base font-bold text-ink">{workspace?.name ?? "مساحة المعلّم"}</span>
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle compact />
            {user ? (
              <>
                <Link to="/courses">
                  <Button variant="secondary">الدورات</Button>
                </Link>
                {user.role === "teacher" && (
                  <Link to="/teacher/students">
                    <Button>لوحة المعلّم</Button>
                  </Link>
                )}
              </>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="secondary">تسجيل الدخول</Button>
                </Link>
                <Link to="/signup">
                  <Button>إنشاء حساب</Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1160px] flex-1 px-6 py-10">
        <Outlet />
      </main>

      <footer className="border-t border-line bg-surface py-6 text-center text-xs text-ink-muted">
        مساحة تعلّم مستقلة على منصة وجهة
      </footer>
    </div>
  );
}
