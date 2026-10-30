import { apiRequest } from "../lib/apiClient";
import { fetchAllPages } from "./pagination";
import type { EnrollResult, Enrollment } from "../types/api";

/** Enrollment endpoints (§7.6) from apps/enrollments. */

const prefix = (slug: string): string => `/workspaces/${encodeURIComponent(slug)}`;

/**
 * POST /courses/{id}/enroll/ — approved students only.
 * Free course -> active; paid course -> pending_payment.
 * First enrollment returns 201; enrolling again returns 200 with the existing
 * enrollment details (idempotent).
 */
export function enrollInCourse(slug: string, courseId: number): Promise<EnrollResult> {
  return apiRequest(`${prefix(slug)}/courses/${courseId}/enroll/`, { method: "POST" });
}

/** GET /enrollments/me/ — every enrollment of the student, across pages. */
export function listMyEnrollments(slug: string): Promise<Enrollment[]> {
  return fetchAllPages<Enrollment>(`${prefix(slug)}/enrollments/me/`);
}
