from django.urls import reverse

from apps.assessments.models import Exam
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import create_exam, create_exam_attempt
from apps.courses.tests.helpers import create_lesson


class ExamFreezeBase(ContentApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def detail_url(self, exam_id, slug="alpha"):
        return reverse("exam-detail", kwargs={"slug": slug, "exam_id": exam_id})

    def patch(self, exam, **body):
        return self.client.patch(self.detail_url(exam.pk), body, format="json")

    def make_exam(self, status=Exam.Status.DRAFT, with_attempt=False, **fields):
        fields.setdefault("duration_minutes", 30)
        fields.setdefault("passing_score", "50.00")
        fields.setdefault("max_attempts", 2)
        exam = create_exam(self.alpha, self.alpha_course, status=status, **fields)
        if with_attempt:
            create_exam_attempt(self.alpha, exam, self.approved_student)
        return exam


class DraftExamEditTests(ExamFreezeBase):
    def test_all_settings_editable(self):
        exam = self.make_exam()
        response = self.patch(
            exam,
            title="New",
            description="d",
            duration_minutes=45,
            passing_score="70",
            max_attempts=1,
            proctoring_enabled=True,
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["duration_minutes"], 45)
        self.assertTrue(response.data["proctoring_enabled"])

    def test_lesson_editable(self):
        exam = self.make_exam()
        lesson = create_lesson(self.alpha, self.alpha_course)
        response = self.patch(exam, lesson=lesson.pk)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["lesson"], lesson.pk)

    def test_course_cannot_be_changed(self):
        exam = self.make_exam()
        response = self.patch(exam, course=self.alpha_course.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.data)

    def test_status_in_body_is_ignored(self):
        exam = self.make_exam()
        response = self.patch(exam, status="published")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "draft")


class ArchivedExamTests(ExamFreezeBase):
    def test_any_edit_is_409(self):
        exam = self.make_exam(status=Exam.Status.ARCHIVED)
        for body in ({"title": "x"}, {"description": "x"}, {"max_attempts": 5}):
            with self.subTest(body=body):
                self.assertEqual(self.patch(exam, **body).status_code, 409)
        exam.refresh_from_db()
        self.assertNotEqual(exam.title, "x")


class PublishedNoAttemptsTests(ExamFreezeBase):
    def test_settings_editable(self):
        exam = self.make_exam(status=Exam.Status.PUBLISHED)
        response = self.patch(
            exam,
            title="New",
            duration_minutes=60,
            passing_score="80",
            proctoring_enabled=True,
            max_attempts=1,
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["duration_minutes"], 60)
        self.assertEqual(response.data["max_attempts"], 1)

    def test_lesson_change_is_409(self):
        exam = self.make_exam(status=Exam.Status.PUBLISHED)
        lesson = create_lesson(self.alpha, self.alpha_course)
        self.assertEqual(self.patch(exam, lesson=lesson.pk).status_code, 409)


class PublishedWithAttemptsTests(ExamFreezeBase):
    def setUp(self):
        super().setUp()
        self.exam = self.make_exam(status=Exam.Status.PUBLISHED, with_attempt=True)

    def test_title_and_description_allowed(self):
        response = self.patch(self.exam, title="Renamed", description="New text")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["title"], "Renamed")

    def test_duration_change_is_409(self):
        self.assertEqual(self.patch(self.exam, duration_minutes=99).status_code, 409)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.duration_minutes, 30)

    def test_passing_score_change_is_409(self):
        self.assertEqual(self.patch(self.exam, passing_score="90").status_code, 409)

    def test_proctoring_change_is_409(self):
        self.assertEqual(self.patch(self.exam, proctoring_enabled=True).status_code, 409)

    def test_lesson_change_is_409(self):
        lesson = create_lesson(self.alpha, self.alpha_course)
        self.assertEqual(self.patch(self.exam, lesson=lesson.pk).status_code, 409)

    def test_max_attempts_decrease_is_409(self):
        self.assertEqual(self.patch(self.exam, max_attempts=1).status_code, 409)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.max_attempts, 2)

    def test_max_attempts_increase_allowed(self):
        response = self.patch(self.exam, max_attempts=5)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["max_attempts"], 5)

    def test_same_value_is_not_a_change(self):
        response = self.patch(
            self.exam,
            duration_minutes=30,
            passing_score="50.00",
            proctoring_enabled=False,
            max_attempts=2,
        )
        self.assertEqual(response.status_code, 200, response.data)