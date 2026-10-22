from decimal import Decimal
from apps.courses.models import Course


def create_course(
    workspace,
    *,
    title="Test Course",
    description="Course description",
    price="0.00",
    is_published=True,
):
    return Course.objects.create(
        workspace=workspace,
        title=title,
        description=description,
        price=Decimal(str(price)),
        is_published=is_published,
    )
