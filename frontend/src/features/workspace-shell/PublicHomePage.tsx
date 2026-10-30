import { Link } from "react-router-dom";

import { Button, Card, PriceTag, FullPageSpinner, WorkspaceLogo } from "../../components/ui";
import { useSession } from "../../context/SessionContext";

/**
 * Home of a teacher's sub-domain: identity and published courses from the
 * public-profile endpoint. Signed-out visitors see registration CTAs,
 * signed-in members see links to their portal.
 */
export function PublicHomePage() {
  const { publicProfile, user, booting } = useSession();

  if (booting) {
    return <FullPageSpinner />;
  }

  if (!publicProfile) {
    return (
      <div className="text-center">
        <h1 className="text-[clamp(29px,3vw,35px)] font-extrabold text-ink">مرحبًا بك</h1>
        <p className="mt-2 text-sm text-ink-secondary">سجّل الدخول أو أنشئ حسابك للبدء.</p>
        <div className="mt-6 flex justify-center gap-3">
          <Link to="/signup">
            <Button>إنشاء حساب</Button>
          </Link>
          <Link to="/login">
            <Button variant="secondary">تسجيل الدخول</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Card className="flex items-start gap-5">
        <WorkspaceLogo src={publicProfile.logo} name={publicProfile.name} size={72} />
        <div>
          <h1 className="text-[clamp(29px,3vw,35px)] font-extrabold leading-[1.4] text-ink">{publicProfile.name}</h1>
          {publicProfile.teacher_name && (
            <p className="text-sm text-ink-secondary">
              المعلّم: <span className="font-semibold text-ink">{publicProfile.teacher_name}</span>
            </p>
          )}
          {publicProfile.headline && <p className="mt-2 leading-[1.8] text-ink">{publicProfile.headline}</p>}
        </div>
      </Card>

      {publicProfile.bio && (
        <Card className="mt-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-secondary">نبذة</h2>
          <p className="mt-2 whitespace-pre-line text-[15px] leading-[1.8] text-ink">{publicProfile.bio}</p>
        </Card>
      )}

      {publicProfile.about && (
        <Card className="mt-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-secondary">عن المعلّم</h2>
          <p className="mt-2 whitespace-pre-line text-[15px] leading-[1.8] text-ink">{publicProfile.about}</p>
        </Card>
      )}

      <section className="mt-8">
        <h2 className="text-2xl font-bold leading-[1.5] text-ink">الدورات</h2>
        {!user && <p className="mt-1 text-sm text-ink-secondary">سجّل في مساحة هذا المعلّم لتتمكن من التسجيل في دورة.</p>}
        {publicProfile.courses.length === 0 ? (
          <p className="mt-3 text-sm text-ink-secondary">لا توجد دورات منشورة بعد.</p>
        ) : (
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {publicProfile.courses.map((course) => (
              <li
                key={course.id}
                className="flex items-start gap-4 rounded-card border border-line bg-surface p-4 transition-all duration-200 ease-[var(--ease-standard)] hover:-translate-y-1 hover:shadow-card"
              >
                <div className="min-w-0">
                  <p className="font-bold text-ink">{course.title}</p>
                  {course.description && <p className="mt-1 line-clamp-2 text-sm leading-[1.8] text-ink-secondary">{course.description}</p>}
                </div>
                <PriceTag price={course.price} className="ms-auto shrink-0" />
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="mt-8 flex justify-center gap-3">
        {user ? (
          <Link to="/courses">
            <Button size="lg">اذهب إلى دوراتي</Button>
          </Link>
        ) : (
          <>
            <Link to="/signup">
              <Button size="lg">إنشاء حساب</Button>
            </Link>
            <Link to="/login">
              <Button variant="secondary" size="lg">تسجيل الدخول</Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
