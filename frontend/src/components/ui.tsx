import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { formatPrice } from "../lib/format";
import type { ApprovalStatus, EnrollmentStatus, PaymentStatus } from "../types/api";

/*
  Shared وجهة primitives — tokens come from src/index.css (DESIGN.md).
  Resting cards rely on borders; shadows are hover/elevated only.
  All copy is Arabic; technical fragments (emails, domains, prices) stay dir="ltr".
*/

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/* ---------- Motion helpers ---------- */

export const motionFast = "duration-180 ease-[var(--ease-standard)]";
export const motionBase = "duration-200 ease-[var(--ease-standard)]";

/* ---------- Button ---------- */

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

const buttonStyles: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-contrast hover:opacity-90",
  secondary: "bg-surface text-accent border border-line hover:bg-soft",
  danger: "bg-err text-white hover:opacity-90 dark:text-[#3e2a2c]",
  ghost: "bg-transparent text-ink hover:bg-soft",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-xs",
  md: "h-10 px-4 text-sm", // portal standard ≥40px
  lg: "h-12 px-6 text-sm", // major landing CTA 48px
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-control font-semibold transition-all focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50",
        motionBase,
        buttonStyles[variant],
        buttonSizes[size],
        className,
      )}
      {...props}
    />
  );
}

/* ---------- Form controls ---------- */

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-ink">
      {children}
    </label>
  );
}

export function FieldError({ id, messages }: { id?: string; messages?: string[] }) {
  if (!messages || messages.length === 0) return null;
  return (
    <p id={id} className="mt-1 text-sm font-medium text-err-form">
      {messages.join(" · ")}
    </p>
  );
}

const fieldBase =
  "block w-full rounded-control border bg-surface px-3 py-2 text-sm text-ink shadow-none placeholder:text-ink-muted focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent disabled:bg-soft";

export function Input({ className, invalid, ...props }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      aria-invalid={invalid || undefined}
      className={cn(fieldBase, invalid ? "border-err-form" : "border-line", className)}
      {...props}
    />
  );
}

export function Textarea({ className, invalid, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  return (
    <textarea
      aria-invalid={invalid || undefined}
      className={cn(fieldBase, "leading-8", invalid ? "border-err-form" : "border-line", className)}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(fieldBase, "border-line", className)} {...props}>
      {children}
    </select>
  );
}

/* ---------- Structure ---------- */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-card border border-line bg-surface p-5", className)}>{children}</div>;
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-[19px] font-bold leading-[1.5] text-ink">{title}</h1>
      {subtitle && <p className="mt-1 text-sm leading-[1.8] text-ink-secondary">{subtitle}</p>}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-card border border-dashed border-line bg-surface/60 p-10 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {hint && <p className="mt-1 text-sm text-ink-secondary">{hint}</p>}
    </div>
  );
}

/* ---------- Feedback ---------- */

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn("inline-block h-5 w-5 animate-spin rounded-full border-2 border-line border-t-accent", className)}
      role="status"
      aria-label="جارٍ التحميل"
    />
  );
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Spinner className="h-8 w-8" />
    </div>
  );
}

type AlertTone = "error" | "success" | "info";

const alertStyles: Record<AlertTone, string> = {
  error: "border-[color:color-mix(in_srgb,var(--error-fg)_35%,transparent)] bg-err-bg text-err",
  success: "border-[color:color-mix(in_srgb,var(--success-fg)_35%,transparent)] bg-success-bg text-success",
  info: "border-[color:color-mix(in_srgb,var(--accent)_35%,transparent)] bg-accent-soft text-ink",
};

export function Alert({ tone = "info", children }: { tone?: AlertTone; children: ReactNode }) {
  return (
    <div className={cn("rounded-card border px-4 py-3 text-sm", alertStyles[tone])} role="alert">
      {children}
    </div>
  );
}

/* ---------- Status badges (never color-only: explicit labels) ---------- */

const badgeBase = "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold";

