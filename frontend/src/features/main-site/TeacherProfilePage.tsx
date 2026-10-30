import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getPublicTeacherProfile } from "../../api/public";
import { Button, Card, FullPageSpinner, PriceTag, WorkspaceLogo } from "../../components/ui";
import { useApiErrorText } from "../../lib/apiErrorText";
import { ApiError } from "../../lib/apiClient";
import { subdomainUrl } from "../../lib/slug";
import type { PublicTeacherProfile } from "../../types/api";

/**
 * Main-domain teacher profile: who the teacher is and what they teach.
 * The registration/login buttons are plain links to that teacher's sub-domain —
 * no token or session is carried over.
 */
export function TeacherProfilePage() {
  const { slug = "" } = useParams();
  const [profile, setProfile] = useState<PublicTeacherProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);
  const errorToText = useApiErrorText();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErrorText(null);
      try {
        const response = await getPublicTeacherProfile(slug);
        if (!cancelled) setProfile(response);
      } catch (error) {
        if (!cancelled) setErrorText(errorToText(error as ApiError, "تعذّر تحميل صفحة هذا المعلّم."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, errorToText]);

  if (loading) {
    return <FullPageSpinner />;
  }

  if (!profile) {
    return (
      <div className="text-center">
        <p className="text-lg font-bold text-ink">لم يتم العثور على المعلّم</p>
        <p className="mt-2 text-sm text-ink-secondary">{errorText ?? "هذا المعلّم غير مُدرج في الدليل."}</p>
        <Link to="/teachers" className="mt-6 inline-block">
          <Button variant="secondary">العودة إلى الدليل</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Card className="flex items-start gap-5">
        <WorkspaceLogo src={profile.logo} name={profile.name} size={72} />
        <div>
          <h1 className="text-[clamp(29px,3vw,35px)] font-extrabold leading-[1.4] text-ink">{profile.name}</h1>
          {profile.teacher_name && (
            <p className="text-sm text-ink-secondary">
              المعلّم: <span className="font-semibold text-ink">{profile.teacher_name}</span>
            </p>
          )}
          {profile.headline && <p className="mt-2 leading-[1.8] text-ink">{profile.headline}</p>}
        </div>
      </Card>

      {profile.bio && (
        <Card className="mt-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-secondary">نبذة</h2>
          <p className="mt-2 whitespace-pre-line text-[15px] leading-[1.8] text-ink">{profile.bio}</p>
        </Card>
      )}

      {profile.about && (
        <Card className="mt-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-secondary">عن المعلّم</h2>
          <p className="mt-2 whitespace-pre-line text-[15px] leading-[1.8] text-ink">{profile.about}</p>
        </Card>
      )}

      <section className="mt-8">
        <h2 className="text-2xl font-bold leading-[1.5] text-ink">الدورات</h2>
        {profile.courses.length === 0 ? (
          <p className="mt-3 text-sm text-ink-secondary">لا توجد دورات منشورة بعد.</p>
        ) : (
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {profile.courses.map((course) => (
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
        <a href={subdomainUrl(profile.slug, "/signup")}>
          <Button size="lg">سجّل مع هذا المعلّم</Button>
        </a>
        <a href={subdomainUrl(profile.slug, "/login")}>
          <Button variant="secondary" size="lg">تسجيل الدخول</Button>
        </a>
      </div>
    </div>
  );
}
