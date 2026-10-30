import { Link } from "react-router-dom";

import { Button } from "../../components/ui";

/** Generic page-not-found on the main domain (or the workspace). */
export function NotFoundPage() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <p className="text-5xl font-extrabold text-line" aria-hidden>
        ٤٠٤
      </p>
      <p className="mt-4 font-bold text-ink">الصفحة غير موجودة</p>
      <p className="mt-1 text-sm text-ink-secondary">الصفحة التي تبحث عنها غير متاحة.</p>
      <Link to="/" className="mt-6">
        <Button variant="secondary">العودة إلى الصفحة الرئيسية</Button>
      </Link>
    </div>
  );
}
