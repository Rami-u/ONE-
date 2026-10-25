from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.workspaces.tenancy import validate_same_workspace


class Topic(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="topics",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="topics",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "topics"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="unique_topic_slug_per_workspace",
            )
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "course")

    def __str__(self):
        return self.name


class LessonTopic(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="lesson_topics",
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.PROTECT,
        related_name="lesson_topics",
    )
    topic = models.ForeignKey(
        "assessments.Topic",
        on_delete=models.PROTECT,
        related_name="lesson_topics",
    )

    class Meta:
        db_table = "lesson_topics"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "topic"],
                name="unique_topic_per_lesson",
            )
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "lesson", "topic")

    def __str__(self):
        return f"Lesson {self.lesson_id}: Topic {self.topic_id}"


class Question(models.Model):
    class SourceType(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI_GENERATED = "ai_generated", "AI generated"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    class QuestionType(models.TextChoices):
        MCQ = "mcq", "Multiple choice"
        TRUE_FALSE = "true_false", "True or false"
        SHORT = "short", "Short answer"
        ESSAY = "essay", "Essay"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="questions",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="questions",
        null=True,
        blank=True,
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.PROTECT,
        related_name="questions",
        null=True,
        blank=True,
    )
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.MANUAL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    stem = models.TextField()
    options = models.JSONField(null=True, blank=True)
    correct_answer = models.JSONField()
    explanation = models.TextField(null=True, blank=True)
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_questions",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "questions"
        ordering = ["-created_at", "id"]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "course", "lesson", "reviewed_by")
        if self.course_id and self.lesson_id and self.lesson.course_id != self.course_id:
            raise ValidationError({"lesson": "The lesson must belong to the question's course."})

    def __str__(self):
        return self.stem[:80]


class QuestionTopic(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="question_topics",
    )
    question = models.ForeignKey(
        "assessments.Question",
        on_delete=models.PROTECT,
        related_name="question_topics",
    )
    topic = models.ForeignKey(
        "assessments.Topic",
        on_delete=models.PROTECT,
        related_name="question_topics",
    )

    class Meta:
        db_table = "question_topics"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "topic"],
                name="unique_topic_per_question",
            )
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "question", "topic")

    def __str__(self):
        return f"Question {self.question_id}: Topic {self.topic_id}"


class Exam(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="exams",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="exams",
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.PROTECT,
        related_name="exams",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    passing_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_attempts = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    proctoring_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exams"
        ordering = ["-created_at", "id"]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "course", "lesson")
        if self.lesson_id and self.course_id and self.lesson.course_id != self.course_id:
            raise ValidationError({"lesson": "The lesson must belong to the exam's course."})

    def __str__(self):
        return self.title


class ExamQuestion(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="exam_questions",
    )
    exam = models.ForeignKey(
        "assessments.Exam",
        on_delete=models.PROTECT,
        related_name="exam_questions",
    )
    question = models.ForeignKey(
        "assessments.Question",
        on_delete=models.PROTECT,
        related_name="exam_questions",
    )
    position = models.IntegerField(default=1)
    points_override = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        db_table = "exam_questions"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "question"],
                name="unique_question_per_exam",
            )
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "exam", "question")

    def __str__(self):
        return f"Exam {self.exam_id}: Question {self.question_id}"


class ExamAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        GRADED = "graded", "Graded"

    class ReviewStatus(models.TextChoices):
        CLEAN = "clean", "Clean"
        FLAGGED = "flagged", "Flagged"
        CLEARED = "cleared", "Cleared"
        VOID = "void", "Void"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="exam_attempts",
    )
    exam = models.ForeignKey(
        "assessments.Exam",
        on_delete=models.PROTECT,
        related_name="exam_attempts",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exam_attempts",
    )
    attempt_number = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    passed = models.BooleanField(null=True, blank=True)
    proctoring_review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.CLEAN,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_exam_attempts",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "exam_attempts"
        ordering = ["-started_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "student", "attempt_number"],
                name="unique_student_attempt_number_per_exam",
            )
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "exam", "student", "reviewed_by")
        if self.student_id and self.student.role != User.Role.STUDENT:
            raise ValidationError({"student": "The attempting user must be a student."})

    def __str__(self):
        return f"Exam {self.exam_id}: Student {self.student_id}, attempt {self.attempt_number}"


class Answer(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="answers",
    )
    attempt = models.ForeignKey(
        "assessments.ExamAttempt",
        on_delete=models.PROTECT,
        related_name="answers",
    )
    question = models.ForeignKey(
        "assessments.Question",
        on_delete=models.PROTECT,
        related_name="answers",
    )
    selected_option = models.JSONField(null=True, blank=True)
    text_answer = models.TextField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    answered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "answers"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_question_per_attempt",
            )
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "attempt", "question")

    def __str__(self):
        return f"Attempt {self.attempt_id}: Question {self.question_id}"
