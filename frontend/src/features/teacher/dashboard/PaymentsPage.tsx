import { useCallback, useEffect, useState } from "react";

import { confirmPayment, listPayments, paymentReceiptUrl, rejectPayment } from "../../../api/payments";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  FullPageSpinner,
  PageHeader,
  PaginationControls,
  PaymentBadge,
  Spinner,
  Textarea,
} from "../../../components/ui";
import { useSession } from "../../../context/SessionContext";
import { useApiErrorText } from "../../../lib/apiErrorText";
import { ApiError } from "../../../lib/apiClient";
import { formatDate, formatPrice } from "../../../lib/format";
import type { PaymentStatus, PaymentSubmission } from "../../../types/api";

const PAGE_SIZE = 20;
const STATUS_TABS: Array<{ value: PaymentStatus; label: string }> = [
  { value: "submitted", label: "بانتظار المراجعة" },
  { value: "confirmed", label: "مؤكّدة" },
  { value: "rejected", label: "مرفوضة" },
];

/**
 * Payment review (§7.7): submitted claims with receipt, note, and amount.
 * Confirming activates the enrollment (done by the backend in one
 * transaction). Rejecting requires a reason. Reviewing a claim twice returns
 * 409 — shown as conflict message.
 */
export function PaymentsReviewPage() {
  const { slug } = useSession();
  const errorToText = useApiErrorText();

  const [status, setStatus] = useState<PaymentStatus>("submitted");
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<PaymentSubmission[]>([]);
  const [count, setCount] = useState(0);
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [previousUrl, setPreviousUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);

  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectingClaim, setRejectingClaim] = useState<PaymentSubmission | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const load = useCallback(
    async (activeStatus: PaymentStatus, activePage: number) => {
      setLoading(true);
      setErrorText(null);
      try {
        const response = await listPayments(slug ?? "", activeStatus, activePage);
        setRows(response.results);
        setCount(response.count);
        setNextUrl(response.next);
        setPreviousUrl(response.previous);
      } catch (error) {
        setErrorText(errorToText(error as ApiError, "تعذّر تحميل المدفوعات."));
      } finally {
        setLoading(false);
      }
    },
    [slug, errorToText],
  );

  useEffect(() => {
    void load(status, page);
  }, [load, status, page]);

  async function confirm(claim: PaymentSubmission) {
    setBusyId(claim.id);
    setErrorText(null);
    try {
      await confirmPayment(slug ?? "", claim.id);
      await load(status, page);
    } catch (error) {
      const apiError = error as ApiError;
      setErrorText(apiError.status === 409 ? apiError.message : errorToText(apiError, "تعذّر تأكيد الدفعة."));
      if (apiError.status === 409) await load(status, page);
    } finally {
      setBusyId(null);
    }
  }

  async function reject(event: React.FormEvent) {
    event.preventDefault();
    if (!rejectingClaim || !rejectionReason.trim()) return;
    setBusyId(rejectingClaim.id);
    setErrorText(null);
    try {
      await rejectPayment(slug ?? "", rejectingClaim.id, rejectionReason.trim());
      setRejectingClaim(null);
      setRejectionReason("");
      await load(status, page);
    } catch (error) {
      const apiError = error as ApiError;
      setErrorText(apiError.status === 409 ? apiError.message : errorToText(apiError, "تعذّر رفض الدفعة."));
      if (apiError.status === 409) {
        setRejectingClaim(null);
        await load(status, page);
      }
    } finally {
      setBusyId(null);
    }
  }

  function openReceipt(paymentId: number) {
    // Same-origin, cookie-authenticated binary download — open in a new tab.
    window.open(paymentReceiptUrl(slug ?? "", paymentId), "_blank", "noopener");
  }

  function switchTab(next: PaymentStatus) {
    setStatus(next);
    setPage(1);
  }

  return (
    <div>
      <PageHeader title="المدفوعات" subtitle="راجع إشعارات الدفع اليدوية التي قدّمها طلابك." />

      {errorText && (
        <div className="mb-4">
          <Alert tone="error">{errorText}</Alert>
        </div>
      )}

      <div className="flex gap-2" role="tablist" aria-label="حالة الدفعات">
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
        <EmptyState title="لا توجد دفعات هنا" hint="تظهر الإشعارات عند قدّمها من قِبل الطلاب." />
      ) : (
        <ul className="mt-6 grid gap-3" aria-live="polite">
          {rows.map((claim) => (
            <li key={claim.id}>
              <Card className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-bold text-ink">{claim.course_title}</p>
                    <PaymentBadge status={claim.status} />
                  </div>
                  <p className="text-sm text-ink-secondary">
                    {claim.student_name} ·{" "}
                    <span dir="ltr" className="text-start">
                      {claim.student_email}
                    </span>
                  </p>
                  <p className="mt-1 text-sm font-semibold text-ink">
                    <span dir="ltr">{formatPrice(claim.amount)}</span> · {methodLabel(claim.method)} ·{" "}
                    {formatDate(claim.submitted_at)}
                  </p>
                  {claim.note && <p className="mt-2 text-sm leading-[1.8] text-ink">ملاحظة: {claim.note}</p>}
                  {claim.status === "rejected" && claim.rejection_reason && (
                    <p className="mt-2 text-sm font-medium text-err">سبب الرفض: {claim.rejection_reason}</p>
                  )}
                  {claim.status !== "submitted" && claim.reviewed_by_name && (
                    <p className="mt-1 text-xs text-ink-muted">تمت المراجعة بواسطة {claim.reviewed_by_name}</p>
                  )}
                </div>

                <div className="flex flex-col items-end gap-2">
                  {claim.has_receipt && (
                    <Button variant="secondary" onClick={() => openReceipt(claim.id)}>
                      عرض الإيصال
                    </Button>
                  )}
                  {claim.status === "submitted" && (
                    <div className="flex gap-2">
                      <Button onClick={() => void confirm(claim)} disabled={busyId === claim.id}>
                        {busyId === claim.id && (
                          <Spinner className="h-4 w-4 border-accent-contrast/40 border-t-accent-contrast" />
                        )}
                        تأكيد
                      </Button>
                      <Button variant="danger" onClick={() => setRejectingClaim(claim)} disabled={busyId === claim.id}>
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

      {rejectingClaim && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#173442]/50 px-4" role="dialog" aria-modal>
          <Card className="w-full max-w-md shadow-elevated">
            <h2 className="text-lg font-bold text-ink">رفض دفعة {rejectingClaim.student_name}</h2>
            <p className="mt-1 text-sm leading-[1.8] text-ink-secondary">
              يبقى التسجيل بانتظار الدفع، وسيرى الطالب سبب الرفض ويمكنه تقديم إشعار جديد.
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
                    setRejectingClaim(null);
                    setRejectionReason("");
                  }}
                >
                  إلغاء
                </Button>
                <Button type="submit" variant="danger" disabled={!rejectionReason.trim() || busyId !== null}>
                  رفض الإشعار
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}

const METHOD_LABELS: Record<string, string> = {
  transfer: "تحويل بنكي",
  e_wallet: "محفظة إلكترونية",
  cash: "نقدي",
  other: "أخرى",
};

function methodLabel(method: string): string {
  return METHOD_LABELS[method] ?? method;
}

/** Status filter tabs: active = teal fill, rest = quiet outlined controls (40px tall). */
function cnTab(active: boolean): string {
  const base =
    "h-10 rounded-control px-4 text-sm font-semibold transition-all duration-200 ease-[var(--ease-standard)] focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-accent";
  return active ? `${base} bg-accent text-accent-contrast` : `${base} border border-line bg-surface text-ink-secondary hover:bg-soft hover:text-ink`;
}
