import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { ThemeToggle } from "../ThemeToggle";
import { Button, cn, motionFast } from "../ui";
import { useSession } from "../../context/SessionContext";
import type { Role } from "../../types/api";

/*
  Authenticated portal shell: fixed right-side navigation (246px, 222px at
  ≤1200px), content region, and a compact top bar. At ≤760px the sidebar
  becomes a drawer. dir="rtl" on <html> puts the first flex child on the
  physical right automatically.
*/

export function DashboardLayout() {
  const { user, signOut } = useSession();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isTeacher = user?.role === ("teacher" satisfies Role);

  const links = isTeacher
    ? [
        { to: "/teacher/students", label: "الطلاب" },
        { to: "/teacher/courses", label: "الدورات" },
        { to: "/teacher/payments", label: "المدفوعات" },
        { to: "/teacher/settings", label: "الإعدادات" },
      ]
    : [
        { to: "/courses", label: "الدورات" },
        { to: "/my-enrollments", label: "تسجيلاتي" },
      ];

  async function handleSignOut() {
    setDrawerOpen(false);
    await signOut();
    navigate("/");
  }

  return (
    <div className="flex min-h-screen bg-page text-ink">
      {/* Mobile drawer backdrop */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#173442]/50 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 start-0 z-40 flex w-[246px] max-[1200px]:w-[222px] flex-col border-e border-line bg-surface px-3 py-4 transition-transform duration-250 ease-[var(--ease-standard)]",
          "md:static md:shrink-0 md:translate-x-0",
          // On narrow screens the drawer slides out of view to the physical right.
          drawerOpen ? "translate-x-0" : "max-[760px]:translate-x-full",
        )}
        aria-label="التنقّل الرئيسي"
      >
        <div className="flex items-center justify-between px-2">
          <span className="text-lg font-extrabold text-ink">وجهة</span>
          <span className="truncate rounded-pill bg-soft px-2 py-0.5 text-[10px] font-semibold text-ink-secondary">
            {user?.workspace.slug}
          </span>
        </div>

        <nav className="mt-4 flex flex-col gap-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={() => setDrawerOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex h-10 items-center rounded-control px-3 text-sm font-medium transition-colors",
                  motionFast,
                  isActive
                    ? "bg-accent-soft text-accent"
                    : "text-ink-secondary hover:bg-soft hover:text-ink",
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-2 border-t border-line pt-3 px-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-semibold text-ink">{user?.full_name}</span>
            {isTeacher && (
              <span className="shrink-0 rounded-pill bg-accent-soft px-2 py-0.5 text-[10px] font-bold text-accent">معلّم</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle compact />
            <Button variant="secondary" size="sm" className="flex-1" onClick={() => void handleSignOut()}>
              تسجيل الخروج
            </Button>
          </div>
        </div>
      </aside>

      {/* Content region */}
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        {/* Top bar: hamburger + workspace name + theme on narrow screens */}
        <div className="flex h-14 items-center gap-3 border-b border-line bg-surface px-4 md:hidden">
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-control border border-line text-ink"
            aria-expanded={drawerOpen}
            aria-label={drawerOpen ? "إغلاق القائمة" : "فتح القائمة"}
            onClick={() => setDrawerOpen((open) => !open)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" className="h-5 w-5" aria-hidden>
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <span className="truncate text-sm font-bold text-ink">{user?.workspace.name}</span>
        </div>

        <main className="mx-auto w-full max-w-[1800px] flex-1 px-4 py-5 md:px-[39px] md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
