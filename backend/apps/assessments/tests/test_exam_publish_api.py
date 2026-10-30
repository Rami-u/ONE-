from django.urls import reverse

from apps.assessments.models import Exam, ExamQuestion, Question
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import create_exam, create_question


class PublishBase(ContentApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def action_url(self, name, exam_id, slug="alpha"):
        return reverse(f"exam-{name}", kwargs={"slug": slug, "exam_id": exam_id})

    def make_exam_with_question(self, **exam_fields):
        exam = create_exam(self.alpha, self.alpha_course, **exam_fields)
        question = create_question(self.alpha, status=Question.Status.APPROVED)
        ExamQuestion.objects.create(workspace=self.alpha, exam=exam, question=question)
        return exam, question


class PublishExamTests(PublishBase):
    def test_publish_success(self):
        exam, _ = self.make_exam_with_question()
        response = self.client.post(self.action_url("publish", exam.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "published")
        self.assertIsNotNone(response.data["published_at"])
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.PUBLISHED)
        self.assertIsNotNone(exam.published_at)

    def test_publish_without_questions_is_400(self):
        exam = create_exam(self.alpha, self.alpha_course)
        response = self.client.post(self.action_url("publish", exam.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("questions", response.data)
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertIsNone(exam.published_at)

    def test_publish_with_no_longer_approved_question_is_400(self):
        exam, question = self.make_exam_with_question()
        Question.objects.filter(pk=question.pk).update(status=Question.Status.ARCHIVED)
        response = self.client.post(self.action_url("publish", exam.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("questions", response.data)
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.DRAFT)

    def test_publish_with_invalid_passing_score_is_400(self):
        exam, _ = self.make_exam_with_question(passing_score="150.00")
        response = self.client.post(self.action_url("publish", exam.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("passing_score", response.data)

    def test_publish_with_valid_passing_score(self):
        exam, _ = self.make_exam_with_question(passing_score="60.00")
        response = self.client.post(self.action_url("publish", exam.pk))
        self.assertEqual(response.status_code, 200, response.data)

    def test_publish_already_published_is_409(self):
        exam, _ = self.make_exam_with_question(status=Exam.Status.PUBLISHED)
        response = self.client.post(self.action_url("publish", exam.pk))
        self.assertEqual(response.status_code, 409)

    def test_publish_archived_is_409(self):
        exam, _ = self.make_exam_with_question(status=Exam.Status.ARCHIVED)
        response = self.client.post(self.action_url("publish", exam.pk))
        self.assertEqual(response.status_code, 409)
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.ARCHIVED)


class ArchiveExamTests(PublishBase):
    def test_archive_draft(self):
        exam = create_exam(self.alpha, self.alpha_course)
        response = self.client.post(self.action_url("archive", exam.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "archived")

    def test_archive_published(self):
        exam, _ = self.make_exam_with_question(status=Exam.Status.PUBLISHED)
        response = self.client.post(self.action_url("archive", exam.pk))
        self.assertEqual(response.status_code, 200, response.data)
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.ARCHIVED)

    def test_archive_archived_is_409(self):
        exam = create_exam(self.alpha, self.alpha_course, status=Exam.Status.ARCHIVED)
        response = self.client.post(self.action_url("archive", exam.pk))
        self.assertEqual(response.status_code, 409)

    def test_archived_exam_rejects_edits(self):
        exam, question = self.make_exam_with_question()
        self.client.post(self.action_url("archive", exam.pk))
        patch = self.client.patch(
            reverse("exam-detail", kwargs={"slug": "alpha", "exam_id": exam.pk}),
            {"title": "x"},
            format="json",
        )
        self.assertEqual(patch.status_code, 409)
        put = self.client.put(
            reverse("exam-questions", kwargs={"slug": "alpha", "exam_id": exam.pk}),
            {"questions": [{"question_id": question.pk}]},
            format="json",
        )
        self.assertEqual(put.status_code, 409)


class PublishIsolationAndAccessTests(PublishBase):
    def test_other_workspace_exam_is_404(self):
        beta_exam = create_exam(self.beta, self.beta_course)
        for name in ("publish", "archive"):
            with self.subTest(action=name):
                response = self.client.post(self.action_url(name, beta_exam.pk))
                self.assertEqual(response.status_code, 404)
        beta_exam.refresh_from_db()
        self.assertEqual(beta_exam.status, Exam.Status.DRAFT)

    def test_beta_teacher_cannot_use_alpha_slug(self):
        exam, _ = self.make_exam_with_question()
        self.login(self.beta_teacher)
        for name in ("publish", "archive"):
            with self.subTest(action=name):
                response = self.client.post(self.action_url(name, exam.pk))
                self.assertIn(response.status_code, (403, 404))
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.DRAFT)

    def test_anonymous_is_401_or_403(self):
        exam, _ = self.make_exam_with_question()
        self.client.logout()
        for name in ("publish", "archive"):
            with self.subTest(action=name):
                response = self.client.post(self.action_url(name, exam.pk))
                self.assertIn(response.status_code, (401, 403))

    def test_students_are_403(self):
        exam, _ = self.make_exam_with_question()
        for student in (self.approved_student, self.pending_student):
            self.login(student)
            for name in ("publish", "archive"):
                with self.subTest(student=student.email, action=name):
                    response = self.client.post(self.action_url(name, exam.pk))
                    self.assertEqual(response.status_code, 403)
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.DRAFT)