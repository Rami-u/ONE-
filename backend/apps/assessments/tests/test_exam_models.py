from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.assessments.models import Answer, Exam, ExamAttempt, ExamQuestion
from apps.assessments.tests.helpers import create_answer, create_exam, create_exam_attempt, create_question
from apps.courses.tests.helpers import create_course, create_lesson


class ExamModelTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.workspace = create_workspace("exam-models")
        cls.other_workspace = create_workspace("other-exam-models")
        cls.course = create_course(cls.workspace)
        cls.other_course = create_course(cls.workspace, title="Another course")
        cls.foreign_course = create_course(cls.other_workspace)
        cls.lesson = create_lesson(cls.workspace, cls.course)
        cls.other_lesson = create_lesson(cls.workspace, cls.other_course)
        # Deliberately invalid row isolates workspace validation from the course check.
        cls.foreign_lesson = create_lesson(cls.other_workspace, cls.course)
        cls.teacher = create_teacher(cls.workspace)
        cls.foreign_teacher = create_teacher(cls.other_workspace)
        cls.student = create_student(cls.workspace)
        cls.foreign_student = create_student(cls.other_workspace)
        cls.exam = create_exam(cls.workspace, cls.course)
        cls.other_exam = create_exam(cls.workspace, cls.course)
        cls.foreign_exam = create_exam(cls.other_workspace, cls.foreign_course)
        cls.question = create_question(cls.workspace)
        cls.foreign_question = create_question(cls.other_workspace)
        cls.attempt = create_exam_attempt(cls.workspace, cls.exam, cls.student)
        cls.foreign_attempt = create_exam_attempt(cls.other_workspace, cls.foreign_exam, cls.foreign_student)

    def test_exam_rejects_cross_workspace_course(self):
        exam = Exam(workspace=self.workspace, course=self.foreign_course, title="Exam")
        with self.assertRaises(ValidationError) as caught:
            exam.clean()
        self.assertEqual(set(caught.exception.message_dict), {"course"})

    def test_exam_rejects_cross_workspace_lesson(self):
        exam = Exam(workspace=self.workspace, course=self.course, lesson=self.foreign_lesson, title="Exam")
        with self.assertRaises(ValidationError) as caught:
            exam.clean()
        self.assertEqual(set(caught.exception.message_dict), {"lesson"})

    def test_exam_rejects_lesson_from_another_course(self):
        exam = Exam(workspace=self.workspace, course=self.course, lesson=self.other_lesson, title="Exam")
        with self.assertRaises(ValidationError) as caught:
            exam.clean()
        self.assertEqual(set(caught.exception.message_dict), {"lesson"})

    def test_exam_accepts_same_workspace_and_course_relations(self):
        exam = create_exam(self.workspace, self.course, lesson=self.lesson)
        exam.full_clean()

    def test_exam_accepts_no_optional_lesson(self):
        self.exam.full_clean()

    def test_exam_defaults_and_choices(self):
        exam = Exam()
        self.assertEqual(exam.status, "draft")
        self.assertEqual(exam.max_attempts, 1)
        self.assertFalse(exam.proctoring_enabled)
        self.assertIsNone(exam.lesson_id)
        self.assertIsNone(exam.description)
        self.assertIsNone(exam.duration_minutes)
        self.assertIsNone(exam.passing_score)
        self.assertIsNone(exam.published_at)
        self.assertEqual(Exam.Status.values, ["draft", "published", "archived"])
        self.assertTrue(Exam._meta.get_field("created_at").auto_now_add)
        self.assertEqual(Exam._meta.ordering, ["-created_at", "id"])
        self.assertEqual(Exam._meta.db_table, "exams")

    def test_exam_rejects_invalid_status(self):
        self.exam.status = "invalid"
        with self.assertRaises(ValidationError) as caught:
            self.exam.full_clean()
        self.assertIn("status", caught.exception.message_dict)

    def test_exam_rejects_zero_max_attempts(self):
        self.exam.max_attempts = 0
        with self.assertRaises(ValidationError) as caught:
            self.exam.full_clean()
        self.assertIn("max_attempts", caught.exception.message_dict)

    def test_exam_rejects_negative_max_attempts(self):
        self.exam.max_attempts = -1
        with self.assertRaises(ValidationError) as caught:
            self.exam.full_clean()
        self.assertIn("max_attempts", caught.exception.message_dict)

    def test_exam_accepts_one_max_attempt(self):
        self.exam.max_attempts = 1
        self.exam.full_clean()

    def test_exam_rejects_zero_duration(self):
        self.exam.duration_minutes = 0
        with self.assertRaises(ValidationError) as caught:
            self.exam.full_clean()
        self.assertIn("duration_minutes", caught.exception.message_dict)

    def test_exam_rejects_negative_duration(self):
        self.exam.duration_minutes = -1
        with self.assertRaises(ValidationError) as caught:
            self.exam.full_clean()
        self.assertIn("duration_minutes", caught.exception.message_dict)

    def test_exam_accepts_one_minute_duration(self):
        self.exam.duration_minutes = 1
        self.exam.full_clean()

    def test_exam_accepts_unlimited_duration(self):
        self.exam.duration_minutes = None
        self.exam.full_clean()

    def test_exam_question_rejects_cross_workspace_exam(self):
        link = ExamQuestion(workspace=self.workspace, exam=self.foreign_exam, question=self.question)
        with self.assertRaises(ValidationError) as caught:
            link.clean()
        self.assertEqual(set(caught.exception.message_dict), {"exam"})

    def test_exam_question_rejects_cross_workspace_question(self):
        link = ExamQuestion(workspace=self.workspace, exam=self.exam, question=self.foreign_question)
        with self.assertRaises(ValidationError) as caught:
            link.clean()
        self.assertEqual(set(caught.exception.message_dict), {"question"})

    def test_exam_question_accepts_same_workspace_relations(self):
        link = ExamQuestion(workspace=self.workspace, exam=self.exam, question=self.question)
        link.full_clean()

    def test_exam_question_pair_is_unique(self):
        self.assertEqual(
            [(constraint.name, constraint.fields) for constraint in ExamQuestion._meta.constraints],
            [("unique_question_per_exam", ("exam", "question"))],
        )
        ExamQuestion.objects.create(workspace=self.workspace, exam=self.exam, question=self.question)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExamQuestion.objects.create(workspace=self.workspace, exam=self.exam, question=self.question)

    def test_exam_question_allows_same_question_in_another_exam(self):
        first = ExamQuestion.objects.create(workspace=self.workspace, exam=self.exam, question=self.question)
        second = ExamQuestion.objects.create(workspace=self.workspace, exam=self.other_exam, question=self.question)
        self.assertNotEqual(first.exam_id, second.exam_id)

    def test_exam_question_defaults(self):
        link = ExamQuestion()
        self.assertEqual(link.position, 1)
        self.assertIsNone(link.points_override)
        self.assertEqual(ExamQuestion._meta.ordering, ["id"])
        self.assertEqual(ExamQuestion._meta.db_table, "exam_questions")

    def test_exam_question_rejects_negative_points_override(self):
        link = ExamQuestion(
            workspace=self.workspace, exam=self.exam, question=self.question, points_override=Decimal("-0.01"),
        )
        with self.assertRaises(ValidationError) as caught:
            link.full_clean()
        self.assertIn("points_override", caught.exception.message_dict)

    def test_exam_question_accepts_zero_points_override(self):
        link = ExamQuestion(
            workspace=self.workspace, exam=self.exam, question=self.question, points_override=Decimal("0.00"),
        )
        link.full_clean()

    def test_exam_attempt_rejects_cross_workspace_exam(self):
        attempt = ExamAttempt(workspace=self.workspace, exam=self.foreign_exam, student=self.student)
        with self.assertRaises(ValidationError) as caught:
            attempt.clean()
        self.assertEqual(set(caught.exception.message_dict), {"exam"})

    def test_exam_attempt_rejects_cross_workspace_student(self):
        attempt = ExamAttempt(workspace=self.workspace, exam=self.exam, student=self.foreign_student)
        with self.assertRaises(ValidationError) as caught:
            attempt.clean()
        self.assertEqual(set(caught.exception.message_dict), {"student"})

    def test_exam_attempt_rejects_cross_workspace_reviewer(self):
        attempt = ExamAttempt(
            workspace=self.workspace, exam=self.exam, student=self.student, reviewed_by=self.foreign_teacher,
        )
        with self.assertRaises(ValidationError) as caught:
            attempt.clean()
        self.assertEqual(set(caught.exception.message_dict), {"reviewed_by"})

    def test_exam_attempt_rejects_non_student(self):
        attempt = ExamAttempt(workspace=self.workspace, exam=self.exam, student=self.teacher)
        with self.assertRaises(ValidationError) as caught:
            attempt.clean()
        self.assertEqual(set(caught.exception.message_dict), {"student"})

    def test_exam_attempt_accepts_same_workspace_student_and_reviewer(self):
        self.attempt.reviewed_by = self.teacher
        self.attempt.full_clean()

    def test_exam_attempt_accepts_no_reviewer(self):
        self.attempt.full_clean()

    def test_exam_attempt_number_is_unique_per_student_and_exam(self):
        self.assertEqual(
            [(constraint.name, constraint.fields) for constraint in ExamAttempt._meta.constraints],
            [("unique_student_attempt_number_per_exam", ("exam", "student", "attempt_number"))],
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_exam_attempt(self.workspace, self.exam, self.student)

    def test_exam_attempt_number_can_repeat_in_another_exam(self):
        other_attempt = create_exam_attempt(self.workspace, self.other_exam, self.student)
        self.assertEqual(other_attempt.attempt_number, self.attempt.attempt_number)

    def test_exam_attempt_number_can_repeat_for_another_student(self):
        second_student = create_student(self.workspace, email="second-student@example.com")
        other_attempt = create_exam_attempt(self.workspace, self.exam, second_student)
        self.assertEqual(other_attempt.attempt_number, self.attempt.attempt_number)

    def test_exam_allows_another_attempt_number_for_same_student(self):
        other_attempt = create_exam_attempt(self.workspace, self.exam, self.student, attempt_number=2)
        self.assertEqual(other_attempt.attempt_number, 2)

    def test_exam_attempt_defaults_and_choices(self):
        before = timezone.now()
        attempt = ExamAttempt()
        after = timezone.now()
        self.assertEqual(attempt.attempt_number, 1)
        self.assertEqual(attempt.status, "in_progress")
        self.assertEqual(attempt.proctoring_review_status, "clean")
        self.assertIsNone(attempt.submitted_at)
        self.assertIsNone(attempt.graded_at)
        self.assertIsNone(attempt.score)
        self.assertIsNone(attempt.max_score)
        self.assertIsNone(attempt.passed)
        self.assertIsNone(attempt.reviewed_by_id)
        self.assertLessEqual(before, attempt.started_at)
        self.assertLessEqual(attempt.started_at, after)
        field = ExamAttempt._meta.get_field("started_at")
        self.assertIs(field.default, timezone.now)
        self.assertTrue(field.editable)
        self.assertFalse(field.auto_now_add)
        self.assertEqual(ExamAttempt.Status.values, ["in_progress", "submitted", "graded"])
        self.assertEqual(ExamAttempt.ReviewStatus.values, ["clean", "flagged", "cleared", "void"])
        self.assertEqual(ExamAttempt._meta.ordering, ["-started_at", "id"])
        self.assertEqual(ExamAttempt._meta.db_table, "exam_attempts")

    def test_exam_attempt_started_at_can_be_set(self):
        chosen_time = timezone.now() - timedelta(days=1)
        attempt = create_exam_attempt(self.workspace, self.exam, self.student, attempt_number=2, started_at=chosen_time)
        attempt.refresh_from_db()
        self.assertEqual(attempt.started_at, chosen_time)

    def test_exam_attempt_rejects_invalid_status(self):
        self.attempt.status = "invalid"
        with self.assertRaises(ValidationError) as caught:
            self.attempt.full_clean()
        self.assertIn("status", caught.exception.message_dict)

    def test_exam_attempt_rejects_invalid_review_status(self):
        self.attempt.proctoring_review_status = "invalid"
        with self.assertRaises(ValidationError) as caught:
            self.attempt.full_clean()
        self.assertIn("proctoring_review_status", caught.exception.message_dict)

    def test_exam_attempt_rejects_negative_score(self):
        self.attempt.score = Decimal("-0.01")
        with self.assertRaises(ValidationError) as caught:
            self.attempt.full_clean()
        self.assertIn("score", caught.exception.message_dict)

    def test_exam_attempt_rejects_negative_max_score(self):
        self.attempt.max_score = Decimal("-0.01")
        with self.assertRaises(ValidationError) as caught:
            self.attempt.full_clean()
        self.assertIn("max_score", caught.exception.message_dict)

    def test_exam_attempt_accepts_zero_scores(self):
        self.attempt.score = Decimal("0.00")
        self.attempt.max_score = Decimal("0.00")
        self.attempt.full_clean()

    def test_answer_rejects_cross_workspace_attempt(self):
        answer = Answer(workspace=self.workspace, attempt=self.foreign_attempt, question=self.question)
        with self.assertRaises(ValidationError) as caught:
            answer.clean()
        self.assertEqual(set(caught.exception.message_dict), {"attempt"})

    def test_answer_rejects_cross_workspace_question(self):
        answer = Answer(workspace=self.workspace, attempt=self.attempt, question=self.foreign_question)
        with self.assertRaises(ValidationError) as caught:
            answer.clean()
        self.assertEqual(set(caught.exception.message_dict), {"question"})

    def test_answer_accepts_same_workspace_relations(self):
        answer = Answer(workspace=self.workspace, attempt=self.attempt, question=self.question)
        answer.full_clean()

    def test_answer_question_is_unique_per_attempt(self):
        self.assertEqual(
            [(constraint.name, constraint.fields) for constraint in Answer._meta.constraints],
            [("unique_question_per_attempt", ("attempt", "question"))],
        )
        create_answer(self.workspace, self.attempt, self.question)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_answer(self.workspace, self.attempt, self.question)

    def test_answer_allows_same_question_in_another_attempt(self):
        other_attempt = create_exam_attempt(self.workspace, self.other_exam, self.student)
        first = create_answer(self.workspace, self.attempt, self.question)
        second = create_answer(self.workspace, other_attempt, self.question)
        self.assertNotEqual(first.attempt_id, second.attempt_id)

    def test_answer_defaults_and_field_types(self):
        before = timezone.now()
        answer = Answer()
        after = timezone.now()
        self.assertIsNone(answer.selected_option)
        self.assertIsNone(answer.text_answer)
        self.assertIsNone(answer.is_correct)
        self.assertIsNone(answer.points_awarded)
        self.assertLessEqual(before, answer.answered_at)
        self.assertLessEqual(answer.answered_at, after)
        field = Answer._meta.get_field("answered_at")
        self.assertIs(field.default, timezone.now)
        self.assertTrue(field.editable)
        self.assertFalse(field.auto_now_add)
        self.assertIsInstance(Answer._meta.get_field("selected_option"), models.JSONField)
        self.assertEqual(Answer._meta.ordering, ["id"])
        self.assertEqual(Answer._meta.db_table, "answers")

    def test_answer_answered_at_can_be_set(self):
        chosen_time = timezone.now() - timedelta(days=1)
        answer = create_answer(self.workspace, self.attempt, self.question, answered_at=chosen_time)
        answer.refresh_from_db()
        self.assertEqual(answer.answered_at, chosen_time)

    def test_answer_rejects_negative_points_awarded(self):
        answer = Answer(
            workspace=self.workspace, attempt=self.attempt, question=self.question, points_awarded=Decimal("-0.01"),
        )
        with self.assertRaises(ValidationError) as caught:
            answer.full_clean()
        self.assertIn("points_awarded", caught.exception.message_dict)

    def test_answer_accepts_zero_points_awarded(self):
        answer = Answer(
            workspace=self.workspace, attempt=self.attempt, question=self.question, points_awarded=Decimal("0.00"),
        )
        answer.full_clean()

    def test_exam_foreign_keys_are_protected_and_named(self):
        for model in (Exam, ExamQuestion, ExamAttempt, Answer):
            for field in model._meta.fields:
                if isinstance(field, models.ForeignKey):
                    with self.subTest(model=model.__name__, field=field.name):
                        self.assertIs(field.remote_field.on_delete, models.PROTECT)
                        expected = "reviewed_exam_attempts" if field.name == "reviewed_by" else model._meta.db_table
                        self.assertEqual(field.remote_field.related_name, expected)
