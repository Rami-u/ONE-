from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student
from apps.assessments.models import Exam, ExamAttempt, ExamQuestion, Question
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import (
    create_exam,
    create_exam_attempt,
    create_question,
)
from apps.courses.tests.helpers import create_course
from apps.enrollments.models import CourseEnrollment
from apps.enrollments.tests.helpers import create_enrollment

FORBIDDEN_KEYS = (
    "passing_score",
    "questions",
    "options",
    "correct_answer",
    "explanation",
    "status",
    "lesson",
)


class StudentExamBase(ContentApiBase):
    def setUp(self):
        self.enroll(self.approved_student, self.alpha_course)
        self.login(self.approved_student)

    def enroll(self, student, course, status=CourseEnrollment.Status.ACTIVE):
        return create_enrollment(self.alpha, student, course, status=status)

    def list_url(self, slug="alpha"):
        return reverse("exam-list-create", kwargs={"slug": slug})

    def detail_url(self, exam_id, slug="alpha"):
        return reverse("exam-detail", kwargs={"slug": slug, "exam_id": exam_id})

    def published(self, course=None, **fields):
        fields.setdefault("status", Exam.Status.PUBLISHED)
        return create_exam(self.alpha, course or self.alpha_course, **fields)

    def add_question(self, exam, points="1.00", position=1, override=None):
        question = create_question(self.alpha, points=points, status=Question.Status.APPROVED)
        ExamQuestion.objects.create(
            workspace=self.alpha,
            exam=exam,
            question=question,
            position=position,
            points_override=override,
        )
        return question

    def listed_ids(self):
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200, response.data)
        return [item["id"] for item in response.data["results"]]


