import { useCallback, useEffect, useState } from "react";

import { approveStudent, listWorkspaceStudents, rejectStudent } from "../../../api/studentReview";
import {
  Alert,
  ApprovalBadge,
  Button,
  Card,
  FullPageSpinner,
  PageHeader,
  PaginationControls,
  Spinner,
  Textarea,
} from "../../../components/ui";
import { useSession } from "../../../context/SessionContext";
import { useApiErrorText } from "../../../lib/apiErrorText";
import { ApiError } from "../../../lib/apiClient";
import { formatDate } from "../../../lib/format";
import type { ApprovalStatus, StudentReviewEntry } from "../../../types/api";

const PAGE_SIZE = 20;
const STATUS_TABS: Array<{ value: ApprovalStatus; label: string }> = [
  { value: "pending", label: "بالانتظار" },
  { value: "approved", label: "مقبولون" },
  { value: "rejected", label: "مرفوضون" },
];

/**
 * Student review (§7.5): list students by approval status, approve or reject
 * (reject requires a reason). Approved/rejected students cannot be reviewed
 * again — the backend answers 409 and this page shows the message.
 */
export function StudentsReviewPage() {
  const { slug } = useSession();
  const errorToText = useApiErrorText();

  const [status, setStatus] = useState<ApprovalStatus>("pending");
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<StudentReviewEntry[]>([]);
  const [count, setCount] = useState(0);
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [previousUrl, setPreviousUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);

  const [rejectingStudent, setRejectingStudent] = useState<StudentReviewEntry | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [busyStudentId, setBusyStudentId] = useState<number | null>(null);

  const load = useCallback(
    async (activeStatus: ApprovalStatus, activePage: number) => {
      setLoading(true);
      setErrorText(null);
      try {
        const response = await listWorkspaceStudents(slug ?? "", activeStatus, activePage);
        setRows(response.results);
        setCount(response.count);
        setNextUrl(response.next);
        setPreviousUrl(response.previous);
      } catch (error) {
        setErrorText(errorToText(error as ApiError, "تعذّر تحميل الطلاب."));
      } finally {
        setLoading(false);
      }
    },
    [slug, errorToText],
  );

  useEffect(() => {
    void load(status, page);
  }, [load, status, page]);

  async function approve(student: StudentReviewEntry) {
    setBusyStudentId(student.id);
    setErrorText(null);
    try {
      await approveStudent(slug ?? "", student.id);
      await load(status, page);
    } catch (error) {
      setErrorText(errorToText(error as ApiError, "تعذّر قبول هذا الطالب."));
    } finally {
      setBusyStudentId(null);
    }
  }

  async function reject(event: React.FormEvent) {
    event.preventDefault();
    if (!rejectingStudent || !rejectionReason.trim()) return;
    setBusyStudentId(rejectingStudent.id);
    setErrorText(null);
    try {
      await rejectStudent(slug ?? "", rejectingStudent.id, rejectionReason.trim());
      setRejectingStudent(null);
      setRejectionReason("");
      await load(status, page);
    } catch (error) {
      setErrorText(errorToText(error as ApiError, "تعذّر رفض هذا الطالب."));
    } finally {
      setBusyStudentId(null);
    }
  }

  function switchTab(next: ApprovalStatus) {
    setStatus(next);
    setPage(1);
  }

  return (
    <div>
      <PageHeader
        title="الطلاب"
        subtitle="راجع طلبات التسجيل وأدر وصول الطلاب إلى مساحتك."
      />

      {errorText && (
        <div className="mb-4">
          <Alert tone="error">{errorText}</Alert>
        </div>
      )}

      <div className="flex gap-2" role="tablist" aria-label="حالة الطلاب">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => switchTab(tab.value)}
            className={cnTab(status === tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <FullPageSpinner />
      ) : rows.length === 0 ? (
        <p className="mt-8 text-center text-sm text-ink-secondary">لا يوجد طلاب بهذه الحالة.</p>
      ) : (
        <ul className="mt-6 grid gap-3" aria-live="polite">
          {rows.map((student) => (
            <li key={student.id}>
              <Card className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-bold text-ink">{student.full_name}</p>
                  <p dir="ltr" className="text-start text-sm text-ink-secondary">
                    {student.email}
                  </p>
                  {student.phone && (
                    <p dir="ltr" className="text-start text-xs text-ink-muted">
                      {student.phone}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-ink-muted">
                    سُجّل {formatDate(student.date_joined)}
                    {student.reviewed_at && ` · تمت المراجعة ${formatDate(student.reviewed_at)}`}
                  </p>
                  {student.approval_status === "rejected" && student.rejection_reason && (
                    <p className="mt-2 text-sm font-medium text-err">السبب: {student.rejection_reason}</p>
                  )}
                </div>

                <div className="flex flex-col items-end gap-2">
                  <ApprovalBadge status={student.approval_status} />
                  {student.approval_status === "pending" && (
                    <div className="flex gap-2">
                      <Button onClick={() => void approve(student)} disabled={busyStudentId === student.id}>
                        {busyStudentId === student.id && (
                          <Spinner className="h-4 w-4 border-accent-contrast/40 border-t-accent-contrast" />
                        )}
                        قبول
                      </Button>
                      <Button variant="danger" onClick={() => setRejectingStudent(student)} disabled={busyStudentId === student.id}>
                        رفض
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {(nextUrl || previousUrl) && (
        <PaginationControls
          page={page}
          count={count}
          pageSize={PAGE_SIZE}
          hasPrevious={page > 1}
          hasNext={nextUrl !== null}
          onPrevious={() => setPage((current) => Math.max(1, current - 1))}
          onNext={() => setPage((current) => current + 1)}
        />
      )}

      {rejectingStudent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#173442]/50 px-4" role="dialog" aria-modal>
          <Card className="w-full max-w-md shadow-elevated">
            <h2 className="text-lg font-bold text-ink">رفض الطالب {rejectingStudent.full_name}</h2>
            <p className="mt-1 text-sm leading-[1.8] text-ink-secondary">
              سيرى الطالب هذا السبب عند محاولته الدخول. يُحفظ الحساب ولا يمكن التسجيل مرة أخرى بنفس البريد.
            </p>
            <form className="mt-4" onSubmit={reject}>
              <Textarea
                rows={4}
                maxLength={1000}
                autoFocus
                value={rejectionReason}
                onChange={(event) => setRejectionReason(event.target.value)}
                placeholder="سبب الرفض (مطلوب)"
                required
              />
              <div className="mt-3 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setRejectingStudent(null);
                    setRejectionReason("");
                  }}
                >
                  إلغاء
                </Button>
                <Button type="submit" variant="danger" disabled={submittingDisabled()}>
                  رفض الطالب
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );

  function submittingDisabled(): boolean {
    return !rejectionReason.trim() || busyStudentId !== null;
  }
}

/** Status filter tabs: active = teal fill, rest = quiet outlined controls (40px tall). */
function cnTab(active: boolean): string {
  const base =
    "h-10 rounded-control px-4 text-sm font-semibold transition-all duration-200 ease-[var(--ease-standard)] focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-accent";
  return active ? `${base} bg-accent text-accent-contrast` : `${base} border border-line bg-surface text-ink-secondary hover:bg-soft hover:text-ink`;
}
