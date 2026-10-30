from decimal import Decimal

from django.urls import reverse

from apps.assessments.models import Exam, ExamQuestion, Question
from apps.assessments.tests.content_base import ContentApiBase
from apps.assessments.tests.helpers import (
    create_exam,
    create_exam_attempt,
    create_question,
)
from apps.courses.tests.helpers import create_course, create_lesson


class ExamQuestionsBase(ContentApiBase):
    def setUp(self):
        self.login(self.alpha_teacher)
        self.exam = create_exam(self.alpha, self.alpha_course)

    def url(self, exam_id=None, slug="alpha"):
        return reverse(
            "exam-questions",
            kwargs={"slug": slug, "exam_id": exam_id or self.exam.pk},
        )

    def approved(self, **fields):
        fields.setdefault("status", Question.Status.APPROVED)
        return create_question(self.alpha, **fields)

    def put(self, items, exam_id=None):
        return self.client.put(self.url(exam_id), {"questions": items}, format="json")


class ReplaceQuestionsTests(ExamQuestionsBase):
    def test_put_sets_positions_and_overrides(self):
        q1 = self.approved(points="2.00")
        q2 = self.approved(points="3.00")
        response = self.put(
            [{"question_id": q2.pk}, {"question_id": q1.pk, "points_override": "4.50"}]
        )
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data["questions"]
        self.assertEqual([r["question_id"] for r in rows], [q2.pk, q1.pk])
        self.assertEqual([r["position"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["points"], "3.00")
        self.assertEqual(rows[1]["points"], "4.50")
        self.assertEqual(rows[1]["points_override"], "4.50")

    def test_get_returns_ordered_list(self):
        q1 = self.approved()
        q2 = self.approved()
        self.put([{"question_id": q2.pk}, {"question_id": q1.pk}])
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [r["question_id"] for r in response.data["questions"]], [q2.pk, q1.pk]
        )

    def test_response_has_no_answer_data(self):
        q = self.approved(explanation="secret")
        response = self.put([{"question_id": q.pk}])
        row = response.data["questions"][0]
        for key in ("correct_answer", "options", "explanation"):
            self.assertNotIn(key, row)

    def test_replace_reorders_same_questions(self):
        q1 = self.approved()
        q2 = self.approved()
        self.put([{"question_id": q1.pk}, {"question_id": q2.pk}])
        response = self.put([{"question_id": q2.pk}, {"question_id": q1.pk}])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ExamQuestion.objects.filter(exam=self.exam).count(), 2)
        self.assertEqual(
            [r["question_id"] for r in response.data["questions"]], [q2.pk, q1.pk]
        )

    def test_empty_list_clears(self):
        q = self.approved()
        self.put([{"question_id": q.pk}])
        response = self.put([])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["questions"], [])

    def test_totals_reflected_in_exam_detail(self):
        q1 = self.approved(points="2.00")
        q2 = self.approved(points="3.00")
        self.put([{"question_id": q1.pk}, {"question_id": q2.pk, "points_override": "1.50"}])
        detail = self.client.get(
            reverse("exam-detail", kwargs={"slug": "alpha", "exam_id": self.exam.pk})
        )
        self.assertEqual(detail.data["question_count"], 2)
        self.assertEqual(detail.data["total_points"], "3.50")

    def test_question_without_course_is_allowed(self):
        q = self.approved(course=None)
        self.assertEqual(self.put([{"question_id": q.pk}]).status_code, 200)

    def test_question_of_same_course_is_allowed(self):
        q = self.approved(course=self.alpha_course)
        self.assertEqual(self.put([{"question_id": q.pk}]).status_code, 200)


