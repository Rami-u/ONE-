import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listCourses } from "../../../api/courses";
import { CourseCover, EnrollmentBadge, EmptyState, FullPageSpinner, PageHeader, PriceTag } from "../../../components/ui";
import { useSession } from "../../../context/SessionContext";
import { useApiErrorText } from "../../../lib/apiErrorText";
import { ApiError } from "../../../lib/apiClient";
import type { Course } from "../../../types/api";

/** Course list for approved students (with their enrollment status) and teachers. */
export function StudentCoursesPage() {
  const { slug, user } = useSession();
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);
  const errorToText = useApiErrorText();

  const isTeacher = user?.role === "teacher";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErrorText(null);
      try {
        const courses = await listCourses(slug ?? "");
        if (!cancelled) setCourses(courses);
      } catch (error) {
        if (!cancelled) setErrorText(errorToText(error as ApiError, "تعذّر تحميل الدورات."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, errorToText]);

  if (loading) {
    return <FullPageSpinner />;
  }

  return (
    <div>
      <PageHeader
        title={isTeacher ? "الدورات" : "مكتبة الدورات"}
        subtitle={isTeacher ? "جميع دوراتك بما فيها المسوّدات." : "استعرض الدورات المنشورة وسجّل فيها."}
      />

      {errorText && <p className="text-sm text-err">{errorText}</p>}

      {courses.length === 0 ? (
        <EmptyState
          title="لا توجد دورات بعد"
          hint={isTeacher ? "أنشئ أول دورة من تبويب الدورات." : "لم ينشر المعلّم أي دورة بعد."}
        />
      ) : (
        <ul
          className="grid gap-4 max-[1200px]:grid-cols-2 max-[480px]:grid-cols-1 md:grid-cols-3"
          aria-live="polite"
        >
          {courses.map((course) => (
            <li key={course.id}>
              <Link to={`/courses/${course.id}`} className="block h-full">
                <div className="flex h-full flex-col rounded-card border border-line bg-surface p-5 transition-all duration-200 ease-[var(--ease-standard)] hover:-translate-y-1 hover:shadow-card focus-visible:-translate-y-1 focus-visible:shadow-card">
                  <div className="flex items-start gap-3">
                    <CourseCover courseId={course.id} title={course.title} />
                    <h3 className="min-w-0 font-bold text-ink">{course.title}</h3>
                  </div>
                  {course.description && <p className="mt-3 line-clamp-3 text-sm leading-[1.8] text-ink-secondary">{course.description}</p>}
                  <div className="mt-3 flex items-center gap-2 border-t border-line pt-3 mt-auto">
                    {course.enrollment_status ? (
                      <EnrollmentBadge status={course.enrollment_status} />
                    ) : isTeacher && !course.is_published ? (
                      <span className="inline-flex items-center rounded-full bg-soft px-2.5 py-0.5 text-xs font-semibold text-ink-secondary border border-line">مسوّدة</span>
                    ) : null}
                    <PriceTag price={course.price} className="ms-auto" />
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
