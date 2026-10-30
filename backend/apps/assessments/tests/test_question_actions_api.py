from django.urls import reverse

from apps.assessments.models import ExamQuestion, Question
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import (
    create_exam,
    create_exam_attempt,
    create_question,
)
from apps.courses.tests.helpers import create_course, create_lesson


class ActionApiBase(ContentApiBase):
    def detail_url(self, question_id, slug="alpha"):
        return reverse("question-detail", kwargs={"slug": slug, "question_id": question_id})

    def action_url(self, name, question_id, slug="alpha"):
        return reverse(f"question-{name}", kwargs={"slug": slug, "question_id": question_id})

    def list_url(self, slug="alpha"):
        return reverse("question-list-create", kwargs={"slug": slug})

    def make_question(self, **fields):
        fields.setdefault("status", Question.Status.DRAFT)
        return create_question(self.alpha, **fields)

    def freeze(self, question):
        """Put the question in an exam that has an attempt."""
        exam = create_exam(self.alpha, self.alpha_course)
        ExamQuestion.objects.create(workspace=self.alpha, exam=exam, question=question)
        create_exam_attempt(self.alpha, exam, self.approved_student)
        return exam


class QuestionStatusActionTests(ActionApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_approve_draft_sets_reviewer_from_server(self):
        question = self.make_question()
        response = self.client.post(self.action_url("approve", question.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "approved")
        question.refresh_from_db()
        self.assertEqual(question.reviewed_by, self.alpha_teacher)
        self.assertIsNotNone(question.reviewed_at)

    def test_approve_ignores_reviewer_in_body(self):
        question = self.make_question()
        response = self.client.post(
            self.action_url("approve", question.pk),
            {"reviewed_by": self.beta_teacher.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        question.refresh_from_db()
        self.assertEqual(question.reviewed_by, self.alpha_teacher)

    def test_approve_non_draft_is_409(self):
        question = self.make_question(status=Question.Status.APPROVED)
        response = self.client.post(self.action_url("approve", question.pk))
        self.assertEqual(response.status_code, 409)

    def test_reject_draft(self):
        question = self.make_question()
        response = self.client.post(self.action_url("reject", question.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "rejected")
        question.refresh_from_db()
        self.assertEqual(question.reviewed_by, self.alpha_teacher)
        self.assertIsNotNone(question.reviewed_at)

    def test_reject_approved_is_409(self):
        question = self.make_question(status=Question.Status.APPROVED)
        response = self.client.post(self.action_url("reject", question.pk))
        self.assertEqual(response.status_code, 409)

    def test_archive_from_each_allowed_status(self):
        for status in (
            Question.Status.DRAFT,
            Question.Status.APPROVED,
            Question.Status.REJECTED,
        ):
            with self.subTest(status=status):
                question = self.make_question(status=status)
                response = self.client.post(self.action_url("archive", question.pk))
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["status"], "archived")
                question.refresh_from_db()
                self.assertIsNone(question.reviewed_by)

    def test_archive_already_archived_is_409(self):
        question = self.make_question(status=Question.Status.ARCHIVED)
        response = self.client.post(self.action_url("archive", question.pk))
        self.assertEqual(response.status_code, 409)

    def test_approve_essay_with_empty_answer(self):
        question = self.make_question(question_type="essay", correct_answer="")
        response = self.client.post(self.action_url("approve", question.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "approved")


class QuestionPatchRuleTests(ActionApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)

    def test_patch_archived_is_409(self):
        question = self.make_question(status=Question.Status.ARCHIVED)
        response = self.client.patch(
            self.detail_url(question.pk), {"difficulty": "hard"}, format="json"
        )
        self.assertEqual(response.status_code, 409)

    def test_patch_question_type_is_400(self):
        question = self.make_question()
        response = self.client.patch(
            self.detail_url(question.pk), {"question_type": "essay"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("question_type", response.data)

    def test_patch_status_is_400(self):
        question = self.make_question()
        response = self.client.patch(
            self.detail_url(question.pk), {"status": "approved"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data)

    def test_patch_stem_frozen_when_exam_has_attempts(self):
        question = self.make_question(status=Question.Status.APPROVED)
        self.freeze(question)
        response = self.client.patch(
            self.detail_url(question.pk), {"stem": "New stem"}, format="json"
        )
        self.assertEqual(response.status_code, 409)

    def test_patch_points_frozen_when_exam_has_attempts(self):
        question = self.make_question(status=Question.Status.APPROVED)
        self.freeze(question)
        response = self.client.patch(
            self.detail_url(question.pk), {"points": "5.00"}, format="json"
        )
        self.assertEqual(response.status_code, 409)

    def test_patch_difficulty_allowed_when_exam_has_attempts(self):
        question = self.make_question(status=Question.Status.APPROVED)
        self.freeze(question)
        response = self.client.patch(
            self.detail_url(question.pk), {"difficulty": "hard"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["difficulty"], "hard")

    def test_patch_stem_allowed_when_exam_has_no_attempts(self):
        question = self.make_question(status=Question.Status.APPROVED)
        exam = create_exam(self.alpha, self.alpha_course)
        ExamQuestion.objects.create(workspace=self.alpha, exam=exam, question=question)
        response = self.client.patch(
            self.detail_url(question.pk), {"stem": "New stem"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["stem"], "New stem")

    def test_lesson_from_other_workspace_is_400(self):
        beta_lesson = create_lesson(self.beta, self.beta_course)
        response = self.client.post(
            self.list_url(),
            {
                "question_type": "true_false",
                "stem": "Q",
                "correct_answer": True,
                "points": "1",
                "lesson": beta_lesson.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("lesson", response.data)

    def test_lesson_without_course_sets_course_from_lesson(self):
        lesson = create_lesson(self.alpha, self.alpha_course)
        response = self.client.post(
            self.list_url(),
            {
                "question_type": "true_false",
                "stem": "Q",
                "correct_answer": True,
                "points": "1",
                "lesson": lesson.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["course"], self.alpha_course.pk)

    def test_lesson_from_different_course_is_400(self):
        other_course = create_course(self.alpha, title="Other course")
        lesson = create_lesson(self.alpha, other_course)
        response = self.client.post(
            self.list_url(),
            {
                "question_type": "true_false",
                "stem": "Q",
                "correct_answer": True,
                "points": "1",
                "course": self.alpha_course.pk,
                "lesson": lesson.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("lesson", response.data)


class QuestionWorkspaceIsolationTests(ActionApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)
        self.beta_question = create_question(
            self.beta, status=Question.Status.DRAFT, stem="Beta question"
        )

    def test_detail_other_workspace_id_is_404(self):
        response = self.client.get(self.detail_url(self.beta_question.pk))
        self.assertEqual(response.status_code, 404)

    def test_patch_other_workspace_id_is_404(self):
        response = self.client.patch(
            self.detail_url(self.beta_question.pk), {"difficulty": "hard"}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_actions_other_workspace_id_is_404(self):
        for name in ("approve", "reject", "archive"):
            with self.subTest(action=name):
                response = self.client.post(self.action_url(name, self.beta_question.pk))
                self.assertEqual(response.status_code, 404)
        self.beta_question.refresh_from_db()
        self.assertEqual(self.beta_question.status, Question.Status.DRAFT)

    def test_list_excludes_other_workspace(self):
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.beta_question.pk, ids)

    def test_beta_teacher_cannot_use_alpha_slug(self):
        self.login(self.beta_teacher)
        question = self.make_question()
        response = self.client.post(self.action_url("approve", question.pk, slug="alpha"))
        self.assertIn(response.status_code, (403, 404))
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DRAFT)


class QuestionAccessTests(ActionApiBase):
    def setUp(self):
        self.question = self.make_question()

    def all_requests(self):
        return [
            ("get", self.detail_url(self.question.pk)),
            ("patch", self.detail_url(self.question.pk)),
            ("post", self.action_url("approve", self.question.pk)),
            ("post", self.action_url("reject", self.question.pk)),
            ("post", self.action_url("archive", self.question.pk)),
        ]

    def test_anonymous_is_401_or_403(self):
        for method, url in self.all_requests():
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")
                self.assertIn(response.status_code, (401, 403))

    def test_approved_student_is_403(self):
        self.login(self.approved_student)
        for method, url in self.all_requests():
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")
                self.assertEqual(response.status_code, 403)

    def test_pending_student_is_403(self):
        self.login(self.pending_student)
        for method, url in self.all_requests():
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {}, format="json")
                self.assertEqual(response.status_code, 403)

    def test_failed_access_did_not_change_question(self):
        self.login(self.approved_student)
        self.client.post(self.action_url("approve", self.question.pk))
        self.question.refresh_from_db()
        self.assertEqual(self.question.status, Question.Status.DRAFT)
        self.assertIsNone(self.question.reviewed_by)
