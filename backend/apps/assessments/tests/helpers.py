from decimal import Decimal

from apps.assessments.models import Answer, Exam, ExamAttempt, Question, Topic


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


def create_exam(workspace, course, *, title="Test exam", **fields):
    return Exam.objects.create(workspace=workspace, course=course, title=title, **fields)


def create_exam_attempt(workspace, exam, student, **fields):
    return ExamAttempt.objects.create(workspace=workspace, exam=exam, student=student, **fields)


def create_answer(workspace, attempt, question, **fields):
    return Answer.objects.create(workspace=workspace, attempt=attempt, question=question, **fields)
