from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.assessments.attempt_services import DEFAULT_DURATION_MINUTES
from apps.assessments.models import Exam, ExamAttempt
from apps.courses.tests.helpers import create_course
from apps.enrollments.models import CourseEnrollment
from apps.enrollments.tests.helpers import create_enrollment

from .helpers import create_exam, create_exam_attempt


def approved_student(workspace, email):
    return create_student(
        workspace, email=email, approval_status=User.ApprovalStatus.APPROVED
    )


def approved_teacher(workspace, email):
    teacher = create_teacher(workspace, email=email)
    teacher.approval_status = User.ApprovalStatus.APPROVED
    teacher.save(update_fields=["approval_status"])
    return teacher


class AttemptApiBase(APITestCase):
    def setUp(self):
        self.ws_a = create_workspace("alpha")
        self.ws_b = create_workspace("beta")

        self.teacher_a = approved_teacher(self.ws_a, "teacher-a@example.com")
        self.teacher_b = approved_teacher(self.ws_b, "teacher-b@example.com")
        self.student = approved_student(self.ws_a, "s1@example.com")
        self.other_student = approved_student(self.ws_a, "s2@example.com")
        self.student_b = approved_student(self.ws_b, "sb@example.com")

        self.course = create_course(self.ws_a, title="Course A")
        self.course_b = create_course(self.ws_b, title="Course B")

        active = CourseEnrollment.Status.ACTIVE
        self.enr = create_enrollment(self.ws_a, self.student, self.course, status=active)
        create_enrollment(self.ws_a, self.other_student, self.course, status=active)
        create_enrollment(self.ws_b, self.student_b, self.course_b, status=active)

        self.exam = create_exam(
            self.ws_a,
            self.course,
            title="Exam A",
            status=Exam.Status.PUBLISHED,
            duration_minutes=60,
            max_attempts=2,
        )

    def start_url(self, exam=None, slug="alpha"):
        exam = exam or self.exam
        return f"/api/v1/workspaces/{slug}/exams/{exam.pk}/attempts/start/"

    def submit_url(self, attempt, slug="alpha"):
        return f"/api/v1/workspaces/{slug}/attempts/{attempt.pk}/submit/"

    def detail_url(self, attempt, slug="alpha"):
        return f"/api/v1/workspaces/{slug}/attempts/{attempt.pk}/"


class StartAttemptTests(AttemptApiBase):
    def test_start_creates_in_progress_attempt(self):
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "in_progress")
        self.assertEqual(response.data["attempt_number"], 1)
        self.assertEqual(response.data["exam"], self.exam.pk)
        self.assertGreater(response.data["remaining_seconds"], 3500)
        attempt = ExamAttempt.objects.get(pk=response.data["id"])
        self.assertEqual(attempt.workspace_id, self.ws_a.pk)
        self.assertEqual(attempt.student_id, self.student.pk)

    def test_start_again_resumes_same_attempt(self):
        self.client.force_login(self.student)
        first = self.client.post(self.start_url(), {}, format="json")
        second = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(ExamAttempt.objects.count(), 1)

    def test_exam_without_duration_uses_default(self):
        exam = create_exam(
            self.ws_a, self.course, status=Exam.Status.PUBLISHED, duration_minutes=None
        )
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(exam), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreater(
            response.data["remaining_seconds"], (DEFAULT_DURATION_MINUTES - 1) * 60
        )

    def test_consent_required_when_proctoring_enabled(self):
        self.exam.proctoring_enabled = True
        self.exam.save()
        self.client.force_login(self.student)
        for body in ({}, {"consent": False}):
            response = self.client.post(self.start_url(), body, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("consent", response.data)
        self.assertEqual(ExamAttempt.objects.count(), 0)

        ok = self.client.post(self.start_url(), {"consent": True}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_consent_not_required_without_proctoring(self):
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unpublished_exam_is_not_found(self):
        for exam_status in (Exam.Status.DRAFT, Exam.Status.ARCHIVED):
            exam = create_exam(self.ws_a, self.course, status=exam_status)
            self.client.force_login(self.student)
            response = self.client.post(self.start_url(exam), {}, format="json")
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_active_enrollment(self):
        CourseEnrollment.objects.filter(pk=self.enr.pk).update(
            status=CourseEnrollment.Status.PENDING_PAYMENT
        )
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ExamAttempt.objects.count(), 0)

        CourseEnrollment.objects.filter(pk=self.enr.pk).update(
            status=CourseEnrollment.Status.WITHDRAWN
        )
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_max_attempts_enforced(self):
        self.client.force_login(self.student)
        for number in (1, 2):
            started = self.client.post(self.start_url(), {}, format="json")
            self.assertEqual(started.data["attempt_number"], number)
            attempt = ExamAttempt.objects.get(pk=started.data["id"])
            self.client.post(self.submit_url(attempt))
        third = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(third.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ExamAttempt.objects.count(), 2)

    def test_expired_attempt_is_closed_and_counts(self):
        expired = create_exam_attempt(
            self.ws_a,
            self.exam,
            self.student,
            attempt_number=1,
            started_at=timezone.now() - timedelta(minutes=61),
        )
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["attempt_number"], 2)
        expired.refresh_from_db()
        self.assertEqual(expired.status, ExamAttempt.Status.SUBMITTED)
        self.assertIsNotNone(expired.submitted_at)

    def test_expired_last_attempt_is_closed_even_when_none_left(self):
        self.exam.max_attempts = 1
        self.exam.save()
        expired = create_exam_attempt(
            self.ws_a,
            self.exam,
            self.student,
            attempt_number=1,
            started_at=timezone.now() - timedelta(minutes=90),
        )
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        expired.refresh_from_db()
        self.assertEqual(expired.status, ExamAttempt.Status.SUBMITTED)

    def test_other_students_attempts_do_not_count(self):
        create_exam_attempt(self.ws_a, self.exam, self.other_student, attempt_number=1)
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["attempt_number"], 1)


