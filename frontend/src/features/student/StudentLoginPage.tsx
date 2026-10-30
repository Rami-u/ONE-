import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { loginStudent } from "../../api/studentAuth";
import { Alert, Button, Card, Input, Label } from "../../components/ui";
import { useSession } from "../../context/SessionContext";
import { useApiErrorText } from "../../lib/apiErrorText";
import { ApiError } from "../../lib/apiClient";
import type { LoginStateError } from "../../types/api";

/**
 * Student login inside the teacher's space. Three account states are visible:
 * success (session starts), pending (approval message), and rejected (shows
 * the teacher's saved reason). The backend still decides everything.
 */
export function StudentLoginPage() {
  const { slug, setUser } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const errorToText = useApiErrorText();

  const from = (location.state as { from?: string } | null)?.from ?? "/courses";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [credentialsError, setCredentialsError] = useState<string | null>(null);
  const [stateError, setStateError] = useState<LoginStateError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setCredentialsError(null);
    setStateError(null);
    try {
      const me = await loginStudent(slug ?? "", email, password);
      setUser(me);
      navigate(from, { replace: true });
    } catch (error) {
      const apiError = error as ApiError;
      if (apiError.body && (apiError.body.code === "pending_approval" || apiError.body.code === "account_rejected")) {
        setStateError(apiError.body as unknown as LoginStateError);
      } else {
        setCredentialsError(errorToText(apiError, "بيانات الدخول غير صحيحة."));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-[30px] font-extrabold leading-[1.4] text-ink">تسجيل الدخول</h1>
      <p className="mt-1 text-sm leading-[1.8] text-ink-secondary">استخدم البريد الذي سجّلت به.</p>

      <Card className="mt-6 shadow-elevated">
        {stateError && (
          <div className="mb-4">
            <Alert tone={stateError.code === "account_rejected" ? "error" : "info"}>
              <p className="font-bold">{stateError.message}</p>
              {stateError.rejection_reason && <p className="mt-1 text-sm">سبب الرفض: {stateError.rejection_reason}</p>}
            </Alert>
          </div>
        )}

        {credentialsError && (
          <div className="mb-4">
            <Alert tone="error">{credentialsError}</Alert>
          </div>
        )}

        <form className="space-y-4" onSubmit={submit}>
          <div>
            <Label htmlFor="login-email">البريد الإلكتروني</Label>
            <Input
              id="login-email"
              type="email"
              dir="ltr"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              invalid={Boolean(credentialsError)}
            />
          </div>
          <div>
            <Label htmlFor="login-password">كلمة المرور</Label>
            <div className="relative">
              <Input
                id="login-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
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
          </div>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "جارٍ الدخول..." : "تسجيل الدخول"}
          </Button>
        </form>
      </Card>

      <div className="mt-4 flex items-center justify-between text-sm text-ink-secondary">
        <Link to="/reset-password" className="font-semibold text-accent hover:underline">
          نسيت كلمة المرور؟
        </Link>
        <Link to="/signup" className="font-semibold text-accent hover:underline">
          إنشاء حساب جديد
        </Link>
      </div>
    </div>
  );
}
