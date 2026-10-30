import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listPublicTeachers } from "../../api/public";
import { FullPageSpinner, Input, PaginationControls, WorkspaceLogo } from "../../components/ui";
import { useApiErrorText } from "../../lib/apiErrorText";
import { ApiError } from "../../lib/apiClient";
import type { PublicTeacherDirectoryEntry } from "../../types/api";

/** Teacher directory on the main site: listed and active workspaces only, searchable and paginated. */

const PAGE_SIZE = 20;

export function TeacherDirectoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const searchTerm = searchParams.get("search") ?? "";
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const [entries, setEntries] = useState<PublicTeacherDirectoryEntry[]>([]);
  const [count, setCount] = useState(0);
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [previousUrl, setPreviousUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState(searchTerm);

  const errorToText = useApiErrorText();

  const setPageData = useCallback((response: Awaited<ReturnType<typeof listPublicTeachers>>) => {
    setEntries(response.results);
    setCount(response.count);
    setNextUrl(response.next);
    setPreviousUrl(response.previous);
  }, []);

  const load = useCallback(
    async (activeSearch: string, activePage: number) => {
      setLoading(true);
      setErrorText(null);
      try {
        const response = await listPublicTeachers({ search: activeSearch || undefined, page: activePage });
        setPageData(response);
      } catch (error) {
        setErrorText(errorToText(error as ApiError, "تعذّر تحميل دليل المعلّمين."));
      } finally {
        setLoading(false);
      }
    },
    [errorToText, setPageData],
  );

  useEffect(() => {
    void load(searchTerm, page);
  }, [load, searchTerm, page]);

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    setSearchParams(searchInput ? { search: searchInput } : {});
  }

  return (
    <div>
      <h1 className="text-[clamp(31px,3vw,35px)] font-bold leading-[1.5] text-ink">دليل المعلّمين</h1>
      <p className="mt-2 text-sm leading-[1.8] text-ink-secondary">
        لكل معلّم أدناه مساحة تعلّم مستقلة على عنوانه الخاص.
      </p>

      <form onSubmit={submitSearch} className="mt-6 flex max-w-md gap-2">
        <Input
          type="search"
          placeholder="ابحث باسم المعلّم..."
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          aria-label="البحث في دليل المعلّمين"
        />
        <button
          type="submit"
          className="h-10 shrink-0 rounded-control bg-accent px-4 text-sm font-semibold text-accent-contrast transition-opacity hover:opacity-90"
        >
          بحث
        </button>
      </form>

      {errorText && <p className="mt-6 text-sm text-err">{errorText}</p>}

      {loading ? (
        <FullPageSpinner />
      ) : (
        <>
          <ul
            className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
            aria-live="polite"
            aria-label="نتائج دليل المعلّمين"
          >
            {entries.map((entry) => (
              <li key={entry.slug}>
                <Link
                  to={`/teachers/${entry.slug}`}
                  className="block h-full rounded-card border border-line bg-surface p-5 transition-all duration-200 ease-[var(--ease-standard)] hover:-translate-y-1 hover:shadow-card focus-visible:-translate-y-1 focus-visible:shadow-card"
                >
                  <div className="flex items-start gap-3">
                    <WorkspaceLogo src={entry.logo} name={entry.name} size={46} />
                    <div className="min-w-0">
                      <p className="font-bold text-ink">{entry.name}</p>
                      {entry.teacher_name && <p className="text-sm text-ink-secondary">{entry.teacher_name}</p>}
                    </div>
                  </div>
                  {entry.headline && <p className="mt-3 line-clamp-2 text-sm leading-[1.8] text-ink-secondary">{entry.headline}</p>}
                  <span dir="ltr" className="mt-3 block text-[10px] text-ink-muted">
                    {entry.slug}
                  </span>
                </Link>
              </li>
            ))}
          </ul>

          {entries.length === 0 && !errorText && (
            <p className="mt-10 text-center text-sm text-ink-secondary">لا توجد نتائج مطابقة.</p>
          )}

          <PaginationControls
            page={page}
            count={count}
            pageSize={PAGE_SIZE}
            hasPrevious={previousUrl !== null && page > 1}
            hasNext={nextUrl !== null}
            onPrevious={() => setSearchParams({ ...(searchTerm ? { search: searchTerm } : {}), page: String(page - 1) })}
            onNext={() => setSearchParams({ ...(searchTerm ? { search: searchTerm } : {}), page: String(page + 1) })}
          />
        </>
      )}
    </div>
  );
}
