from decimal import Decimal

from apps.assessments.models import Question, Topic


def create_topic(workspace, *, course=None, name="Test topic", slug="test-topic", **fields):
    return Topic.objects.create(
        workspace=workspace,
        course=course,
        name=name,
        slug=slug,
        **fields,
    )


def create_question(
    workspace,
    *,
    course=None,
    lesson=None,
    question_type=Question.QuestionType.MCQ,
    stem="What is two plus two?",
    correct_answer="4",
    points="1.00",
    **fields,
):
    return Question.objects.create(
        workspace=workspace,
        course=course,
        lesson=lesson,
        question_type=question_type,
        stem=stem,
        correct_answer=correct_answer,
        points=Decimal(str(points)),
        **fields,
    )