const enrollmentBadge: Record<EnrollmentStatus, string> = {
  pending_payment: `${badgeBase} bg-warn-bg text-warn`,
  active: `${badgeBase} bg-success-bg text-success`,
  withdrawn: `${badgeBase} bg-soft text-ink-secondary border border-line`,
};

const paymentBadge: Record<PaymentStatus, string> = {
  submitted: `${badgeBase} bg-warn-bg text-warn`,
  confirmed: `${badgeBase} bg-success-bg text-success`,
  rejected: `${badgeBase} bg-err-bg text-err`,
};

const approvalBadge: Record<ApprovalStatus, string> = {
  pending: `${badgeBase} bg-warn-bg text-warn`,
  approved: `${badgeBase} bg-success-bg text-success`,
  rejected: `${badgeBase} bg-err-bg text-err`,
};

export function EnrollmentBadge({ status }: { status: EnrollmentStatus }) {
  const label = status === "pending_payment" ? "بانتظار الدفع" : status === "active" ? "نشط" : "منسحب";
  return <span className={cn(enrollmentBadge[status], motionBase)}>{label}</span>;
}

export function PaymentBadge({ status }: { status: PaymentStatus }) {
  const label = status === "submitted" ? "قُدّم" : status === "confirmed" ? "مؤكّد" : "مرفوض";
  return <span className={cn(paymentBadge[status], motionBase)}>{label}</span>;
}

export function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  const label = status === "pending" ? "بالانتظار" : status === "approved" ? "مقبول" : "مرفوض";
  return <span className={cn(approvalBadge[status], motionBase)}>{label}</span>;
}

/* ---------- Pagination ---------- */

export function PaginationControls({
  page,
  count,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: {
  page: number;
  count: number;
  /** Kept for callers' readability; the count sentence is the only place sizes are shown. */
  pageSize?: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-ink-secondary">
      <span aria-live="polite">
        {count} نتيجة · صفحة {page}
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={!hasPrevious} onClick={onPrevious}>
          السابق
        </Button>
        <Button variant="secondary" size="sm" disabled={!hasNext} onClick={onNext}>
          التالي
        </Button>
      </div>
    </div>
  );
}

/* ---------- Course cover tile (subject accents) ---------- */

const TILE_SETS = ["teal", "blue", "sand", "purple"] as const;

/** Deterministic per-course accent from the doc's four subject pairs. */
export function courseTileKey(courseId: number): (typeof TILE_SETS)[number] {
  return TILE_SETS[Math.abs(courseId) % 4];
}

export function CourseCover({ courseId, title, size = 52 }: { courseId: number; title: string; size?: number }) {
  const tile = courseTileKey(courseId);
  return (
    <span
      aria-hidden
      className="flex shrink-0 items-center justify-center rounded-card font-bold"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.4,
        color: `var(--tile-${tile}-fg)`,
        background: `var(--tile-${tile}-bg)`,
      }}
    >
      {title.trim().charAt(0) || "؟"}
    </span>
  );
}

export function PriceTag({ price, className }: { price: string; className?: string }) {
  const free = formatPrice(price) === "Free";
  return (
    <span dir="ltr" className={cn("font-semibold", free ? "text-success" : "text-accent", className)}>
      {formatPrice(price)}
    </span>
  );
}

/* ---------- Images and identity ---------- */

export function WorkspaceLogo({ src, name, size = 40 }: { src: string | null; name: string; size?: number }) {
  if (!src) {
    return (
      <span
        aria-hidden
        className="inline-flex items-center justify-center rounded-control bg-accent-soft font-bold text-accent"
        style={{ width: size, height: size, fontSize: size * 0.4 }}
      >
        {(name ?? "؟").trim().charAt(0) || "؟"}
      </span>
    );
  }
  return (
    <img
      src={src}
      alt={name ? `شعار ${name}` : "شعار المساحة"}
      className="rounded-control object-cover"
      style={{ width: size, height: size }}
      loading="lazy"
    />
  );
}
