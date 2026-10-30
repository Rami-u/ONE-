import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { listPublicTeachers } from "../../api/public";
import { Button, FullPageSpinner, Input, Select } from "../../components/ui";
import { subdomainUrl } from "../../lib/slug";
import type { PublicTeacherDirectoryEntry } from "../../types/api";

/*
  وجهة landing (per the approved design):
  1. Hero with the photo composition and floating cards
  2. Feature strip
  3. Teacher preview cards (real directory data, client-side filters)
  4. Steps band
  5. FAQ accordion
  6. Dark closing CTA
  Copy stays truthful to what the product actually does today.
*/

const TILES = ["teal", "blue", "sand", "purple"] as const;
type TileKey = (typeof TILES)[number];

function tileFor(slug: string): TileKey {
  let hash = 0;
  for (const ch of slug) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return TILES[hash % TILES.length];
}

function toArabicDigits(value: number | string): string {
  return String(value).replace(/[0-9]/g, (d) => "٠١٢٣٤٥٦٧٨٩"[Number(d)]);
}

/** Client-side category filter: matches the keyword against the workspace text. */
const CATEGORIES: { label: string; keywords: string[] }[] = [
  { label: "الكل", keywords: [] },
  { label: "التصميم", keywords: ["تصميم"] },
  { label: "البرمجة", keywords: ["برمجة", "برمجيات", "كود"] },
  { label: "الرياضيات", keywords: ["رياضيات", "جبر", "تفاضل"] },
  { label: "اللغات", keywords: ["لغة", "لغات", "إنجليزي", "عربي"] },
  { label: "الأعمال", keywords: ["أعمال", "إدارة", "مشاريع"] },
  { label: "تحليل البيانات", keywords: ["بيانات", "تحليل", "إحصاء"] },
  { label: "العلوم", keywords: ["علوم", "فيزياء", "كيمياء", "أحياء"] },
  { label: "الهوايات", keywords: ["هوايات", "موسيقى", "رسم", "خط"] },
  { label: "المهارات المهنية", keywords: ["مهارات", "مهني"] },
];

const FEATURE_STRIP = [
  { label: "معلمون مختصون", icon: "book" },
  { label: "مساحة خاصة لكل معلّم", icon: "grid" },
  { label: "تعلّم مباشر مع معلّمك", icon: "person" },
  { label: "تقدّم مستقر مع كل معلّم", icon: "chart" },
] as const;

const STEPS = [
  {
    title: "اختر معلّمك",
    body: "استعرض دليل المعلّمين واختر التخصص الذي تريد تعلّمه.",
    icon: "grid" as const,
  },
  {
    title: "سجّل في مساحة المعلّم",
    body: "أنشئ حسابك من صفحة المعلّم نفسه، وانتظر موافقته على طلبك.",
    icon: "book" as const,
  },
  {
    title: "تابع رحلة تعلّمك",
    body: "الدورات المجانية تُفعَّل فورًا، وبمقابل ينتظر تأكيد المعلّم لإشعار الدفع.",
    icon: "chart" as const,
  },
];

const FAQS = [
  {
    q: "ما هي وجهة؟",
    a: "منصّة عربية تضع لكل معلّم مساحة تعلّم مستقلة بعنوانه الخاص، فيها حسابه وطلابه ودوراته.",
  },
  {
    q: "كيف أسجّل مع معلّم؟",
    a: "اختر معلّمك من الدليل، ثم أنشئ حسابًا في مساحته الخاصة. الدخول يبدأ بعد موافقة المعلّم على طلبك.",
  },
  {
    q: "هل يمكنني الاشتراك مع أكثر من معلّم؟",
    a: "نعم. لكل معلّم مساحة وحساب مستقل، ولك كلمة مرور وطلب موافقة داخل كل مساحة.",
  },
  {
    q: "أين تُحفظ تسجيلاتي؟",
    a: "تسجيلاتك ودوراتك محفوظة في مساحة المعلّم نفسها، وتظهر لك في حسابك بعد الموافقة.",
  },
];

/* ---------- Small inline stroke icons (consistent with the UI set) ---------- */

