from decimal import Decimal
from apps.enrollments.models import CourseEnrollment


def create_enrollment(
    workspace,
    student,
    course,
    *,
    status=CourseEnrollment.Status.PENDING_PAYMENT,
    price=None,
    activated_at=None,
):
    if price is None:
        price = course.price
    return CourseEnrollment.objects.create(
        workspace=workspace,
        student=student,
        course=course,
        status=status,
        price_at_enrollment=Decimal(str(price)),
        activated_at=activated_at,
    )
