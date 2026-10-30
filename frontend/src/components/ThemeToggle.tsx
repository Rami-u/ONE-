import { useCallback, useEffect, useState } from "react";

/**
 * Theme switch (sun/moon) — follows the system preference until the user
 * picks a mode; stores the choice locally and syncs it between open tabs.
 * The initial value comes from the inline script in index.html.
 */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains("dark"));

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === "wajha-theme" && event.newValue) {
        document.documentElement.classList.toggle("dark", event.newValue === "dark");
        setIsDark(event.newValue === "dark");
      }
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggle = useCallback(() => {
    const next = !isDark;
    document.documentElement.classList.toggle("dark", next);
    document.documentElement.style.colorScheme = next ? "dark" : "light";
    try {
      localStorage.setItem("wajha-theme", next ? "dark" : "light");
    } catch {
      /* storage unavailable — choice lives for this tab only */
    }
    setIsDark(next);
  }, [isDark]);

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? "التبديل إلى الوضع الفاتح" : "التبديل إلى الوضع الداكن"}
      aria-pressed={isDark}
      className={`inline-flex items-center gap-1.5 rounded-control border border-line bg-surface px-2.5 text-ink transition-colors duration-200 hover:bg-soft ${
        compact ? "h-9" : "h-10"
      }`}
    >
      {/* Sun / moon glyphs; decorative icons duplicated as a text label for accessibility below. */}
      {isDark ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" className="h-[18px] w-[18px] shrink-0" aria-hidden>
          <circle cx="12" cy="12" r="4.5" />
          <path d="M12 3v2.2M12 18.8V21M4.2 12H2M22 12h-2.2M6.3 6.3 4.8 4.8M19.2 19.2l-1.5-1.5M17.7 6.3l1.5-1.5M4.8 19.2l1.5-1.5" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" className="h-[18px] w-[18px] shrink-0" aria-hidden>
          <path d="M20.6 14.2A8.3 8.3 0 0 1 9.8 3.4a8.4 8.4 0 1 0 10.8 10.8Z" />
        </svg>
      )}
      {!compact && <span className="text-xs font-medium">{isDark ? "فاتح" : "داكن"}</span>}
    </button>
  );
}
