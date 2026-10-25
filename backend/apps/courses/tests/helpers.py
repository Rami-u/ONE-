from decimal import Decimal
from apps.courses.models import Course, CourseSection, Lesson, LessonAsset


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


def create_section(workspace, course, *, title="Test Section", **fields):
    return CourseSection.objects.create(
        workspace=workspace,
        course=course,
        title=title,
        **fields,
    )


def create_lesson(workspace, course, *, title="Test Lesson", **fields):
    return Lesson.objects.create(
        workspace=workspace,
        course=course,
        title=title,
        **fields,
    )


def create_lesson_asset(
    workspace,
    lesson,
    *,
    title="Test Asset",
    asset_type=LessonAsset.AssetType.PDF,
    storage_key="lessons/example.pdf",
    **fields,
):
    return LessonAsset.objects.create(
        workspace=workspace,
        lesson=lesson,
        title=title,
        asset_type=asset_type,
        storage_key=storage_key,
        **fields,
    )
