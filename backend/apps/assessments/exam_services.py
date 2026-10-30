from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Exam, ExamAttempt, ExamQuestion, Question

FROZEN_WHEN_ATTEMPTS = ("duration_minutes", "passing_score", "proctoring_enabled")


class ExamConflictError(Exception):
    """Raised when an exam change is not allowed in its current state (HTTP 409)."""


def _django_errors_to_drf(exc):
    if hasattr(exc, "message_dict"):
        return serializers.ValidationError(exc.message_dict)
    return serializers.ValidationError({"non_field_errors": exc.messages})


def exam_has_attempts(exam):
    return ExamAttempt.objects.filter(exam=exam).exists()


def create_exam(workspace, validated_data):
    exam = Exam(workspace=workspace, status=Exam.Status.DRAFT, **validated_data)
    try:
        exam.full_clean()
    except DjangoValidationError as exc:
        raise _django_errors_to_drf(exc) from exc
    exam.save()
    return exam


def update_exam(exam_id, workspace, validated_data):
    data = dict(validated_data)
    with transaction.atomic():
        exam = Exam.objects.select_for_update(of=("self",)).get(
            pk=exam_id, workspace=workspace
        )
        if exam.status == Exam.Status.ARCHIVED:
            raise ExamConflictError("An archived exam cannot be edited.")
        if exam.status == Exam.Status.PUBLISHED:
            _check_published_rules(exam, data)
        for field, value in data.items():
            setattr(exam, field, value)
        try:
            exam.full_clean()
        except DjangoValidationError as exc:
            raise _django_errors_to_drf(exc) from exc
        exam.save()
    return exam


def _check_published_rules(exam, data):
    if "lesson" in data and data["lesson"] != exam.lesson:
        raise ExamConflictError("The lesson cannot be changed after publishing.")
    if not exam_has_attempts(exam):
        return
    for field in FROZEN_WHEN_ATTEMPTS:
        if field in data and data[field] != getattr(exam, field):
            raise ExamConflictError(
                f"{field} cannot be changed: this exam already has attempts."
            )
    if "max_attempts" in data and data["max_attempts"] < exam.max_attempts:
        raise ExamConflictError(
            "max_attempts can only be increased: this exam already has attempts."
        )


def replace_exam_questions(exam_id, workspace, items):
    """Replace the ordered question list of an exam.

    `items` is a list of dicts: {"question_id": int, "points_override": Decimal|None}.
    Position is the index + 1. Everything runs in one transaction.
    """
    with transaction.atomic():
        exam = Exam.objects.select_for_update(of=("self",)).get(
            pk=exam_id, workspace=workspace
        )
        if exam.status == Exam.Status.ARCHIVED:
            raise ExamConflictError("An archived exam cannot be edited.")
        if exam.status == Exam.Status.PUBLISHED and exam_has_attempts(exam):
            raise ExamConflictError(
                "The question list cannot be changed: this exam already has attempts."
            )

        ids = [item["question_id"] for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                {"questions": ["A question cannot appear twice in the same exam."]}
            )

        questions = {
            q.pk: q
            for q in Question.objects.filter(workspace=workspace, pk__in=ids).select_related(
                "lesson"
            )
        }
        errors = []
        for index, item in enumerate(items):
            question = questions.get(item["question_id"])
            if question is None:
                errors.append(f"Item {index + 1}: unknown question id {item['question_id']}.")
                continue
            if question.status != Question.Status.APPROVED:
                errors.append(f"Item {index + 1}: question {question.pk} is not approved.")
            if question.course_id is not None and question.course_id != exam.course_id:
                errors.append(
                    f"Item {index + 1}: question {question.pk} belongs to a different course."
                )
            if question.lesson_id is not None and question.lesson.course_id != exam.course_id:
                errors.append(
                    f"Item {index + 1}: question {question.pk} has a lesson from a different course."
                )
            override = item.get("points_override")
            if override is not None and override <= Decimal("0"):
                errors.append(f"Item {index + 1}: points_override must be greater than 0.")
        if errors:
            raise serializers.ValidationError({"questions": errors})

        ExamQuestion.objects.filter(exam=exam).delete()
        for position, item in enumerate(items, start=1):
            link = ExamQuestion(
                workspace=workspace,
                exam=exam,
                question=questions[item["question_id"]],
                position=position,
                points_override=item.get("points_override"),
            )
            try:
                link.full_clean()
            except DjangoValidationError as exc:
                raise _django_errors_to_drf(exc) from exc
            link.save()
    return exam


def publish_exam(exam_id, workspace):
    with transaction.atomic():
        exam = Exam.objects.select_for_update(of=("self",)).get(
            pk=exam_id, workspace=workspace
        )
        if exam.status != Exam.Status.DRAFT:
            raise ExamConflictError(f"Only a draft exam can be published (it is {exam.status}).")

        questions = list(
            Question.objects.filter(exam_questions__exam=exam).distinct()
        )
        errors = {}
        if not questions:
            errors["questions"] = ["Add at least one question."]
        elif any(q.status != Question.Status.APPROVED for q in questions):
            errors["questions"] = ["All questions must still be approved."]
        if exam.passing_score is not None and not (
            Decimal("0") <= exam.passing_score <= Decimal("100")
        ):
            errors["passing_score"] = ["Must be between 0 and 100."]
        if errors:
            raise serializers.ValidationError(errors)

        exam.status = Exam.Status.PUBLISHED
        exam.published_at = timezone.now()
        exam.save(update_fields=["status", "published_at"])
    return exam


def archive_exam(exam_id, workspace):
    with transaction.atomic():
        exam = Exam.objects.select_for_update(of=("self",)).get(
            pk=exam_id, workspace=workspace
        )
        if exam.status not in (Exam.Status.DRAFT, Exam.Status.PUBLISHED):
            raise ExamConflictError(f"Cannot archive a {exam.status} exam.")
        exam.status = Exam.Status.ARCHIVED
        exam.save(update_fields=["status"])
    return exam