from apps.payments.models import PaymentSubmission


def create_payment(
    workspace,
    enrollment,
    student,
    *,
    amount=None,
    method=PaymentSubmission.Method.TRANSFER,
    note="Test payment note",
    status=PaymentSubmission.Status.SUBMITTED,
    receipt_image=None,
    reviewed_by=None,
    reviewed_at=None,
    rejection_reason=None,
):
    if amount is None:
        amount = enrollment.price_at_enrollment
    return PaymentSubmission.objects.create(
        workspace=workspace,
        enrollment=enrollment,
        submitted_by=student,
        amount=amount,
        method=method,
        note=note,
        status=status,
        receipt_image=receipt_image,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        rejection_reason=rejection_reason,
    )
