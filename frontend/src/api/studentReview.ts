import { apiRequest } from "../lib/apiClient";
import type { ApprovalStatus, Page, StudentReviewEntry } from "../types/api";

/** Workspace student review endpoints (§7.5) under /api/v1/workspaces/{slug}/students/. */

const prefix = (slug: string): string => `/workspaces/${encodeURIComponent(slug)}/students`;

/** GET /students/?status=pending|approved|rejected — filter; anything else is a 400. */
export function listWorkspaceStudents(
  slug: string,
  status: ApprovalStatus | null,
  page = 1,
): Promise<Page<StudentReviewEntry>> {
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (page > 1) query.set("page", String(page));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`${prefix(slug)}/${suffix}`);
}

/** POST /students/{id}/approve/ — only allowed while the student is still pending. */
export function approveStudent(slug: string, studentId: number): Promise<StudentReviewEntry> {
  return apiRequest(`${prefix(slug)}/${studentId}/approve/`, { method: "POST" });
}

/** POST /students/{id}/reject/ — a reason (max 1000 chars) is required. */
export function rejectStudent(slug: string, studentId: number, rejectionReason: string): Promise<StudentReviewEntry> {
  return apiRequest(`${prefix(slug)}/${studentId}/reject/`, {
    method: "POST",
    json: { rejection_reason: rejectionReason },
  });
}
