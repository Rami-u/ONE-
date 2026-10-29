from decimal import Decimal

from django.urls import reverse

from apps.assessments.models import Exam, ExamQuestion, Question
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import create_exam, create_question
from apps.courses.tests.helpers import create_course, create_lesson


def exam_payload(course, **overrides):
    payload = {
        "course": course.pk,
        "title": "Midterm",
        "duration_minutes": 30,
        "max_attempts": 2,
    }
    payload.update(overrides)
    return payload


class ExamApiBase(ContentApiBase):
    def list_url(self, slug="alpha"):
        return reverse("exam-list-create", kwargs={"slug": slug})

    def detail_url(self, exam_id, slug="alpha"):
        return reverse("exam-detail", kwargs={"slug": slug, "exam_id": exam_id})

    def link(self, exam, question, position=1, points_override=None):
        return ExamQuestion.objects.create(
            workspace=exam.workspace,
            exam=exam,
            question=question,
            position=position,
            points_override=points_override,
        )


class ExamCreateTests(ExamApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_create_exam_is_draft(self):
        response = self.client.post(self.list_url(), exam_payload(self.alpha_course), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "draft")
        self.assertIsNone(response.data["published_at"])
        self.assertEqual(response.data["question_count"], 0)
        self.assertEqual(response.data["total_points"], "0.00")
        exam = Exam.objects.get(pk=response.data["id"])
        self.assertEqual(exam.workspace, self.alpha)

    def test_create_ignores_status_in_body(self):
        response = self.client.post(
            self.list_url(),
            exam_payload(self.alpha_course, status="published"),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "draft")

    def test_create_with_null_duration_and_passing_score(self):
        response = self.client.post(
            self.list_url(),
            exam_payload(self.alpha_course, duration_minutes=None, passing_score="60"),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["duration_minutes"])
        self.assertEqual(response.data["passing_score"], "60.00")

    def test_create_with_lesson_of_same_course(self):
        lesson = create_lesson(self.alpha, self.alpha_course)
        response = self.client.post(
            self.list_url(), exam_payload(self.alpha_course, lesson=lesson.pk), format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["lesson"], lesson.pk)

    def test_lesson_of_other_course_is_400(self):
        other = create_course(self.alpha, title="Other")
        lesson = create_lesson(self.alpha, other)
        response = self.client.post(
            self.list_url(), exam_payload(self.alpha_course, lesson=lesson.pk), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("lesson", response.data)

    def test_course_of_other_workspace_is_400(self):
        response = self.client.post(
            self.list_url(), exam_payload(self.beta_course), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.data)

    def test_lesson_of_other_workspace_is_400(self):
        lesson = create_lesson(self.beta, self.beta_course)
        response = self.client.post(
            self.list_url(), exam_payload(self.alpha_course, lesson=lesson.pk), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("lesson", response.data)

    def test_missing_course_and_title_is_400(self):
        response = self.client.post(self.list_url(), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.data)
        self.assertIn("title", response.data)

    def test_invalid_numbers_are_400(self):
        for field, value in (
            ("duration_minutes", 0),
            ("max_attempts", 0),
            ("passing_score", "101"),
            ("passing_score", "-1"),
        ):
            with self.subTest(field=field, value=value):
                response = self.client.post(
                    self.list_url(),
                    exam_payload(self.alpha_course, **{field: value}),
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)


class ExamReadTests(ExamApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_question_count_and_total_points(self):
        exam = create_exam(self.alpha, self.alpha_course)
        q1 = create_question(self.alpha, points="2.00", status=Question.Status.APPROVED)
        q2 = create_question(self.alpha, points="3.00", status=Question.Status.APPROVED)
        q3 = create_question(self.alpha, points="1.00", status=Question.Status.APPROVED)
        self.link(exam, q1, 1)
        self.link(exam, q2, 2, points_override=Decimal("4.50"))
        self.link(exam, q3, 3)
        response = self.client.get(self.detail_url(exam.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["question_count"], 3)
        self.assertEqual(response.data["total_points"], "7.50")

    def test_list_counts_are_per_exam(self):
        exam_a = create_exam(self.alpha, self.alpha_course, title="A")
        exam_b = create_exam(self.alpha, self.alpha_course, title="B")
        q1 = create_question(self.alpha, points="2.00", status=Question.Status.APPROVED)
        q2 = create_question(self.alpha, points="5.00", status=Question.Status.APPROVED)
        self.link(exam_a, q1)
        self.link(exam_a, q2, 2)
        self.link(exam_b, q2)
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        by_title = {item["title"]: item for item in response.data["results"]}
        self.assertEqual(by_title["A"]["question_count"], 2)
        self.assertEqual(by_title["A"]["total_points"], "7.00")
        self.assertEqual(by_title["B"]["question_count"], 1)
        self.assertEqual(by_title["B"]["total_points"], "5.00")

    def test_list_query_count_does_not_grow(self):
        for i in range(2):
            create_exam(self.alpha, self.alpha_course, title=f"E{i}")
        with self.assertNumQueries(self.count_list_queries()):
            self.client.get(self.list_url())
        for i in range(2, 6):
            exam = create_exam(self.alpha, self.alpha_course, title=f"E{i}")
            self.link(exam, create_question(self.alpha, status=Question.Status.APPROVED))
        with self.assertNumQueries(self.count_list_queries()):
            self.client.get(self.list_url())

    def count_list_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.list_url())
        return len(ctx)

    def test_list_excludes_other_workspace(self):
        other = create_exam(self.beta, self.beta_course, title="Beta exam")
        response = self.client.get(self.list_url())
        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(other.pk, ids)


class ExamIsolationAndAccessTests(ExamApiBase):
    def setUp(self):
        self.exam = create_exam(self.alpha, self.alpha_course)
        self.beta_exam = create_exam(self.beta, self.beta_course, title="Beta exam")

    def test_other_workspace_exam_is_404(self):
        self.login(self.alpha_teacher)
        for method in ("get", "patch"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.detail_url(self.beta_exam.pk), {"title": "x"}, format="json"
                )
                self.assertEqual(response.status_code, 404)

    def test_beta_teacher_cannot_use_alpha_slug(self):
        self.login(self.beta_teacher)
        response = self.client.get(self.detail_url(self.exam.pk, slug="alpha"))
        self.assertIn(response.status_code, (403, 404))

    def test_anonymous_is_401_or_403(self):
        for method, url in (
            ("get", self.list_url()),
            ("post", self.list_url()),
            ("get", self.detail_url(self.exam.pk)),
            ("patch", self.detail_url(self.exam.pk)),
        ):
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")
                self.assertIn(response.status_code, (401, 403))

    def test_students_are_403_for_now(self):
        for student in (self.approved_student, self.pending_student):
            self.login(student)
            for method, url in (
                ("get", self.list_url()),
                ("post", self.list_url()),
                ("get", self.detail_url(self.exam.pk)),
                ("patch", self.detail_url(self.exam.pk)),
            ):
                with self.subTest(student=student.email, method=method):
                    response = getattr(self.client, method)(url, {}, format="json")
                    self.assertEqual(response.status_code, 403)