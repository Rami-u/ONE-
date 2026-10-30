import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { setStaffPassword, startStaffPasswordReset } from "../../api/staffAuth";
import { Alert, Button, Card, FieldError, Input, Label } from "../../components/ui";
import { useSession } from "../../context/SessionContext";
import { useApiErrorText } from "../../lib/apiErrorText";
import { ApiError } from "../../lib/apiClient";

/**
 * Destination of the invitation / staff password-reset email. The link opens
 * /teacher/set-password/?uid=<uid>&token=<token>; both are submitted to the
 * staff set-password endpoint with the chosen new password.
 *
 * Without uid/token in the URL the page becomes the "forgot password" entry
 * point: it sends POST /staff/auth/password-reset/ for a typed email. The
 * answer is always generic, so it does not reveal whether the email exists.
 */
export function TeacherSetPasswordPage() {
  const { slug, workspace } = useSession();
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");
  const errorToText = useApiErrorText();

  const missingLink = !uid || !token;

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [errorText, setErrorText] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const passwordsMismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    setFieldErrors({});
    try {
      await setStaffPassword(slug ?? "", uid as string, token as string, newPassword);
      setDone(true);
    } catch (error) {
      const apiError = error as ApiError;
      setFieldErrors(apiError.fieldErrors ?? {});
      setErrorText(errorToText(apiError, "رابط كلمة المرور غير صالح أو منتهي."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-landing text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-[1160px] items-center px-6">
          <Link to="/" className="text-lg font-extrabold text-ink">
            {workspace?.name ?? "مساحة المعلّم"}
          </Link>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[420px] flex-1 flex-col justify-center px-6 py-12">
        <h1 className="text-[30px] font-extrabold leading-[1.4] text-ink">
          {missingLink ? "استعادة كلمة المرور" : "تعيين كلمة المرور"}
        </h1>
        <p className="text-sm leading-[1.8] text-ink-secondary">
          {missingLink ? "نسيت كلمة المرور؟ أدخل بريدك لإرسال رابط استعادة." : "اختر كلمة المرور الخاصة بحسابك كمعلّم."}
        </p>

        <Card className="mt-6 shadow-elevated">
          {done && (
            <div>
              <Alert tone="success">تم تعيين كلمة المرور بنجاح.</Alert>
              <p className="mt-4 text-center text-sm text-ink-secondary">
                <Link to="/teacher/login" className="font-semibold text-accent hover:underline">
                  الانتقال إلى صفحة دخول المعلّمين
                </Link>
              </p>
            </div>
          )}

          {!done && missingLink && <RequestResetForm slug={slug ?? ""} />}

          {!done && !missingLink && (
            <>
              {errorText && (
                <div className="mb-4">
                  <Alert tone="error">{errorText}</Alert>
                </div>
              )}

              <form className="space-y-4" onSubmit={submit}>
                <div>
                  <Label htmlFor="set-new-password">كلمة المرور الجديدة</Label>
                  <div className="relative">
                    <Input
                      id="set-new-password"
                      type={showPassword ? "text" : "password"}
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      required
                      invalid={Boolean(fieldErrors.new_password)}
                      aria-describedby={fieldErrors.new_password ? "set-new-password-error" : undefined}
                    />
                    <button
                      type="button"
                      className="absolute inset-y-0 end-2 my-auto h-8 rounded-control px-2 text-xs font-semibold text-accent hover:underline"
                      onClick={() => setShowPassword((value) => !value)}
                      aria-label={showPassword ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
                    >
                      {showPassword ? "إخفاء" : "إظهار"}
                    </button>
                  </div>
                  <span id="set-new-password-error">
                    <FieldError messages={fieldErrors.new_password} />
                  </span>
                </div>
                <div>
                  <Label htmlFor="set-confirm-password">تأكيد كلمة المرور</Label>
                  <Input
                    id="set-confirm-password"
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    required
                  />
                  {passwordsMismatch && <p className="mt-1 text-sm font-medium text-err-form">كلمتا المرور غير متطابقتين.</p>}
                </div>
                <Button type="submit" className="w-full" disabled={submitting || passwordsMismatch}>
                  {submitting ? "جارٍ الحفظ..." : "تعيين كلمة المرور"}
                </Button>
              </form>
            </>
          )}
        </Card>
      </main>
    </div>
  );
}

/* ---------- Forgot-password entry point (page opened without uid/token) ---------- */

function RequestResetForm({ slug }: { slug: string }) {
  const errorToText = useApiErrorText();
  const [email, setEmail] = useState("");
  const [sentDetail, setSentDetail] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    try {
      const response = await startStaffPasswordReset(slug, email);
      setSentDetail(response.detail);
    } catch (error) {
      setErrorText(errorToText(error as ApiError, "تعذّر إرسال طلب الاستعادة."));
    } finally {
      setSubmitting(false);
    }
  }

  if (sentDetail !== null) {
    return (
      <>
        <Alert tone="success">{sentDetail}</Alert>
        <p className="mt-4 text-center text-sm text-ink-secondary">
          <Link to="/teacher/login" className="font-semibold text-accent hover:underline">
            العودة إلى صفحة دخول المعلّمين
          </Link>
        </p>
      </>
    );
  }

  return (
    <>
      {errorText && (
        <div className="mb-4">
          <Alert tone="error">{errorText}</Alert>
        </div>
      )}

      <p className="text-sm leading-[1.8] text-ink-secondary">
        إذا كان بريدك مسجّلًا كمعلّم في هذه المساحة، سنرسل إليه رابطًا لتعيين كلمة مرور جديدة.
      </p>

      <form className="mt-4 space-y-4" onSubmit={submit}>
        <div>
          <Label htmlFor="reset-email">البريد الإلكتروني</Label>
          <Input
            id="reset-email"
            type="email"
            dir="ltr"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "جارٍ الإرسال..." : "إرسال رابط الاستعادة"}
        </Button>
      </form>

      <p className="mt-4 text-center text-sm text-ink-secondary">
        <Link to="/teacher/login" className="font-semibold text-accent hover:underline">
          العودة إلى صفحة دخول المعلّمين
        </Link>
      </p>
    </>
  );
}