class StartAttemptPermissionTests(AttemptApiBase):
    def test_anonymous_is_rejected(self):
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_teacher_cannot_start(self):
        self.client.force_login(self.teacher_a)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unapproved_student_cannot_start(self):
        pending = create_student(self.ws_a, email="pending@example.com")
        create_enrollment(
            self.ws_a, pending, self.course, status=CourseEnrollment.Status.ACTIVE
        )
        self.client.force_login(pending)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_of_another_workspace_cannot_start(self):
        self.client.force_login(self.student_b)
        response = self.client.post(self.start_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ExamAttempt.objects.count(), 0)

    def test_exam_of_another_workspace_is_not_found(self):
        exam_b = create_exam(
            self.ws_b, self.course_b, status=Exam.Status.PUBLISHED, duration_minutes=30
        )
        self.client.force_login(self.student)
        response = self.client.post(self.start_url(exam_b), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_workspace_is_not_found(self):
        self.client.force_login(self.student)
        response = self.client.post(
            self.start_url(slug="missing"), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SubmitAttemptTests(AttemptApiBase):
    def start(self, user=None):
        self.client.force_login(user or self.student)
        response = self.client.post(self.start_url(), {}, format="json")
        return ExamAttempt.objects.get(pk=response.data["id"])

    def test_submit_closes_attempt(self):
        attempt = self.start()
        response = self.client.post(self.submit_url(attempt))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "submitted")
        self.assertEqual(response.data["remaining_seconds"], 0)
        self.assertIsNotNone(response.data["submitted_at"])
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, ExamAttempt.Status.SUBMITTED)

    def test_submit_twice_is_rejected(self):
        attempt = self.start()
        self.client.post(self.submit_url(attempt))
        response = self.client.post(self.submit_url(attempt))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_submit_another_students_attempt(self):
        attempt = self.start(self.student)
        self.client.force_login(self.other_student)
        response = self.client.post(self.submit_url(attempt))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, ExamAttempt.Status.IN_PROGRESS)

    def test_teacher_cannot_submit(self):
        attempt = self.start()
        self.client.force_login(self.teacher_a)
        response = self.client.post(self.submit_url(attempt))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_workspace_submit_is_blocked(self):
        attempt = self.start()
        self.client.force_login(self.student_b)
        response = self.client.post(self.submit_url(attempt))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.post(self.submit_url(attempt, slug="beta"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, ExamAttempt.Status.IN_PROGRESS)


class AttemptDetailTests(AttemptApiBase):
    def setUp(self):
        super().setUp()
        self.attempt = create_exam_attempt(
            self.ws_a, self.exam, self.student, attempt_number=1
        )

    def test_owner_sees_state_and_remaining_time(self):
        self.client.force_login(self.student)
        response = self.client.get(self.detail_url(self.attempt))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "in_progress")
        self.assertGreater(response.data["remaining_seconds"], 3500)
        self.assertLessEqual(response.data["remaining_seconds"], 3600)

    def test_finished_attempt_has_zero_remaining(self):
        self.attempt.status = ExamAttempt.Status.SUBMITTED
        self.attempt.save()
        self.client.force_login(self.student)
        response = self.client.get(self.detail_url(self.attempt))
        self.assertEqual(response.data["remaining_seconds"], 0)

    def test_expired_in_progress_attempt_has_zero_remaining(self):
        ExamAttempt.objects.filter(pk=self.attempt.pk).update(
            started_at=timezone.now() - timedelta(hours=3)
        )
        self.client.force_login(self.student)
        response = self.client.get(self.detail_url(self.attempt))
        self.assertEqual(response.data["remaining_seconds"], 0)

    def test_other_student_gets_not_found(self):
        self.client.force_login(self.other_student)
        response = self.client.get(self.detail_url(self.attempt))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_workspace_teacher_can_view(self):
        self.client.force_login(self.teacher_a)
        response = self.client.get(self.detail_url(self.attempt))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.attempt.pk)

    def test_teacher_of_another_workspace_is_blocked(self):
        self.client.force_login(self.teacher_b)
        response = self.client.get(self.detail_url(self.attempt))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.get(self.detail_url(self.attempt, slug="beta"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_of_another_workspace_is_blocked(self):
        self.client.force_login(self.student_b)
        response = self.client.get(self.detail_url(self.attempt))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_is_rejected(self):
        response = self.client.get(self.detail_url(self.attempt))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
