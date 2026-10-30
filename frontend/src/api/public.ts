import { apiRequest, type RequestOptions } from "../lib/apiClient";
import type { Page, PublicTeacherDirectoryEntry, PublicTeacherProfile, WorkspaceBranding } from "../types/api";

/**
 * Endpoints from apps/public. All are public (no authentication), so they work
 * on the main domain, on a listed teacher's sub-domain, and before login.
 */

/** GET /api/v1/public/teachers/?search=&page= — active and listed workspaces only. */
export function listPublicTeachers(params: { search?: string; page?: number } = {}): Promise<Page<PublicTeacherDirectoryEntry>> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.page && params.page > 1) query.set("page", String(params.page));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`/public/teachers/${suffix}`);
}

/** GET /api/v1/public/teachers/{slug}/ — profile for the main-site directory page. */
export function getPublicTeacherProfile(slug: string): Promise<PublicTeacherProfile> {
  return apiRequest(`/public/teachers/${encodeURIComponent(slug)}/`);
}

/** GET /api/v1/workspaces/{slug}/branding/ — works even when the workspace is not listed. */
export function getWorkspaceBranding(slug: string, options: RequestOptions = {}): Promise<WorkspaceBranding> {
  return apiRequest(`/workspaces/${encodeURIComponent(slug)}/branding/`, options);
}

/** GET /api/v1/workspaces/{slug}/public-profile/ — any active workspace, listed or not. */
export function getWorkspacePublicProfile(slug: string): Promise<PublicTeacherProfile> {
  return apiRequest(`/workspaces/${encodeURIComponent(slug)}/public-profile/`);
}