function Icon({ name, className = "h-4 w-4" }: { name: string; className?: string }) {
  const paths: Record<string, ReactNode> = {
    book: (
      <>
        <path d="M3 4.5c2.5-1 5-1 7 .5v13c-2-1.5-4.5-1.5-7-.5v-13Z" />
        <path d="M10 5c2-1.5 4.5-1.5 7-.5v13c-2.5-1-5-1-7 .5v-13Z" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    person: (
      <>
        <circle cx="12" cy="7.5" r="3.5" />
        <path d="M5 20c1.5-3.5 4-5 7-5s5.5 1.5 7 5" />
      </>
    ),
    chart: (
      <>
        <path d="M4 20V10" />
        <path d="M10 20V4" />
        <path d="M16 20v-8" />
      </>
    ),
    star: <path d="M12 3.5l2.3 4.7 5.2.7-3.8 3.6.9 5.1L12 15.2l-4.6 2.4.9-5.1-3.8-3.6 5.2-.7L12 3.5Z" />,
    check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
    chevron: <path d="M6 9l6 6 6-6" />,
  };
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      {paths[name]}
    </svg>
  );
}

export function LandingPage() {
  const [entries, setEntries] = useState<PublicTeacherDirectoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(0);
  const [sortBy, setSortBy] = useState<"default" | "name">("default");
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 320);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErrorText(null);
      try {
        const response = await listPublicTeachers();
        if (!cancelled) {
          setEntries(response.results);
          setTotal(response.count);
        }
      } catch {
        if (!cancelled) setErrorText("تعذّر تحميل دليل المعلّمين. حاول بعد قليل.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeCategory = CATEGORIES[category];

  const visible = useMemo(() => {
    const term = search.trim();
    let list = entries;
    if (activeCategory.keywords.length > 0) {
      list = list.filter((entry) => {
        const haystack = `${entry.name} ${entry.teacher_name ?? ""} ${entry.headline ?? ""}`;
        return activeCategory.keywords.some((k) => haystack.includes(k));
      });
    }
    if (term) {
      list = list.filter((entry) =>
        `${entry.name} ${entry.teacher_name ?? ""} ${entry.headline ?? ""}`.includes(term),
      );
    }
    if (sortBy === "name") {
      list = [...list].sort((a, b) => (a.teacher_name ?? a.name).localeCompare(b.teacher_name ?? b.name, "ar"));
    }
    return list;
  }, [entries, activeCategory, search, sortBy]);

  function categoriesFor(entry: PublicTeacherDirectoryEntry): string[] {
    const haystack = `${entry.name} ${entry.teacher_name ?? ""} ${entry.headline ?? ""}`;
    return CATEGORIES.filter(
      (c) => c.keywords.length > 0 && c.keywords.some((k) => haystack.includes(k)),
    ).map((c) => c.label);
  }

  return (
    <div className="divide-y divide-line">
      {/* ---------- 1. Hero ---------- */}
      <section className="grid items-center gap-10 pb-14 pt-6 lg:grid-cols-[1fr_1.05fr]">
        <div>
          <p className="flex items-center justify-end gap-2 text-sm text-ink-secondary">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
            لكل فضول، بداية جديدة
          </p>
          <h1 className="mt-4 text-[clamp(42px,5vw,64px)] font-extrabold leading-[1.25] text-ink">
            تعلّم اليوم.
            <br />
            <span className="relative inline-block text-accent">
              حدّد وجهتك.
              <span
                aria-hidden
                className="absolute -bottom-1 start-0 h-2 w-full rounded-full bg-accent/20"
              />
            </span>
          </h1>
          <p className="mt-5 max-w-lg text-sm leading-[1.9] text-ink-secondary">
            تعلّم مع معلّم يقدُم رحلتك. اختر معلّمك، واشترك إلى مساحته الخاصة، وحدّد خطوتك الأولى نحو ما تريد أن تكون.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-4">
            <Link to="/teachers">
              <Button size="lg">
                ابدأ رحلتك
                <span aria-hidden>←</span>
              </Button>
            </Link>
          </div>
          <p className="mt-3 flex items-center gap-2 text-xs text-ink-muted">
            <Icon name="check" className="h-3.5 w-3.5 text-success" />
            اختر معلّمك أولًا، ثم سجّل معه — نسخة تجريبية.
          </p>
          <p className="mt-10 border-t border-line pt-5 text-sm font-semibold text-ink">
            رحلة تعلّم أوضح. آفاق أوسع.
          </p>
        </div>

        {/* Photo composition with floating cards (decorative) */}
        <div className="relative px-4 pb-6 pt-10" aria-hidden>
          <span className="absolute -top-2 end-6 text-4xl font-light text-ink-muted select-none">+</span>
          <div className="relative">
            <span className="absolute -inset-4 -rotate-3 rounded-[3rem] border border-line" />
            <div className="relative overflow-hidden rounded-[2.2rem]">
              <img
                src="/images/hero-student.jpg"
                alt=""
                className="h-[430px] w-full object-cover"
                loading="eager"
              />
              <div className="absolute inset-x-0 bottom-0 bg-surface/90 px-6 py-3 text-center">
                <p className="font-bold text-ink">خطواتك القادمة تبدأ من هنا.</p>
              </div>
            </div>

            <div className="absolute -start-8 top-10 flex items-center gap-3 rounded-control bg-surface p-3 pe-5 shadow-elevated">
              <span className="flex h-10 w-10 items-center justify-center rounded-card bg-accent-soft text-accent">
                <Icon name="star" />
              </span>
              <div>
                <p className="text-sm font-bold text-ink">خطوة أقرب إلى هدفك</p>
                <p className="text-[11px] text-ink-muted">كل درس يصنع فرقًا.</p>
              </div>
              <span className="ms-4 flex h-8 w-8 items-center justify-center rounded-full bg-success-bg text-success">
                <Icon name="check" className="h-4 w-4" />
              </span>
            </div>

            <div className="absolute -bottom-2 end-[-14px] w-60 rounded-control bg-surface/95 p-4 shadow-elevated backdrop-blur">
              <p className="text-[11px] text-ink-muted">تقدّم على هدف، ويُبنى بنقّة.</p>
              <p className="mt-1 flex items-center gap-2 text-sm font-bold text-ink">
                <span className="flex h-7 w-7 items-center justify-center rounded-card bg-accent-soft text-accent">
                  <Icon name="book" className="h-3.5 w-3.5" />
                </span>
                شاهد كيف تُبنى معرفتك
              </p>
              <span className="mt-2 block h-1.5 rounded-full bg-soft">
                <span className="block h-1.5 w-3/4 rounded-full bg-accent" />
              </span>
            </div>
          </div>
          <p className="mt-4 text-center text-[11px] text-ink-muted">تعلّم. اكتشف. تقدّم.</p>
        </div>
      </section>

      {/* ---------- 2. Feature strip ---------- */}
      <section className="py-10">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <p className="max-w-[220px] text-sm font-semibold leading-[1.8] text-ink">
            مهما كانت رحلتك، هناك معلّم يناسبك.
          </p>
          {FEATURE_STRIP.map((item) => (
            <span key={item.label} className="flex items-center gap-2.5 text-sm font-medium text-ink-secondary">
              <Icon name={item.icon} className="h-5 w-5 text-ink-muted" />
              {item.label}
            </span>
          ))}
        </div>
      </section>

      {/* ---------- 3. Teachers preview (real data) ---------- */}
      <section id="teachers" className="scroll-mt-24 py-12">
        <p className="text-sm text-ink-muted">المعلّمون المتميّزون، بداية مختلفة</p>
        <h2 className="mt-2 text-[clamp(28px,3vw,36px)] font-extrabold leading-[1.4] text-ink">
          اختر من يرافق رحلة تعلّمك.
        </h2>
        <p className="mt-2 text-sm leading-[1.8] text-ink-secondary">
          تعرّف على المعلمين واختر تخصصك، ثم سجّل في مساحة معلّمك.
        </p>

        <div className="mt-6 max-w-xl">
          <Input
            type="search"
            placeholder="ابحث باسم المعلم أو التخصص..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="البحث في دليل المعلّمين"
          />
        </div>

        <ul className="mt-5 flex flex-wrap justify-end gap-2" aria-label="التصنيفات">
          {CATEGORIES.map((item, index) => (
            <li key={item.label}>
              <button
                type="button"
                onClick={() => setCategory(index)}
                aria-pressed={category === index}
                className={
                  "rounded-full border px-4 py-2 text-xs font-semibold transition-all " +
                  (category === index
                    ? "border-accent bg-accent text-accent-contrast"
                    : "border-line bg-surface text-ink-secondary hover:border-accent/50 hover:text-ink")
                }
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs text-ink-muted">ترتيب حسب</span>
            <Select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as "default" | "name")}
              className="w-44"
              aria-label="ترتيب المعلمين"
            >
              <option value="default">الترتيب الافتراضي</option>
              <option value="name">اسم المعلّم</option>
            </Select>
          </div>
          <span className="text-xs text-ink-muted">
            نعرض {toArabicDigits(visible.length)} من {toArabicDigits(total)} معلمين
          </span>
        </div>

        {errorText ? (
          <p className="mt-8 text-sm text-err">{errorText}</p>
        ) : loading ? (
          <FullPageSpinner />
        ) : visible.length === 0 ? (
          <p className="mt-10 text-center text-sm text-ink-secondary">لا توجد مساحات مطابقة في هذا الترشيح بعد.</p>
        ) : (
          <ul className="mt-6 grid gap-5 sm:grid-cols-2 xl:grid-cols-4" aria-live="polite">
            {visible.map((entry) => (
              <TeacherPreviewCard key={entry.slug} entry={entry} subjects={categoriesFor(entry)} />
            ))}
          </ul>
        )}

        <div className="mt-10 text-center">
          <Link to="/teachers">
            <Button variant="secondary" size="lg">
              استكشف جميع المعلمين
              <span aria-hidden>←</span>
            </Button>
          </Link>
          <p className="mt-3 text-xs text-ink-muted">
            أسماء المعلمين وصفحاتهم معروضة للتصفح قبل التسجيل — لا حاجة للحساب للبدء.
          </p>
        </div>
      </section>

      {/* ---------- 4. Steps ---------- */}
      <section id="how" className="scroll-mt-24 py-4">
        <div className="relative left-1/2 w-screen -translate-x-1/2 bg-section px-6 py-14">
          <div className="mx-auto grid w-full max-w-[1112px] items-start gap-10 lg:grid-cols-2">
            <div>
              <p className="text-sm text-ink-muted">من البداية إلى الإتقان</p>
              <h2 className="mt-2 text-[clamp(28px,3vw,36px)] font-extrabold leading-[1.4] text-ink">
                طريق واضح. سطور واضحة.
              </h2>
              <p className="mt-3 max-w-md text-sm leading-[1.9] text-ink-secondary">
                لا تحتاج أن تعرف كل شيء لتبدأ. تحتاج فقط أن تختار خطوتك الأولى.
              </p>
              <Link to="/teachers" className="mt-6 inline-block">
                <Button>اكتشف المعلمين</Button>
              </Link>
            </div>

            <ol className="divide-y divide-line">
              {STEPS.map((step, index) => (
                <li key={step.title} className="flex items-start justify-between gap-6 py-6 first:pt-2 last:pb-2">
                  <div>
                    <p className="text-xs text-ink-muted">{toArabicDigits(index + 1)}.</p>
                    <h3 className="mt-1 font-bold text-ink">{step.title}</h3>
                    <p className="mt-1 text-sm leading-[1.8] text-ink-secondary">{step.body}</p>
                  </div>
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center text-ink-muted">
                    <Icon name={step.icon} className="h-6 w-6" />
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* ---------- 5. FAQ ---------- */}
      <section id="faq" className="scroll-mt-24 py-14">
        <p className="text-center text-sm text-ink-muted">قبل خطوتك الأولى</p>
        <h2 className="mt-2 text-center text-[clamp(28px,3vw,36px)] font-extrabold leading-[1.4] text-ink">
          قد تتساءل…
        </h2>
        <p className="mt-2 text-center text-sm text-ink-secondary">إجابات بسيطة لتبدأ بثقة.</p>

        <div className="mx-auto mt-8 max-w-3xl divide-y divide-line">
          {FAQS.map((faq) => (
            <details key={faq.q} className="group px-2 py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-ink marker:content-none">
                {faq.q}
                <Icon
                  name="chevron"
                  className="h-4 w-4 shrink-0 text-ink-muted transition-transform duration-200 group-open:rotate-180"
                />
              </summary>
              <p className="mt-3 text-sm leading-[1.9] text-ink-secondary">{faq.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ---------- 6. Closing CTA ---------- */}
      <section className="pb-6 pt-8">
        <div className="relative overflow-hidden rounded-panel bg-panel px-8 py-14 text-center text-panel-fg md:px-14">
          <span className="pointer-events-none absolute -start-10 top-1/2 flex h-48 w-48 -translate-y-1/2 items-center justify-center rounded-full bg-panel-fg/5">
            <Icon name="book" className="h-16 w-16 text-panel-fg/15" />
          </span>
          <p className="text-sm text-panel-fg/70">المعرفة تفتح أبواباً جديدة</p>
          <h2 className="mt-2 text-[clamp(28px,3.4vw,40px)] font-extrabold leading-[1.4]">
            أفقك القادم، يبدأ بخطوة.
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-sm leading-[1.9] text-panel-fg/75">
            ابدأ رحلتك مع وجهة، واجعل فضولك بوابتك إلى المزيد.
          </p>
          <Link to="/teachers" className="mt-7 inline-block">
            <Button variant="secondary" size="lg">
              ابدأ رحلتك الآن
              <span aria-hidden>←</span>
            </Button>
          </Link>
          <p className="mt-4 text-xs text-panel-fg/60">بدون حساب: تصفّح دليل المعلّمين واختر معلّمك حين تكون مستعدًّا.</p>
        </div>
      </section>

      {/* Back to top */}
      {scrolled && (
        <button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-6 end-6 z-20 flex h-11 w-11 items-center justify-center rounded-full border border-line bg-surface text-accent shadow-elevated transition-all hover:bg-soft"
          aria-label="العودة إلى الأعلى"
        >
          <span aria-hidden>↑</span>
        </button>
      )}
    </div>
  );
}

/* ---------- One teacher preview card ---------- */

function TeacherPreviewCard({
  entry,
  subjects,
}: {
  entry: PublicTeacherDirectoryEntry;
  subjects: string[];
}) {
  const tile = tileFor(entry.slug);
  const title = entry.teacher_name || entry.name;

  return (
    <li className="h-full overflow-hidden rounded-card border border-line bg-surface transition-all duration-200 ease-[var(--ease-standard)] hover:-translate-y-1 hover:shadow-card">
      {/* Tinted cover with watermark + optional subject chip */}
      <div
        className="relative flex h-24 items-center justify-center"
        style={{ background: `var(--tile-${tile}-bg)` }}
      >
        {subjects[0] && (
          <span className="absolute top-3 start-3 rounded-full bg-surface/85 px-2.5 py-0.5 text-[11px] font-semibold text-ink">
            {subjects[0]}
          </span>
        )}
        <Icon name="grid" className="absolute -start-6 bottom-[-14px] h-24 w-24 text-black/[0.04]" />
        {/* Avatar circle overlapping the cover bottom */}
        <div className="absolute -bottom-9">
          {entry.logo ? (
            <img
              src={entry.logo}
              alt={`شعار ${entry.name}`}
              className="h-[72px] w-[72px] rounded-full border-4 border-surface object-cover"
              loading="lazy"
            />
          ) : (
            <span
              className="flex h-[72px] w-[72px] items-center justify-center rounded-full border-4 border-surface text-2xl font-bold"
              style={{
                color: `var(--tile-${tile}-fg)`,
                background: `var(--tile-${tile}-bg)`,
                borderColor: "var(--surface)",
              }}
            >
              {title.trim().charAt(0) || "؟"}
            </span>
          )}
        </div>
      </div>

      <div className="px-5 pb-5 pt-12">
        <p className="min-w-0 truncate text-center text-lg font-extrabold text-ink">{title}</p>
        {entry.headline && (
          <p className="mt-2 line-clamp-2 min-h-[3.4em] text-center text-sm leading-[1.8] text-ink-secondary">
            {entry.headline}
          </p>
        )}

        <div className="mt-4 space-y-2 border-t border-line pt-4">
          {entry.name !== title && (
            <p className="flex items-center justify-between gap-2 text-xs">
              <span className="text-ink-muted">المساحة</span>
              <span className="min-w-0 truncate font-semibold text-ink">{entry.name}</span>
            </p>
          )}
          <p className="flex items-center justify-between gap-2 text-xs">
            <span className="text-ink-muted">الموقع</span>
            <span dir="ltr" className="min-w-0 truncate font-medium text-ink-secondary">
              {entry.slug}.{location.hostname.includes("localhost") ? "localhost" : "edunova.com"}
            </span>
          </p>
        </div>

        <div className="mt-4">
          <Link
            to={`/teachers/${entry.slug}`}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-control border border-line bg-surface text-sm font-semibold text-accent transition-colors hover:bg-soft"
          >
            تعرّف على المعلم
            <span aria-hidden>←</span>
          </Link>
          <a
            href={subdomainUrl(entry.slug)}
            className="mt-2 flex h-10 w-full items-center justify-center gap-2 rounded-control bg-accent text-sm font-semibold text-accent-contrast transition-opacity hover:opacity-90"
          >
            تعلّم مع المعلم
            <span aria-hidden>←</span>
          </a>
        </div>
      </div>
    </li>
  );
}