class StudentExamVisibilityTests(StudentExamBase):
    def test_sees_published_exam_in_enrolled_course(self):
        exam = self.published()
        self.assertEqual(self.listed_ids(), [exam.pk])

    def test_draft_and_archived_are_hidden(self):
        self.published(status=Exam.Status.DRAFT, title="D")
        self.published(status=Exam.Status.ARCHIVED, title="A")
        self.assertEqual(self.listed_ids(), [])

    def test_not_enrolled_course_is_hidden(self):
        other = create_course(self.alpha, title="Other")
        self.published(course=other)
        self.assertEqual(self.listed_ids(), [])

    def test_pending_payment_and_withdrawn_enrollments_are_hidden(self):
        for status in (
            CourseEnrollment.Status.PENDING_PAYMENT,
            CourseEnrollment.Status.WITHDRAWN,
        ):
            with self.subTest(status=status):
                CourseEnrollment.objects.filter(student=self.approved_student).update(
                    status=status
                )
                self.published()
                self.assertEqual(self.listed_ids(), [])

    def test_other_students_enrollment_does_not_count(self):
        other_student = create_student(
            self.alpha,
            email="other@alpha.test",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        other_course = create_course(self.alpha, title="Other")
        self.enroll(other_student, other_course)
        self.published(course=other_course)
        self.assertEqual(self.listed_ids(), [])

    def test_other_workspace_exam_is_hidden(self):
        create_exam(self.beta, self.beta_course, status=Exam.Status.PUBLISHED)
        self.assertEqual(self.listed_ids(), [])

    def test_pending_student_is_403(self):
        self.login(self.pending_student)
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_student_of_other_workspace_is_403(self):
        beta_student = create_student(
            self.beta,
            email="student@beta.test",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.login(beta_student)
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_anonymous_is_401_or_403(self):
        self.client.logout()
        self.assertIn(self.client.get(self.list_url()).status_code, (401, 403))


class StudentExamFieldsTests(StudentExamBase):
    def test_fields_and_no_leaks(self):
        exam = self.published(
            title="Quiz",
            description="About benzene",
            duration_minutes=20,
            max_attempts=3,
            proctoring_enabled=True,
            passing_score="60.00",
        )
        self.add_question(exam, points="2.00", position=1)
        self.add_question(exam, points="3.00", position=2, override=Decimal("4.50"))
        response = self.client.get(self.list_url())
        item = response.data["results"][0]
        self.assertEqual(
            set(item),
            {
                "id",
                "title",
                "description",
                "course",
                "duration_minutes",
                "max_attempts",
                "proctoring_enabled",
                "question_count",
                "total_points",
                "attempts_used",
                "in_progress_attempt_id",
            },
        )
        self.assertEqual(item["course"], {"id": self.alpha_course.pk, "title": "Alpha course"})
        self.assertEqual(item["question_count"], 2)
        self.assertEqual(item["total_points"], "6.50")
        self.assertEqual(item["duration_minutes"], 20)
        self.assertEqual(item["max_attempts"], 3)
        self.assertTrue(item["proctoring_enabled"])
        for key in FORBIDDEN_KEYS:
            self.assertNotIn(key, item)

    def test_detail_has_same_shape_and_no_leaks(self):
        exam = self.published(passing_score="60.00")
        self.add_question(exam)
        response = self.client.get(self.detail_url(exam.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["id"], exam.pk)
        for key in FORBIDDEN_KEYS:
            self.assertNotIn(key, response.data)

    def test_empty_attempts_defaults(self):
        self.published()
        item = self.client.get(self.list_url()).data["results"][0]
        self.assertEqual(item["attempts_used"], 0)
        self.assertIsNone(item["in_progress_attempt_id"])

    def test_attempts_used_and_in_progress_id(self):
        exam = self.published(max_attempts=3)
        create_exam_attempt(
            self.alpha,
            exam,
            self.approved_student,
            attempt_number=1,
            status=ExamAttempt.Status.SUBMITTED,
        )
        current = create_exam_attempt(
            self.alpha, exam, self.approved_student, attempt_number=2
        )
        item = self.client.get(self.list_url()).data["results"][0]
        self.assertEqual(item["attempts_used"], 2)
        self.assertEqual(item["in_progress_attempt_id"], current.pk)

    def test_other_students_attempts_are_not_counted(self):
        exam = self.published()
        other_student = create_student(
            self.alpha,
            email="other@alpha.test",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        create_exam_attempt(self.alpha, exam, other_student)
        item = self.client.get(self.list_url()).data["results"][0]
        self.assertEqual(item["attempts_used"], 0)
        self.assertIsNone(item["in_progress_attempt_id"])

    def test_counts_are_not_multiplied_by_attempts(self):
        exam = self.published(max_attempts=3)
        self.add_question(exam, points="2.00")
        for number in (1, 2):
            create_exam_attempt(
                self.alpha,
                exam,
                self.approved_student,
                attempt_number=number,
                status=ExamAttempt.Status.SUBMITTED,
            )
        item = self.client.get(self.list_url()).data["results"][0]
        self.assertEqual(item["question_count"], 1)
        self.assertEqual(item["total_points"], "2.00")
        self.assertEqual(item["attempts_used"], 2)


class StudentExamDetailAccessTests(StudentExamBase):
    def test_unavailable_exams_are_404(self):
        other = create_course(self.alpha, title="Other")
        cases = {
            "draft": self.published(status=Exam.Status.DRAFT),
            "archived": self.published(status=Exam.Status.ARCHIVED),
            "not_enrolled": self.published(course=other),
            "other_workspace": create_exam(
                self.beta, self.beta_course, status=Exam.Status.PUBLISHED
            ),
        }
        for name, exam in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.client.get(self.detail_url(exam.pk)).status_code, 404)

    def test_student_cannot_write_or_use_teacher_endpoints(self):
        exam = self.published()
        self.assertEqual(
            self.client.post(self.list_url(), {}, format="json").status_code, 403
        )
        self.assertEqual(
            self.client.patch(self.detail_url(exam.pk), {"title": "x"}, format="json").status_code,
            403,
        )
        questions_url = reverse("exam-questions", kwargs={"slug": "alpha", "exam_id": exam.pk})
        self.assertEqual(self.client.get(questions_url).status_code, 403)

    def test_teacher_still_sees_everything(self):
        self.published(status=Exam.Status.DRAFT)
        self.published()
        self.login(self.alpha_teacher)
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIn("passing_score", response.data["results"][0])


class StudentExamQueryCountTests(StudentExamBase):
    def count_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        return len(ctx)

    def test_query_count_does_not_grow_with_exams(self):
        for i in range(2):
            exam = self.published(title=f"E{i}")
            self.add_question(exam)
        self.count_queries()  # warm up
        few = self.count_queries()
        for i in range(2, 8):
            exam = self.published(title=f"E{i}")
            self.add_question(exam)
            create_exam_attempt(self.alpha, exam, self.approved_student)
        many = self.count_queries()
        self.assertEqual(few, many)