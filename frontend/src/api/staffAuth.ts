import { apiRequest } from "../lib/apiClient";

/** Teacher/staff authentication endpoints (§7.3) on the private workspace path. */

const prefix = (slug: string): string => `/workspaces/${encodeURIComponent(slug)}/staff/auth`;

export interface StaffLoginResponse {
  id: number;
  full_name: string;
}

/** POST /staff/auth/login/ — teachers only; students get the same generic failure. */
export function loginStaff(slug: string, email: string, password: string): Promise<StaffLoginResponse> {
  return apiRequest(`${prefix(slug)}/login/`, { method: "POST", json: { email, password } });
}

/**
 * POST /staff/auth/set-password/ — set the first password from an invitation
 * link, or finish a staff password reset (same uid/token/new_password shape).
 */
export function setStaffPassword(
  slug: string,
  uid: string,
  token: string,
  newPassword: string,
): Promise<{ detail: string }> {
  return apiRequest(`${prefix(slug)}/set-password/`, {
    method: "POST",
    json: { uid, token, new_password: newPassword },
  });
}

/** POST /staff/auth/password-reset/ — send the reset email; always returns a generic message. */
export function startStaffPasswordReset(slug: string, email: string): Promise<{ detail: string }> {
  return apiRequest(`${prefix(slug)}/password-reset/`, { method: "POST", json: { email } });
}
