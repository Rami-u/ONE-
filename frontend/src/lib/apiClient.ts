/*
  Small same-origin fetch wrapper for the backend API.

  - Authentication is the Django session cookie, so requests are same-origin
    and no token is ever stored in the app.
  - Unsafe methods (POST/PATCH/...) send the X-CSRFToken header taken from the
    csrftoken cookie. If the cookie is missing, the workspace CSRF endpoint is
    called once to set it.
*/

const API_BASE = "/api/v1";
const CSRF_COOKIE = "csrftoken";

let workspaceSlug: string | null = null;

/** Point the client at the current workspace (null on the main domain). */
export function setApiWorkspace(slug: string | null): void {
  workspaceSlug = slug;
}

export class ApiError extends Error {
  status: number;
  /** The full parsed body of the error response (e.g. {code, message, rejection_reason}). */
  body: Record<string, unknown>;
  /** DRF-style field validation errors, e.g. { email: ["Enter a valid email address."] }. */
  fieldErrors: Record<string, string[]>;

  constructor(status: number, message: string, body: Record<string, unknown>, fieldErrors: Record<string, string[]>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.fieldErrors = fieldErrors;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** Sent as a JSON body. */
  json?: unknown;
  /** Sent as multipart/form-data (file uploads). */
  formData?: FormData;
}

function readCookie(name: string): string | null {
  const match = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

/** GET /auth/csrf/ so the browser stores a csrf token before unsafe requests. */
async function ensureCsrfCookie(): Promise<void> {
  if (readCookie(CSRF_COOKIE) || !workspaceSlug) return;
  await fetch(
    `${API_BASE}/workspaces/${encodeURIComponent(workspaceSlug)}/auth/csrf/`,
    { credentials: "same-origin" },
  );
}

function serializeErrorBody(body: unknown, status: number): {
  message: string;
  fieldErrors: Record<string, string[]>;
  parsed: Record<string, unknown>;
} {
  if (body && typeof body === "object") {
    const parsed = body as Record<string, unknown>;

    if (typeof parsed.detail === "string") {
      return { message: parsed.detail, fieldErrors: {}, parsed };
    }
    if (typeof parsed.message === "string") {
      return { message: parsed.message, fieldErrors: {}, parsed };
    }

    const fieldErrors: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(parsed)) {
      if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
        fieldErrors[key] = value as string[];
      }
    }
    if (Object.keys(fieldErrors).length > 0) {
      return { message: "Please fix the errors below.", fieldErrors, parsed };
    }
  }
  return { message: `Request failed (${status}).`, fieldErrors: {}, parsed: {} };
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  if (method !== "GET") {
    await ensureCsrfCookie();
    const token = readCookie(CSRF_COOKIE);
    if (token) headers["X-CSRFToken"] = token;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?", {}, {});
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let parsedBody: unknown = null;
  const contentType = response.headers.get("Content-Type") ?? "";
  if (contentType.includes("application/json")) {
    parsedBody = await response.json().catch(() => null);
  }

  if (!response.ok) {
    const { message, fieldErrors, parsed } = serializeErrorBody(parsedBody, response.status);
    throw new ApiError(response.status, message, parsed, fieldErrors);
  }

  return parsedBody as T;
}
