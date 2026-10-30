import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { loginStaff } from "../../api/staffAuth";
import { getMe } from "../../api/studentAuth";
import { Alert, Button, Card, Input, Label } from "../../components/ui";
import { ThemeToggle } from "../../components/ThemeToggle";
import { useSession } from "../../context/SessionContext";
import { useApiErrorText } from "../../lib/apiErrorText";
import { ApiError } from "../../lib/apiClient";

/**
 * Private teacher sign-in at /teacher/login — not linked from student pages,
 * keep it out of navigation. Students (and any non-teacher) get the same
 * generic failure as a wrong password.
 */
export function TeacherLoginPage() {
  const { slug, user, setUser, refreshWorkspace, workspace } = useSession();
  const navigate = useNavigate();
  const errorToText = useApiErrorText();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrorText(null);
    try {
      await loginStaff(slug ?? "", email, password);
      setUser(await getMe(slug ?? ""));
      void refreshWorkspace();
      navigate("/teacher/students", { replace: true });
    } catch (error) {
      setErrorText(errorToText(error as ApiError, "بيانات الدخول غير صحيحة."));
    } finally {
      setSubmitting(false);
    }
  }

  // Already signed in as the teacher of this space — go straight to the portal.
  if (user?.role === "teacher") {
    return <Navigate to="/teacher/students" replace />;
  }

  return (
    <div className="flex min-h-screen flex-col bg-page text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-[1160px] items-center justify-between px-6">
          <Link to="/" className="text-lg font-extrabold text-ink">
            {workspace?.name ?? "مساحة المعلّم"}
          </Link>
          <ThemeToggle compact />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[420px] flex-1 flex-col justify-center px-6 py-12">
        <h1 className="text-[30px] font-extrabold leading-[1.4] text-ink">دخول المعلّمين</h1>
        <p className="mt-1 text-sm leading-[1.8] text-ink-secondary">
          منطقة خاصة بالمعلّم — الطلاب يستخدمون صفحة الدخول العادية.
        </p>

        <Card className="mt-6 shadow-elevated">
          {errorText && (
            <div className="mb-4">
              <Alert tone="error">{errorText}</Alert>
            </div>
          )}

          <form className="space-y-4" onSubmit={submit}>
            <div>
              <Label htmlFor="staff-email">البريد الإلكتروني</Label>
              <Input
                id="staff-email"
                type="email"
                dir="ltr"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                invalid={Boolean(errorText)}
              />
            </div>
            <div>
              <Label htmlFor="staff-password">كلمة المرور</Label>
              <Input
                id="staff-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "جارٍ الدخول..." : "دخول"}
            </Button>
          </form>
        </Card>

        <p className="mt-4 text-center text-sm leading-[1.8] text-ink-secondary">
          استلمت دعوة إلى هذه المساحة؟ استخدم رابط «تعيين كلمة المرور» من بريدك، أو{" "}
          <Link to="/teacher/set-password" className="font-semibold text-accent hover:underline">
            استعد كلمة المرور
          </Link>
          .
        </p>
      </main>
    </div>
  );
}
