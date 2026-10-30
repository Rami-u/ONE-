import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listMyEnrollments } from "../../../api/enrollments";
import { submitPaymentClaim } from "../../../api/payments";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  EnrollmentBadge,
  FieldError,
  FullPageSpinner,
  Input,
  Label,
  PageHeader,
  Select,
  Spinner,
  Textarea,
} from "../../../components/ui";
import { useSession } from "../../../context/SessionContext";
import { useApiErrorText } from "../../../lib/apiErrorText";
import { ApiError } from "../../../lib/apiClient";
import { formatDate, formatPrice } from "../../../lib/format";
import type { Enrollment } from "../../../types/api";

const PAYMENT_METHODS = [
  { value: "transfer", label: "تحويل بنكي" },
  { value: "e_wallet", label: "محفظة إلكترونية" },
  { value: "cash", label: "نقدي" },
  { value: "other", label: "أخرى" },
];

const MAX_NOTE_LENGTH = 1000;
/** Receipt rules mirrored from the backend validator: JPEG/PNG/PDF, at most 5 MB. */
const RECEIPT_MAX_BYTES = 5 * 1024 * 1024;
const RECEIPT_TYPES = ["image/jpeg", "image/png", "application/pdf"];

/**
 * The student's enrollments. Paid enrollments that are still pending payment
 * show the claim form: method, optional note, optional receipt.
 * The enrollment stays pending payment until the teacher confirms the claim.
 */
