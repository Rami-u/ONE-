import { Link, Outlet, useLocation } from "react-router-dom";

import { ThemeToggle } from "../ThemeToggle";
import { Button } from "../ui";

/**
 * Chrome for the main-domain marketing pages (وجهة landing, teacher directory, profiles).
 * Warm canvas: #fcfcf9. Nav links point at the landing sections and the directory;
 * the header CTA stays outlined so the landing hero's filled button stays primary.
 */

const NAV_LINKS = [
  { href: "/teachers", label: "المعلّمون" },
  { href: "/#how", label: "كيف تبدأ" },
  { href: "/#faq", label: "الأسئلة الشائعة" },
];

export function MainSiteLayout() {
  const location = useLocation();

  return (
    <div className="flex min-h-screen flex-col bg-landing text-ink overflow-x-clip">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-[1160px] items-center justify-between gap-4 px-6">
          <Link to="/" className="flex items-center gap-2" aria-label="وجهة — الصفحة الرئيسية">
            <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-control bg-accent text-base font-extrabold text-accent-contrast">
              و
            </span>
            <span className="text-xl font-extrabold tracking-normal text-ink">وجهة</span>
          </Link>
          <nav className="hidden items-center gap-7 text-sm font-medium text-ink-secondary sm:flex" aria-label="التنقل الرئيسي">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className={
                  link.href === "/teachers" && isCurrent(location.pathname, "/teachers")
                    ? "text-accent"
                    : "transition-colors hover:text-ink"
                }
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link to="/teachers">
              <Button variant="secondary" size="md">
                اختر معلّمك
                <span aria-hidden>←</span>
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1160px] flex-1 px-6 py-10">
        <Outlet />
      </main>

      <footer className="mt-auto border-t border-line bg-surface py-8">
        <div className="mx-auto flex max-w-[1160px] flex-wrap items-center justify-between gap-4 px-6">
          <div className="flex items-center gap-3">
            <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-control bg-accent text-base font-extrabold text-accent-contrast">
              و
            </span>
            <p className="text-sm leading-[1.7] text-ink-secondary">
              <span className="font-extrabold text-ink">وجهة</span> — آفاق أوسع للمعرفة، وتجربة عربية تُرافق رحلتك.
            </p>
          </div>
          <div className="text-xs leading-[1.7] text-ink-muted">
            <p>نموذج تفاعلي — البيانات تُجلب من الواجهة الخلفية.</p>
            <p>
              الصورة:{" "}
              <a
                href="https://unsplash.com/photos/man-wearing-headphones-while-sitting-on-chair-in-front-of-macbook-4-EeTnaC1S4"
                target="_blank"
                rel="noreferrer"
                className="underline decoration-line underline-offset-2 transition-colors hover:text-ink"
              >
                Wes Hicks / Unsplash
              </a>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function isCurrent(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