class ReplaceQuestionsValidationTests(ExamQuestionsBase):
    def assert_400_and_unchanged(self, items, keep):
        response = self.put(items)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("questions", response.data)
        self.assertEqual(
            list(
                ExamQuestion.objects.filter(exam=self.exam)
                .order_by("position")
                .values_list("question_id", flat=True)
            ),
            [k.pk for k in keep],
        )

    def test_failed_put_keeps_existing_list(self):
        keep = self.approved()
        self.assertEqual(self.put([{"question_id": keep.pk}]).status_code, 200)
        draft = self.approved(status=Question.Status.DRAFT)
        self.assert_400_and_unchanged([{"question_id": draft.pk}], [keep])

    def test_draft_question_is_400(self):
        q = self.approved(status=Question.Status.DRAFT)
        self.assert_400_and_unchanged([{"question_id": q.pk}], [])

    def test_archived_question_is_400(self):
        q = self.approved(status=Question.Status.ARCHIVED)
        self.assert_400_and_unchanged([{"question_id": q.pk}], [])

    def test_duplicate_is_400(self):
        q = self.approved()
        self.assert_400_and_unchanged([{"question_id": q.pk}, {"question_id": q.pk}], [])

    def test_unknown_id_is_400(self):
        self.assert_400_and_unchanged([{"question_id": 999999}], [])

    def test_other_workspace_question_is_400(self):
        q = create_question(self.beta, status=Question.Status.APPROVED)
        self.assert_400_and_unchanged([{"question_id": q.pk}], [])

    def test_other_course_question_is_400(self):
        other = create_course(self.alpha, title="Other")
        q = self.approved(course=other)
        self.assert_400_and_unchanged([{"question_id": q.pk}], [])

    def test_question_with_lesson_of_other_course_is_400(self):
        other = create_course(self.alpha, title="Other")
        lesson = create_lesson(self.alpha, other)
        q = self.approved(course=None, lesson=lesson)
        self.assert_400_and_unchanged([{"question_id": q.pk}], [])

    def test_non_positive_override_is_400(self):
        q = self.approved()
        for value in ("0", "-1"):
            with self.subTest(value=value):
                response = self.put([{"question_id": q.pk, "points_override": value}])
                self.assertEqual(response.status_code, 400)

    def test_missing_questions_key_is_400(self):
        response = self.client.put(self.url(), {}, format="json")
        self.assertEqual(response.status_code, 400)


class QuestionsFreezeTests(ExamQuestionsBase):
    def test_archived_is_409(self):
        q = self.approved()
        exam = create_exam(self.alpha, self.alpha_course, status=Exam.Status.ARCHIVED)
        self.assertEqual(self.put([{"question_id": q.pk}], exam_id=exam.pk).status_code, 409)
        self.assertEqual(ExamQuestion.objects.filter(exam=exam).count(), 0)

    def test_published_with_attempts_is_409(self):
        q = self.approved()
        exam = create_exam(self.alpha, self.alpha_course, status=Exam.Status.PUBLISHED)
        ExamQuestion.objects.create(workspace=self.alpha, exam=exam, question=q)
        create_exam_attempt(self.alpha, exam, self.approved_student)
        other = self.approved()
        self.assertEqual(self.put([{"question_id": other.pk}], exam_id=exam.pk).status_code, 409)
        self.assertEqual(
            list(ExamQuestion.objects.filter(exam=exam).values_list("question_id", flat=True)),
            [q.pk],
        )

    def test_published_without_attempts_is_allowed(self):
        q = self.approved()
        exam = create_exam(self.alpha, self.alpha_course, status=Exam.Status.PUBLISHED)
        self.assertEqual(self.put([{"question_id": q.pk}], exam_id=exam.pk).status_code, 200)


class QuestionsAccessTests(ExamQuestionsBase):
    def test_other_workspace_exam_is_404(self):
        beta_exam = create_exam(self.beta, self.beta_course)
        self.assertEqual(self.client.get(self.url(beta_exam.pk)).status_code, 404)
        self.assertEqual(self.put([], exam_id=beta_exam.pk).status_code, 404)

    def test_beta_teacher_cannot_use_alpha_slug(self):
        self.login(self.beta_teacher)
        self.assertIn(self.client.get(self.url()).status_code, (403, 404))
        self.assertIn(self.put([]).status_code, (403, 404))

    def test_anonymous_is_401_or_403(self):
        self.client.logout()
        self.assertIn(self.client.get(self.url()).status_code, (401, 403))
        self.assertIn(self.put([]).status_code, (401, 403))

    def test_students_are_403(self):
        for student in (self.approved_student, self.pending_student):
            self.login(student)
            with self.subTest(student=student.email):
                self.assertEqual(self.client.get(self.url()).status_code, 403)
                self.assertEqual(self.put([]).status_code, 403)