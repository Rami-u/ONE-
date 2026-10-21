from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.enrollments.models import CourseEnrollment
from .models import PaymentSubmission


class PaymentConflictError(Exception):
    """Raised when an operation conflicts with the current payment/enrollment state."""
    pass


@transaction.atomic
def submit_payment_claim(enrollment, student, method, note=None, receipt_image=None):
    """
    Submit a manual payment claim for an enrollment.
    Amount is derived strictly from enrollment.price_at_enrollment.
    Only one submitted claim may be open at a time.
    """
    if enrollment.status != CourseEnrollment.Status.PENDING_PAYMENT:
        raise PaymentConflictError(
            f"Cannot submit payment for an enrollment that is {enrollment.status}."
        )

    has_open_claim = (
        PaymentSubmission.objects.select_for_update()
        .filter(enrollment=enrollment, status=PaymentSubmission.Status.SUBMITTED)
        .exists()
    )
    if has_open_claim:
        raise PaymentConflictError("A payment claim is already submitted and pending review.")

    submission = PaymentSubmission.objects.create(
        workspace=enrollment.workspace,
        enrollment=enrollment,
        submitted_by=student,
        amount=enrollment.price_at_enrollment,
        method=method,
        note=note,
        receipt_image=receipt_image,
        status=PaymentSubmission.Status.SUBMITTED,
    )
    return submission


@transaction.atomic
def confirm_payment(payment_id, workspace, reviewer):
    """
    Confirm a payment claim and activate the associated enrollment in the SAME transaction.
    Verifies that the payment is currently submitted.
    """
    payment = (
        PaymentSubmission.objects.select_for_update()
        .filter(workspace=workspace, pk=payment_id)
        .first()
    )
    if payment is None:
        return None

    if payment.status != PaymentSubmission.Status.SUBMITTED:
        raise PaymentConflictError(
            f"Cannot confirm payment because it is already {payment.status}."
        )

    payment.status = PaymentSubmission.Status.CONFIRMED
    payment.reviewed_by = reviewer
    payment.reviewed_at = timezone.now()
    payment.save()

    enrollment = (
        CourseEnrollment.objects.select_for_update()
        .get(pk=payment.enrollment_id)
    )
    enrollment.status = CourseEnrollment.Status.ACTIVE
    enrollment.activated_at = timezone.now()
    enrollment.save()

    return payment


@transaction.atomic
def reject_payment(payment_id, workspace, reviewer, rejection_reason):
    """
    Reject a payment claim with a reason.
    Enrollment remains pending_payment so the student may resubmit.
    Verifies that the payment is currently submitted.
    """
    payment = (
        PaymentSubmission.objects.select_for_update()
        .filter(workspace=workspace, pk=payment_id)
        .first()
    )
    if payment is None:
        return None

    if payment.status != PaymentSubmission.Status.SUBMITTED:
        raise PaymentConflictError(
            f"Cannot reject payment because it is already {payment.status}."
        )

    payment.status = PaymentSubmission.Status.REJECTED
    payment.rejection_reason = rejection_reason
    payment.reviewed_by = reviewer
    payment.reviewed_at = timezone.now()
    payment.save()

    return payment
