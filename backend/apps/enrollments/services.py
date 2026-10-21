from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import CourseEnrollment


@transaction.atomic
def enroll_student_in_course(student, course, workspace):
    """
    Enroll a student in a course within the workspace.
    If already enrolled, return the existing enrollment.
    Free courses become active immediately; paid courses become pending_payment.
    """
    enrollment = (
        CourseEnrollment.objects.select_for_update()
        .filter(student=student, course=course)
        .first()
    )
    if enrollment is not None:
        return enrollment, False

    if course.price == Decimal("0.00"):
        status = CourseEnrollment.Status.ACTIVE
        activated_at = timezone.now()
    else:
        status = CourseEnrollment.Status.PENDING_PAYMENT
        activated_at = None

    try:
        with transaction.atomic():
            enrollment = CourseEnrollment.objects.create(
                workspace=workspace,
                student=student,
                course=course,
                status=status,
                price_at_enrollment=course.price,
                activated_at=activated_at,
            )
        return enrollment, True
    except IntegrityError:
        existing = (
            CourseEnrollment.objects.filter(student=student, course=course)
            .first()
        )
        if existing:
            return existing, False
        raise
