import { apiRequest } from "../lib/apiClient";
import type { Page, PaymentStatus, PaymentSubmission } from "../types/api";

/** Manual payment endpoints (§7.7) from apps/payments. */

const prefix = (slug: string): string => `/workspaces/${encodeURIComponent(slug)}`;

export interface PaymentClaimInput {
  method: string;
  note?: string | null;
  receipt?: File | null;
}

/**
 * POST /enrollments/{id}/payments/ — multipart claim by the owning student.
 * The amount is derived by the server from price_at_enrollment. Returns 201
 * with the submission; 409 Conflict when a claim for this enrollment is
 * already in progress (submitted state).
 */
export function submitPaymentClaim(
  slug: string,
  enrollmentId: number,
  input: PaymentClaimInput,
): Promise<PaymentSubmission> {
  const formData = new FormData();
  formData.append("method", input.method);
  if (input.note) formData.append("note", input.note);
  if (input.receipt) formData.append("receipt_image", input.receipt);
  return apiRequest(`${prefix(slug)}/enrollments/${enrollmentId}/payments/`, {
    method: "POST",
    formData,
  });
}

/**
 * GET /payments/?status= — list payments for the teacher. The status filter
 * accepts submitted|confirmed|rejected; anything else is a 400 Bad Request.
 */
export function listPayments(slug: string, status: PaymentStatus | null, page = 1): Promise<Page<PaymentSubmission>> {
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (page > 1) query.set("page", String(page));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest(`${prefix(slug)}/payments/${suffix}`);
}

/** GET /payments/{id}/receipt/ — binary file served through the authorized endpoint. */
export function paymentReceiptUrl(slug: string, paymentId: number): string {
  return `/api/v1/${prefix(slug)}/payments/${paymentId}/receipt/`;
}

/** POST /payments/{id}/confirm/ — activates the enrollment in one transaction. */
export function confirmPayment(slug: string, paymentId: number): Promise<PaymentSubmission> {
  return apiRequest(`${prefix(slug)}/payments/${paymentId}/confirm/`, { method: "POST" });
}

/** POST /payments/{id}/reject/ — a reason (max 1000 chars) is required. */
export function rejectPayment(slug: string, paymentId: number, rejectionReason: string): Promise<PaymentSubmission> {
  return apiRequest(`${prefix(slug)}/payments/${paymentId}/reject/`, {
    method: "POST",
    json: { rejection_reason: rejectionReason },
  });
}
