import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getCourse } from "../../../api/courses";
import { enrollInCourse } from "../../../api/enrollments";
import { Alert, Button, Card, CourseCover, EnrollmentBadge, FullPageSpinner, PriceTag } from "../../../components/ui";
import { useSession } from "../../../context/SessionContext";
import { useApiErrorText } from "../../../lib/apiErrorText";
import { ApiError } from "../../../lib/apiClient";
import type { Course, EnrollResult } from "../../../types/api";

/**
 * Course detail. Students enroll here: a free course activates immediately, a
 * paid course moves to pending payment and shows the teacher's payment
 * instructions plus a link to submit the claim. Teachers get a link to the
 * course manager.
 */
export function CourseDetailPage() {
  const { slug, user } = useSession();
  const params = useParams();
  const courseId = Number(params.courseId);
  const errorToText = useApiErrorText();

  const [course, setCourse] = useState<Course | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollResult, setEnrollResult] = useState<EnrollResult | null>(null);
  const [enrollError, setEnrollError] = useState<string | null>(null);

  const isTeacher = user?.role === "teacher";
  const isStudent = user?.role === "student";

  const load = useCallback(async () => {
    setLoading(true);
    setErrorText(null);
    try {
      setCourse(await getCourse(slug ?? "", courseId));
    } catch (error) {
      setErrorText(errorToText(error as ApiError, "تعذّر تحميل هذه الدورة."));
    } finally {
      setLoading(false);
    }
  }, [slug, courseId, errorToText]);

  useEffect(() => {
    void load();
  }, [load]);

  async function enroll() {
    setEnrolling(true);
    setEnrollError(null);
    try {
      const result = await enrollInCourse(slug ?? "", courseId);
      setEnrollResult(result);
      // Re-fetch so the visible enrollment_status matches the backend.
      await load();
    } catch (error) {
      setEnrollError(errorToText(error as ApiError, "تعذّر التسجيل في هذه الدورة."));
    } finally {
      setEnrolling(false);
    }
  }

  if (loading) {
    return <FullPageSpinner />;
  }

  if (!course) {
    return (
      <div className="text-center">
        <p className="font-bold text-ink">لم يتم العثور على الدورة</p>
        {errorText && <p className="mt-2 text-sm text-ink-secondary">{errorText}</p>}
        <Link to="/courses" className="mt-6 inline-block">
          <Button variant="secondary">العودة إلى الدورات</Button>
        </Link>
      </div>
    );
  }

  const isFree = course.price === "0.00" || course.price === "0";
  const activeEnrollment = course.enrollment_status === "active";
  const pendingPayment = course.enrollment_status === "pending_payment";

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-start gap-4">
        <CourseCover courseId={course.id} title={course.title} size={64} />
        <div>
          <h1 className="text-[26px] font-extrabold leading-[1.45] text-ink">{course.title}</h1>
          <div className="mt-2 flex items-center gap-3">
            <PriceTag price={course.price} className="text-lg" />
            {course.enrollment_status && <EnrollmentBadge status={course.enrollment_status} />}
          </div>
        </div>
      </div>

      <Card>
        <h2 className="text-sm font-bold text-ink-secondary">الوصف</h2>
        {course.description ? (
          <p className="mt-2 whitespace-pre-line leading-[2] text-ink">{course.description}</p>
        ) : (
          <p className="mt-2 text-sm text-ink-muted">لم يكتب المعلّم وصفًا لهذه الدورة.</p>
        )}
      </Card>

      <Card className="mt-4">
        {isTeacher && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink-secondary">هذه الدورة من دوراتك.</p>
            <Link to="/teacher/courses">
              <Button variant="secondary">تعديلها في إدارة الدورات</Button>
            </Link>
          </div>
        )}

        {isStudent && (
          <>
            {activeEnrollment && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-bold text-success">أنت مسجّل في هذه الدورة.</p>
                  <p className="mt-1 text-sm text-ink-secondary">يفتح محتوى الدورة في مرحلة لاحقة من المنصّة.</p>
                </div>
                <Link to="/my-enrollments">
                  <Button variant="secondary">تسجيلاتي</Button>
                </Link>
              </div>
            )}

            {pendingPayment && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-bold text-warn">بانتظار تأكيد الدفعة.</p>
                  <p className="mt-1 text-sm text-ink-secondary">قدّم إشعار الدفع من صفحة تسجيلاتك.</p>
                </div>
                <Link to="/my-enrollments">
                  <Button>تقديم إشعار الدفع</Button>
                </Link>
              </div>
            )}

            {!course.enrollment_status && enrollResult === null && (
              <div>
                <p className="text-sm leading-[1.8] text-ink-secondary">
                  {isFree
                    ? "الدورة مجانية — التسجيل فيها يُفعّل الوصول فورًا."
                    : "التسجيل في دورة بمقابل ينقلها إلى انتظار الدفع مع إظهار تعليمات الدفع."}
                </p>
                {enrollError && (
                  <div className="mt-3">
                    <Alert tone="error">{enrollError}</Alert>
                  </div>
                )}
                <Button className="mt-3" onClick={() => void enroll()} disabled={enrolling}>
                  {enrolling ? "جارٍ التسجيل..." : isFree ? "سجّل مجانًا" : "سجّل وتابع الدفع"}
                </Button>
              </div>
            )}

            {!course.enrollment_status && enrollResult !== null && (
              <div>
                <Alert tone="success">
                  {enrollResult.status === "active"
                    ? "أنت مسجّل في هذه الدورة الآن."
                    : "تم إنشاء التسجيل. أكمل الدفع بالتعليمات أدناه ليؤكّده المعلّم."}
                </Alert>
                {enrollResult.payment_instructions && (
                  <div className="mt-4 rounded-card bg-soft p-4">
                    <p className="text-xs font-bold uppercase tracking-wide text-ink-secondary">تعليمات الدفع</p>
                    <p className="mt-2 whitespace-pre-line text-sm leading-[1.8] text-ink">{enrollResult.payment_instructions}</p>
                  </div>
                )}
                {enrollResult.status === "pending_payment" && (
                  <Link to="/my-enrollments" className="mt-4 inline-block">
                    <Button>الذهاب إلى تسجيلاتي</Button>
                  </Link>
                )}
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
