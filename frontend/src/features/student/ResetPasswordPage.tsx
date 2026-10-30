import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { confirmStudentPasswordReset, startStudentPasswordReset } from "../../api/studentAuth";
import { Alert, Button, Card, FieldError, Input, Label } from "../../components/ui";
import { useSession } from "../../context/SessionContext";
import { useApiErrorText } from "../../lib/apiErrorText";
import { ApiError } from "../../lib/apiClient";

/**
 * Password reset for students — one route handles both steps:
 *  - without uid/token in the URL: ask for the email and send the link
 *  - with uid/token (the emailed link points here): set the new password
 */
export function ResetPasswordPage() {
  const { slug } = useSession();
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const hasToken = Boolean(uid && token);
  const errorToText = useApiErrorText();

  const [email, setEmail] = useState("");
  const [sentMessage, setSentMessage] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [errorText, setErrorText] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const passwordsMismatch = useMemo(
    () => confirmPassword.length > 0 && newPassword !== confirmPassword,
    [newPassword, confirmPassword],
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    setFieldErrors({});
    try {
      if (hasToken) {
        await confirmStudentPasswordReset(slug ?? "", uid as string, token as string, newPassword);
        setDone(true);
      } else {
        const response = await startStudentPasswordReset(slug ?? "", email);
        setSentMessage(response.detail);
      }
    } catch (error) {
      const apiError = error as ApiError;
      setFieldErrors(apiError.fieldErrors ?? {});
      setErrorText(errorToText(apiError, "رابط كلمة المرور غير صالح أو منتهي."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-[30px] font-extrabold leading-[1.4] text-ink">
        {hasToken ? "تعيين كلمة المرور الجديدة" : "استعادة كلمة المرور"}
      </h1>

      <Card className="mt-6 shadow-elevated">
        {!hasToken && sentMessage && (
          <div className="mb-4">
            <Alert tone="success">{sentMessage}</Alert>
          </div>
        )}

        {hasToken && done && (
          <div>
            <Alert tone="success">تم تعيين كلمة المرور بنجاح.</Alert>
            <p className="mt-4 text-center text-sm text-ink-secondary">
              <Link to="/login" className="font-semibold text-accent hover:underline">
                سجّل الدخول بكلمة المرور الجديدة
              </Link>
            </p>
          </div>
        )}

        {!(hasToken && done) && (
          <>
            {errorText && (
              <div className="mb-4">
                <Alert tone="error">{errorText}</Alert>
              </div>
            )}

            <form className="space-y-4" onSubmit={submit}>
              {!hasToken && (
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
              )}
              {hasToken && (
                <>
                  <div>
                    <Label htmlFor="reset-password">كلمة المرور الجديدة</Label>
                    <div className="relative">
                      <Input
                        id="reset-password"
                        type={showPassword ? "text" : "password"}
                        value={newPassword}
                        onChange={(event) => setNewPassword(event.target.value)}
                        required
                        invalid={Boolean(fieldErrors.new_password)}
                        aria-describedby={fieldErrors.new_password ? "reset-password-error" : undefined}
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
                    <span id="reset-password-error">
                      <FieldError messages={fieldErrors.new_password} />
                    </span>
                  </div>
                  <div>
                    <Label htmlFor="reset-confirm">تأكيد كلمة المرور</Label>
                    <Input
                      id="reset-confirm"
                      type={showPassword ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      required
                    />
                    {passwordsMismatch && <p className="mt-1 text-sm font-medium text-err-form">كلمتا المرور غير متطابقتين.</p>}
                  </div>
                </>
              )}
              <Button type="submit" className="w-full" disabled={submitting || passwordsMismatch}>
                {submitting ? "جارٍ العمل..." : hasToken ? "تعيين كلمة المرور" : "إرسال رابط الاستعادة"}
              </Button>
            </form>
          </>
        )}
      </Card>

      {!hasToken && sentMessage && (
        <p className="mt-4 text-center text-sm text-ink-secondary">
          <Link to="/login" className="font-semibold text-accent hover:underline">
            العودة إلى تسجيل الدخول
          </Link>
        </p>
      )}
    </div>
  );
}
