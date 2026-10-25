from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.workspaces.tenancy import validate_same_workspace


class Course(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="courses",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "courses"
        ordering = ["-created_at", "id"]

    def __str__(self):
        return self.title


class CourseSection(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="course_sections",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="course_sections",
    )
    title = models.CharField(max_length=200)
    position = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "course_sections"
        ordering = ["position", "id"]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "course")

    def __str__(self):
        return self.title


class Lesson(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="lessons",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="lessons",
    )
    section = models.ForeignKey(
        CourseSection,
        on_delete=models.PROTECT,
        related_name="lessons",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    content = models.TextField(null=True, blank=True)
    position = models.IntegerField(default=1)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lessons"
        ordering = ["position", "id"]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "course", "section")
        if self.section_id and self.course_id and self.section.course_id != self.course_id:
            raise ValidationError({"section": "The section must belong to the lesson's course."})

    def __str__(self):
        return self.title


class LessonAsset(models.Model):
    class AssetType(models.TextChoices):
        PDF = "pdf", "PDF"
        VIDEO = "video", "Video"
        SLIDE = "slide", "Slide"
        DOC = "doc", "Document"
        AUDIO = "audio", "Audio"

    class ExtractionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="lesson_assets",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.PROTECT,
        related_name="lesson_assets",
    )
    title = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=20, choices=AssetType.choices)
    storage_key = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    extraction_status = models.CharField(
        max_length=20,
        choices=ExtractionStatus.choices,
        default=ExtractionStatus.PENDING,
    )
    extracted_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lesson_assets"
        ordering = ["id"]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "lesson")

    def __str__(self):
        return self.title