export function MyEnrollmentsPage() {
  const { slug } = useSession();
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);
  const errorToText = useApiErrorText();

  /** Enrollments where the student already submitted a claim in this visit. */
  const [claimedEnrollmentIds, setClaimedEnrollmentIds] = useState<number[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setErrorText(null);
    try {
      setEnrollments(await listMyEnrollments(slug ?? ""));
    } catch (error) {
      setErrorText(errorToText(error as ApiError, "تعذّر تحميل تسجيلاتك."));
    } finally {
      setLoading(false);
    }
  }, [slug, errorToText]);

  useEffect(() => {
    void load();
  }, [load]);

  function markClaimed(id: number) {
    setClaimedEnrollmentIds((previous) => [...previous, id]);
  }

  return (
    <div>
      <PageHeader
        title="تسجيلاتي"
        subtitle="الدورات المجانية تكون نشطة فورًا. دورات المقابل تحتاج تأكيد المعلّم لإشعار الدفع."
      />

      {errorText && <p className="text-sm text-err">{errorText}</p>}

      {loading ? (
        <FullPageSpinner />
      ) : enrollments.length === 0 ? (
        <EmptyState title="لا توجد تسجيلات بعد" hint="استعرض مكتبة الدورات واختر دورة للبدء." />
      ) : (
        <ul className="grid gap-4">
          {enrollments.map((enrollment) => (
            <li key={enrollment.id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Link
                      to={`/courses/${enrollment.course_id}`}
                      className="font-bold text-ink transition-colors hover:text-accent"
                    >
                      {enrollment.course_title}
                    </Link>
                    <p className="mt-1 text-xs text-ink-muted">
                      مسجّل{" "}
                      <span dir="ltr" className="font-medium">
                        {formatDate(enrollment.created_at)}
                      </span>{" "}
                      · <span dir="ltr">{formatPrice(enrollment.price_at_enrollment)}</span>
                      {enrollment.activated_at && ` · تفعيل ${formatDate(enrollment.activated_at)}`}
                    </p>
                  </div>
                  <EnrollmentBadge status={enrollment.status} />
                </div>

                {enrollment.status === "active" && (
                  <p className="mt-3 text-sm font-medium text-success">
                    الوصول نشط. يفتح محتوى الدورة في مرحلة لاحقة من المنصّة.
                  </p>
                )}

                {enrollment.status === "withdrawn" && (
                  <p className="mt-3 text-sm text-ink-secondary">تم سحب هذا التسجيل.</p>
                )}

                {enrollment.status === "pending_payment" && !claimedEnrollmentIds.includes(enrollment.id) && (
                  <PaymentClaimForm
                    slug={slug ?? ""}
                    enrollmentId={enrollment.id}
                    onClaimed={() => markClaimed(enrollment.id)}
                    onReload={load}
                  />
                )}

                {enrollment.status === "pending_payment" && claimedEnrollmentIds.includes(enrollment.id) && (
                  <Alert tone="info">
                    <p className="font-bold">تم إرسال إشعار الدفع.</p>
                    <p className="mt-1">
                      إشعارك بانتظار مراجعة المعلّم، ويبقى التسجيل «بانتظار الدفع» حتى يؤكّده.
                    </p>
                  </Alert>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ---------- Payment claim form for one pending enrollment ---------- */

function PaymentClaimForm({
  slug,
  enrollmentId,
  onClaimed,
  onReload,
}: {
  slug: string;
  enrollmentId: number;
  onClaimed: () => void;
  onReload: () => Promise<void>;
}) {
  const [method, setMethod] = useState("transfer");
  const [note, setNote] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);
  const [receiptError, setReceiptError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const errorToText = useApiErrorText();

  function chooseReceipt(file: File | null) {
    setReceiptError(null);
    if (!file) {
      setReceipt(null);
      return;
    }
    if (!RECEIPT_TYPES.includes(file.type)) {
      setReceiptError("يجب أن يكون الإيصال ملف JPEG أو PNG أو PDF.");
      setReceipt(null);
      return;
    }
    if (file.size > RECEIPT_MAX_BYTES) {
      setReceiptError("يجب ألا يتجاوز الإيصال 5 ميغابايت.");
      setReceipt(null);
      return;
    }
    setReceipt(file);
  }

  async function submitClaim(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await submitPaymentClaim(slug, enrollmentId, { method, note: note || null, receipt });
      onClaimed();
      await onReload();
    } catch (error) {
      const apiError = error as ApiError;
      if (apiError.status === 409) {
        setFormError(apiError.message);
      } else {
        setFormError(errorToText(apiError, "تعذّر إرسال إشعار الدفع."));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      className="mt-4 rounded-card border border-[color:color-mix(in_srgb,var(--warning-fg)_40%,transparent)] bg-warn-bg/60 p-4"
      onSubmit={(event) => void submitClaim(event)}
    >
      <p className="font-bold text-warn">قدّم إشعار دفعك</p>
      <p className="mt-1 text-xs leading-[1.8] text-ink-secondary">
        بعد الدفع خارج المنصّة، أخبر المعلّم بطريقة الدفع وأرفق الإيصال إن وجد.
      </p>

      {formError && (
        <div className="mt-3">
          <Alert tone="error">{formError}</Alert>
        </div>
      )}

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor={`claim-method-${enrollmentId}`}>طريقة الدفع</Label>
          <Select id={`claim-method-${enrollmentId}`} value={method} onChange={(event) => setMethod(event.target.value)}>
            {PAYMENT_METHODS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor={`claim-receipt-${enrollmentId}`}>الإيصال (JPEG أو PNG أو PDF — حتى 5 ميغابايت)</Label>
          <Input
            id={`claim-receipt-${enrollmentId}`}
            type="file"
            accept="image/jpeg,image/png,application/pdf"
            onChange={(event) => chooseReceipt(event.target.files?.[0] ?? null)}
            invalid={Boolean(receiptError)}
          />
          <FieldError messages={receiptError ? [receiptError] : undefined} />
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor={`claim-note-${enrollmentId}`}>ملاحظة للمعلّم (اختياري)</Label>
          <Textarea
            id={`claim-note-${enrollmentId}`}
            rows={2}
            maxLength={MAX_NOTE_LENGTH}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="مثال: رقم مرجع التحويل 12345"
          />
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <Button type="submit" disabled={submitting}>
          {submitting && <Spinner className="h-4 w-4 border-accent-contrast/40 border-t-accent-contrast" />}
          {submitting ? "جارٍ الإرسال..." : "إرسال الإشعار"}
        </Button>
        <span className="text-xs text-ink-muted">يُتفعّل التسجيل بعد تأكيد المعلّم.</span>
      </div>
    </form>
  );
}
