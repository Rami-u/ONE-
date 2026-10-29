from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import ExamAttempt, Question, QuestionTopic, Topic

CONTENT_FIELDS = ("stem", "options", "correct_answer", "points")


class QuestionConflictError(Exception):
    """Raised when a question change is not allowed in its current state (HTTP 409)."""


def _django_errors_to_drf(exc):
    if hasattr(exc, "message_dict"):
        return serializers.ValidationError(exc.message_dict)
    return serializers.ValidationError({"non_field_errors": exc.messages})


def question_has_attempts(question):
    return ExamAttempt.objects.filter(exam__exam_questions__question=question).exists()


def _replace_topics(question, topic_ids):
    topics = list(Topic.objects.filter(workspace=question.workspace, pk__in=topic_ids))
    if len(topics) != len(set(topic_ids)):
        raise serializers.ValidationError({"topic_ids": ["Unknown topic id."]})
    QuestionTopic.objects.filter(question=question).delete()
    for topic in topics:
        link = QuestionTopic(workspace=question.workspace, question=question, topic=topic)
        link.full_clean()
        link.save()


def create_question(workspace, validated_data):
    data = dict(validated_data)
    topic_ids = data.pop("topic_ids", None)
    with transaction.atomic():
        question = Question(
            workspace=workspace,
            source_type=Question.SourceType.MANUAL,
            **data,
        )
        try:
            question.full_clean(exclude=["correct_answer"])
        except DjangoValidationError as exc:
            raise _django_errors_to_drf(exc) from exc
        question.save()
        if topic_ids:
            _replace_topics(question, topic_ids)
    return question


def update_question(question_id, workspace, validated_data):
    data = dict(validated_data)
    data.pop("status", None)
    data.pop("question_type", None)
    topic_ids = data.pop("topic_ids", None)
    with transaction.atomic():
        question = Question.objects.select_for_update(of=("self",)).get(
            pk=question_id, workspace=workspace
        )
        if question.status == Question.Status.ARCHIVED:
            raise QuestionConflictError("An archived question cannot be edited.")
        if any(field in data for field in CONTENT_FIELDS) and question_has_attempts(question):
            raise QuestionConflictError(
                "This question is part of an exam that already has attempts; its content is frozen."
            )
        for field, value in data.items():
            setattr(question, field, value)
        try:
            question.full_clean(exclude=["correct_answer"])
        except DjangoValidationError as exc:
            raise _django_errors_to_drf(exc) from exc
        question.save()
        if topic_ids is not None:
            _replace_topics(question, topic_ids)
    return question


def _change_status(question_id, workspace, reviewer, allowed_from, new_status, set_reviewer):
    with transaction.atomic():
        question = Question.objects.select_for_update(of=("self",)).get(
            pk=question_id, workspace=workspace
        )
        if question.status not in allowed_from:
            raise QuestionConflictError(
                f"Cannot move a {question.status} question to {new_status}."
            )
        question.status = new_status
        if set_reviewer:
            question.reviewed_by = reviewer
            question.reviewed_at = timezone.now()
        question.full_clean(exclude=["correct_answer"])
        question.save()
    return question


def approve_question(question_id, workspace, reviewer):
    return _change_status(
        question_id, workspace, reviewer,
        {Question.Status.DRAFT}, Question.Status.APPROVED, True,
    )


def reject_question(question_id, workspace, reviewer):
    return _change_status(
        question_id, workspace, reviewer,
        {Question.Status.DRAFT}, Question.Status.REJECTED, True,
    )


def archive_question(question_id, workspace, reviewer):
    return _change_status(
        question_id, workspace, reviewer,
        {Question.Status.DRAFT, Question.Status.APPROVED, Question.Status.REJECTED},
        Question.Status.ARCHIVED, False,
    )