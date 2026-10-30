"""Proctoring services (Track A).

Only record_consent exists for now. The remaining services from the work
split (process_frame, record_event, save_snapshot, finish_attempt,
finish_proctoring_safely) are added in later commits.

Do not import from apps.assessments.attempt_views here (circular import).
"""

from apps.assessments.models import ExamAttempt


def record_consent(attempt, now):
    """Save the first consent time on the attempt.

    The time is written only if consent_given_at is still empty, so a
    resumed attempt keeps its original time. The filter makes the check and
    the write one database statement, so two parallel requests cannot
    overwrite each other.
    """
    updated = ExamAttempt.objects.filter(
        pk=attempt.pk, consent_given_at__isnull=True
    ).update(consent_given_at=now)
    if updated:
        attempt.consent_given_at = now