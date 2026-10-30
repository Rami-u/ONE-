import { useState } from "react";
import { Link } from "react-router-dom";

import { registerStudent } from "../../api/studentAuth";
import { Alert, Button, Card, FieldError, Input, Label } from "../../components/ui";
import { useSession } from "../../context/SessionContext";
import { useApiErrorText } from "../../lib/apiErrorText";
import { ApiError } from "../../lib/apiClient";

/** Student registration inside the teacher's space — creates a pending account; no session is issued. */
export function SignupPage() {
  const { slug } = useSession();
  const errorToText = useApiErrorText();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [errorText, setErrorText] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    setFieldErrors({});
    try {
      const response = await registerStudent(slug ?? "", { email, full_name: fullName, password, phone: phone || null });
      setSuccessMessage(response.message);
    } catch (error) {
      const apiError = error as ApiError;
      setFieldErrors(apiError.fieldErrors ?? {});
      setErrorText(errorToText(apiError, "تعذّر إنشاء الحساب."));
    } finally {
      setSubmitting(false);
    }
  }

  if (!successMessage) {
    return (
      <div className="mx-auto max-w-[420px]">
        <h1 className="text-[30px] font-extrabold leading-[1.4] text-ink">أنشئ حسابك</h1>
        <p className="mt-1 text-sm leading-[1.8] text-ink-secondary">
          التسجيل في مساحة هذا المعلّم، ويبدأ الدخول بعد موافقته على حسابك.
        </p>

        <Card className="mt-6 shadow-elevated">
          {errorText && (
            <div className="mb-4">
              <Alert tone="error">{errorText}</Alert>
            </div>
          )}

          <form className="space-y-4" onSubmit={submit}>
            <div>
              <Label htmlFor="signup-name">الاسم الكامل</Label>
              <Input
                id="signup-name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
                invalid={Boolean(fieldErrors.full_name)}
                aria-describedby={fieldErrors.full_name ? "signup-name-error" : undefined}
              />
              <span id="signup-name-error">
                <FieldError messages={fieldErrors.full_name} />
              </span>
            </div>
            <div>
              <Label htmlFor="signup-email">البريد الإلكتروني</Label>
              <Input
                id="signup-email"
                type="email"
                dir="ltr"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                invalid={Boolean(fieldErrors.email)}
                aria-describedby={fieldErrors.email ? "signup-email-error" : undefined}
              />
              <span id="signup-email-error">
                <FieldError messages={fieldErrors.email} />
              </span>
            </div>
            <div>
              <Label htmlFor="signup-phone">رقم الهاتف (اختياري)</Label>
              <Input
                id="signup-phone"
                type="tel"
                dir="ltr"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                invalid={Boolean(fieldErrors.phone)}
                aria-describedby={fieldErrors.phone ? "signup-phone-error" : undefined}
              />
              <span id="signup-phone-error">
                <FieldError messages={fieldErrors.phone} />
              </span>
            </div>
            <div>
              <Label htmlFor="signup-password">كلمة المرور</Label>
              <div className="relative">
                <Input
                  id="signup-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  invalid={Boolean(fieldErrors.password)}
                  aria-describedby={fieldErrors.password ? "signup-password-error" : undefined}
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
              <span id="signup-password-error">
                <FieldError messages={fieldErrors.password} />
              </span>
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "جارٍ الإرسال..." : "إنشاء الحساب"}
            </Button>
          </form>
        </Card>

        <p className="mt-4 text-center text-sm text-ink-secondary">
          لديك حساب مقبول بالفعل؟{" "}
          <Link to="/login" className="font-semibold text-accent hover:underline">
            تسجيل الدخول
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <Card className="text-center shadow-elevated">
        <h1 className="text-xl font-extrabold text-ink">بانتظار موافقة المعلّم</h1>
        <p className="mt-2 text-sm leading-[1.8] text-ink-secondary">
          وصلنا طلبك بنجاح. يمكنك تسجيل الدخول بعد أن يقبل المعلّم حسابك، وستظهر لك حالة الطلب عند محاولة الدخول.
        </p>
        <Link to="/" className="mt-6 inline-block">
          <Button variant="secondary">العودة إلى الصفحة الرئيسية</Button>
        </Link>
      </Card>
    </div>
  );
}
