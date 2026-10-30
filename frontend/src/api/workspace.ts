import { apiRequest } from "../lib/apiClient";
import type { WorkspaceSettings } from "../types/api";

/** Workspace settings endpoints from apps/public (teacher workspace §7.5). */

const pk = (slug: string): string => encodeURIComponent(slug);

/** GET /api/v1/workspaces/{slug}/ — current settings. Workspace staff only. */
export function getWorkspaceSettings(slug: string): Promise<WorkspaceSettings> {
  return apiRequest(`/workspaces/${pk(slug)}/`);
}

export interface WorkspaceSettingsPatch {
  name?: string;
  headline?: string | null;
  bio?: string | null;
  about?: string | null;
  is_listed?: boolean;
  payment_instructions?: string | null;
}

/**
 * PATCH /api/v1/workspaces/{slug}/ — update settings. The slug is not editable.
 * When changing the logo the request must be multipart/form-data; otherwise
 * the backend expects a JSON body.
 *
 * FormData cannot represent a JSON null, so when the patch clears a text
 * field while also uploading a logo, the text change is sent as an ordinary
 * JSON PATCH first and the logo goes in a second multipart PATCH.
 */
export async function updateWorkspaceSettings(
  slug: string,
  patch: WorkspaceSettingsPatch & { logo?: File | null },
): Promise<WorkspaceSettings> {
  const { logo, ...fields } = patch;

  if (!logo) {
    return apiRequest(`/workspaces/${pk(slug)}/`, { method: "PATCH", json: patch });
  }

  const clearsTextFields = Object.values(fields).some((value) => value === null);
  if (clearsTextFields) {
    await apiRequest(`/workspaces/${pk(slug)}/`, { method: "PATCH", json: fields });
  }

  const formData = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    if (value === null || value === undefined) continue;
    formData.append(key, typeof value === "boolean" ? (value ? "true" : "false") : String(value));
  }
  formData.append("logo", logo);
  return apiRequest(`/workspaces/${pk(slug)}/`, { method: "PATCH", formData });
}
