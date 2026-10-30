from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.enrollments.models import CourseEnrollment

from .models import Exam, ExamAttempt

# Used when an exam has no duration_minutes set.
DEFAULT_DURATION_MINUTES = 180


def exam_duration_minutes(exam):
    return exam.duration_minutes or DEFAULT_DURATION_MINUTES


def attempt_end_time(attempt):
    return attempt.started_at + timedelta(minutes=exam_duration_minutes(attempt.exam))


def remaining_seconds(attempt, now=None):
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return 0
    now = now or timezone.now()
    return max(0, int((attempt_end_time(attempt) - now).total_seconds()))


def _close_attempt(attempt, when):
    attempt.status = ExamAttempt.Status.SUBMITTED
    attempt.submitted_at = when
    attempt.save(update_fields=["status", "submitted_at"])

    if attempt.exam.proctoring_enabled:
        from apps.proctoring.services import finish_proctoring_safely

        attempt_id = attempt.id
        transaction.on_commit(lambda: finish_proctoring_safely(attempt_id))


class AttemptStartError(Exception):
    """Raised when a student may not start an attempt; carries a message."""


class AttemptSubmitError(Exception):
    """Raised when an attempt cannot be submitted; carries a message."""


@transaction.atomic
def start_attempt(student, exam, workspace):
    """Start (or resume) the student's attempt on a published exam.

    Returns (attempt, created). Returns (None, False) when
    the student has no attempts left. The closing of an expired attempt is
    committed because this function returns instead of raising in that case.

    The student's enrollment row is locked so two simultaneous start requests
    are handled one after the other.
    """
    has_enrollment = (
        CourseEnrollment.objects.select_for_update()
        .filter(
            workspace=workspace,
            student=student,
            course_id=exam.course_id,
            status=CourseEnrollment.Status.ACTIVE,
        )
        .exists()
    )
    if not has_enrollment:
        raise AttemptStartError("An active enrollment in the course is required.")

    now = timezone.now()
    attempts = list(
        ExamAttempt.objects.select_for_update(of=("self",))
        .select_related("exam")
        .filter(workspace=workspace, exam=exam, student=student)
        .order_by("attempt_number")
    )

    current = next(
        (a for a in attempts if a.status == ExamAttempt.Status.IN_PROGRESS), None
    )
    if current is not None:
        if attempt_end_time(current) > now:
            return current, False
        # Time ran out earlier: close it; it still counts as an attempt.
        _close_attempt(current, attempt_end_time(current))

    if len(attempts) >= exam.max_attempts:
        return None, False

    attempt = ExamAttempt.objects.create(
        workspace=workspace,
        exam=exam,
        student=student,
        attempt_number=len(attempts) + 1,
        status=ExamAttempt.Status.IN_PROGRESS,
        started_at=now,
    )
    return attempt, True


@transaction.atomic
def submit_attempt(attempt_id, student, workspace):
    """Finish the student's own in-progress attempt.

    Returns the attempt, or None if it does not exist for this student in this
    workspace. Raises AttemptSubmitError if it is already finished.
    A late submit is recorded at the deadline, not at the current time.
    """
    attempt = (
        ExamAttempt.objects.select_for_update(of=("self",))
        .select_related("exam")
        .filter(pk=attempt_id, workspace=workspace, student=student)
        .first()
    )
    if attempt is None:
        return None
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        raise AttemptSubmitError("This attempt is already finished.")
    _close_attempt(attempt, min(timezone.now(), attempt_end_time(attempt)))
    return attempt


def get_exam_for_start(workspace, exam_id):
    return Exam.objects.filter(
        workspace=workspace, pk=exam_id, status=Exam.Status.PUBLISHED
    ).first()
