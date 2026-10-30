/*
  TypeScript mirrors of the backend serializer shapes. Keep these in sync with
  the serializers under backend/apps/* — the authoritative reference is the
  OpenAPI schema at /api/schema/ (Shape 8.x of docs/backend-design.md).
*/

export type Role = "teacher" | "student" | "assistant" | "admin";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export type WorkspaceStatus = "active" | "suspended";

export type EnrollmentStatus = "pending_payment" | "active" | "withdrawn";

export type PaymentStatus = "submitted" | "confirmed" | "rejected";

export type PaymentMethod = "transfer" | "e_wallet" | "cash" | "other";

/* ---------- Authentication (apps/accounts) ---------- */

export interface WorkspaceRef {
  slug: string;
  name: string;
}

/** GET auth/me/ — any role currently signed in to this workspace. */
export interface ApiUser {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  approval_status: ApprovalStatus;
  workspace: WorkspaceRef;
}

/** 403 body of student login when credentials are correct but the account is pending/rejected. */
export interface LoginStateError {
  code: "pending_approval" | "account_rejected";
  message: string;
  rejection_reason?: string | null;
}

export interface RegistrationResponse {
  message: string;
  approval_status: ApprovalStatus;
}

/* ---------- Public showcase (apps/public) ---------- */

export interface PublicTeacherDirectoryEntry {
  slug: string;
  name: string;
  teacher_name: string;
  logo: string | null;
  headline: string | null;
}

export interface PublicCourse {
  id: number;
  title: string;
  description: string | null;
  price: string;
}

export interface PublicTeacherProfile {
  slug: string;
  name: string;
  teacher_name: string;
  logo: string | null;
  headline: string | null;
  bio: string | null;
  about: string | null;
  courses: PublicCourse[];
}

/** Branding response — includes status so the frontend can show "unavailable". */
export interface WorkspaceBranding {
  slug: string;
  name: string;
  logo: string | null;
  headline: string | null;
  status: WorkspaceStatus;
}

/* ---------- Workspace settings (teacher) ---------- */

export interface WorkspaceSettings {
  slug: string;
  name: string;
  logo: string | null;
  headline: string | null;
  bio: string | null;
  about: string | null;
  is_listed: boolean;
  payment_instructions: string | null;
}

/* ---------- Courses (apps/courses) ---------- */

export interface Course {
  id: number;
  title: string;
  description: string | null;
  price: string;
  is_published: boolean;
  /** The signed-in student's enrollment status for this course; null for teachers/guests. */
  enrollment_status: EnrollmentStatus | null;
  created_at: string;
}

/* ---------- Enrollments (apps/enrollments) ---------- */

export interface EnrollResult {
  enrollment_id: number;
  status: EnrollmentStatus;
  price: string;
  payment_instructions: string | null;
}

export interface Enrollment {
  id: number;
  course_id: number;
  course_title: string;
  status: EnrollmentStatus;
  price_at_enrollment: string;
  created_at: string;
  activated_at: string | null;
}

/* ---------- Payments (apps/payments) ---------- */

export interface PaymentSubmission {
  id: number;
  enrollment_id: number;
  course_id: number;
  course_title: string;
  student_id: number;
  student_name: string;
  student_email: string;
  amount: string;
  method: PaymentMethod;
  note: string | null;
  has_receipt: boolean;
  status: PaymentStatus;
  submitted_at: string;
  reviewed_by_id: number | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
}

/* ---------- Student review (apps/accounts) ---------- */

export interface StudentReviewEntry {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  approval_status: ApprovalStatus;
  rejection_reason: string | null;
  reviewed_at: string | null;
  date_joined: string;
}

/* ---------- Generic pagination (PageNumberPagination, 20 per page) ---------- */

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
