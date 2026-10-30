import { apiRequest } from "../lib/apiClient";
import type { ApiUser, RegistrationResponse } from "../types/api";

/** Student authentication endpoints (§7.2) under /api/v1/workspaces/{slug}/auth/. */

const prefix = (slug: string): string => `/workspaces/${encodeURIComponent(slug)}/auth`;

export interface StudentRegistrationInput {
  email: string;
  full_name: string;
  password: string;
  phone?: string | null;
}

/** POST /auth/register/ — creates a pending student. No session is issued; 201. */
export function registerStudent(slug: string, input: StudentRegistrationInput): Promise<RegistrationResponse> {
  return apiRequest(`${prefix(slug)}/register/`, {
    method: "POST",
    json: { email: input.email, full_name: input.full_name, password: input.password, phone: input.phone || null },
  });
}

/**
 * POST /auth/login/ — starts a session for an approved student.
 * Throws ApiError: 400 with {detail} for wrong credentials,
 * 403 with LoginStateError ({code, message, rejection_reason}) when the
 * credentials are correct but the account is pending or rejected.
 */
export function loginStudent(slug: string, email: string, password: string): Promise<ApiUser> {
  return apiRequest(`${prefix(slug)}/login/`, { method: "POST", json: { email, password } });
}

/** POST /auth/logout/ — ends the session. 204. */
export function logoutStudent(slug: string): Promise<void> {
  return apiRequest(`${prefix(slug)}/logout/`, { method: "POST" });
}

/** GET /auth/me/ — the signed-in workspace member (any role). 401/403 when signed out. */
export function getMe(slug: string): Promise<ApiUser> {
  return apiRequest(`${prefix(slug)}/me/`);
}

/** POST /auth/password-reset/ — always succeeds with a generic message; do not reveal account existence. */
export function startStudentPasswordReset(slug: string, email: string): Promise<{ detail: string }> {
  return apiRequest(`${prefix(slug)}/password-reset/`, { method: "POST", json: { email } });
}

/** POST /auth/password-reset/confirm/ — finish reset with uid/token from the emailed link. */
export function confirmStudentPasswordReset(
  slug: string,
  uid: string,
  token: string,
  newPassword: string,
): Promise<{ detail: string }> {
  return apiRequest(`${prefix(slug)}/password-reset/confirm/`, {
    method: "POST",
    json: { uid, token, new_password: newPassword },
  });
}
