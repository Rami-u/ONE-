import io
import os
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assessments.models import (
    Exam,
    ExamAttempt,
    LessonTopic,
    Question,
    QuestionTopic,
    Topic,
)
from apps.courses.models import Course, CourseSection, Lesson
from apps.enrollments.models import CourseEnrollment
from apps.workspaces.models import Workspace

SEED_PASSWORD = "Seed-test-password-123!"


def run_seed(*args, **kwargs):
    out = io.StringIO()
    call_command("seed_demo_data", *args, stdout=out, **kwargs)
    return out.getvalue()


def counts():
    return {
        "workspaces": Workspace.objects.count(),
        "users": User.objects.count(),
        "courses": Course.objects.count(),
        "sections": CourseSection.objects.count(),
        "lessons": Lesson.objects.count(),
        "topics": Topic.objects.count(),
        "lesson_topics": LessonTopic.objects.count(),
        "questions": Question.objects.count(),
        "question_topics": QuestionTopic.objects.count(),
        "exams": Exam.objects.count(),
        "exam_questions": sum(e.exam_questions.count() for e in Exam.objects.all()),
        "enrollments": CourseEnrollment.objects.count(),
    }


@override_settings(DEBUG=True)
class SeedContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_seed(password=SEED_PASSWORD)
        cls.workspace = Workspace.objects.get(slug="demo-chem")

    def test_expected_counts(self):
        c = counts()
        self.assertEqual(c["workspaces"], 1)
        self.assertEqual(c["users"], 6)  # 1 teacher + 5 students
        self.assertEqual(c["courses"], 1)
        self.assertEqual(c["sections"], 2)
        self.assertEqual(c["lessons"], 4)
        self.assertEqual(c["topics"], 6)
        self.assertEqual(c["lesson_topics"], 6)
        self.assertEqual(c["questions"], 24)
        self.assertEqual(c["question_topics"], 24)
        self.assertEqual(c["exams"], 3)
        self.assertEqual(c["enrollments"], 5)

    def test_teacher_and_students(self):
        teacher = User.objects.get(workspace=self.workspace, email="teacher@demo.local")
        self.assertEqual(teacher.role, User.Role.TEACHER)
        students = User.objects.filter(workspace=self.workspace, role=User.Role.STUDENT)
        self.assertEqual(students.count(), 5)
        for student in students:
            self.assertEqual(student.approval_status, User.ApprovalStatus.APPROVED)
            self.assertTrue(student.check_password(SEED_PASSWORD))

    def test_workspace_is_active_and_listed(self):
        self.assertEqual(self.workspace.status, Workspace.Status.ACTIVE)
        self.assertTrue(self.workspace.is_listed)

    def test_course_and_enrollments(self):
        course = Course.objects.get(workspace=self.workspace)
        self.assertEqual(course.title, "Organic Chemistry 101")
        self.assertTrue(course.is_published)
        enrollments = CourseEnrollment.objects.filter(course=course)
        self.assertEqual(enrollments.count(), 5)
        for enrollment in enrollments:
            self.assertEqual(enrollment.status, CourseEnrollment.Status.ACTIVE)
            self.assertIsNotNone(enrollment.activated_at)

    def test_lesson_two_is_benzene(self):
        lessons = list(Lesson.objects.filter(workspace=self.workspace).order_by("position"))
        self.assertEqual(lessons[1].title, "Aromatic compounds: benzene")
        self.assertTrue(all(lesson.is_published for lesson in lessons))

    def test_questions_are_manual_approved_with_explanation(self):
        questions = Question.objects.filter(workspace=self.workspace)
        self.assertEqual(questions.count(), 24)
        for question in questions:
            self.assertEqual(question.source_type, Question.SourceType.MANUAL)
            self.assertEqual(question.status, Question.Status.APPROVED)
            self.assertTrue(question.explanation)
        types = set(questions.values_list("question_type", flat=True))
        self.assertEqual(types, {"mcq", "true_false", "short", "essay"})

    def test_each_topic_has_three_or_more_questions(self):
        for topic in Topic.objects.filter(workspace=self.workspace):
            with self.subTest(topic=topic.slug):
                self.assertGreaterEqual(
                    QuestionTopic.objects.filter(topic=topic).count(), 3
                )

    def test_exams(self):
        exams = {e.title: e for e in Exam.objects.filter(workspace=self.workspace)}
        quiz = exams["Quiz 1: Alkanes and Alkenes"]
        mid = exams["Midterm: Aromatic compounds"]
        draft = exams["Draft exam"]
        self.assertEqual(quiz.status, Exam.Status.PUBLISHED)
        self.assertEqual(quiz.exam_questions.count(), 10)
        self.assertEqual(quiz.duration_minutes, 20)
        self.assertEqual(quiz.max_attempts, 2)
        self.assertFalse(quiz.proctoring_enabled)
        self.assertEqual(mid.status, Exam.Status.PUBLISHED)
        self.assertEqual(mid.exam_questions.count(), 12)
        self.assertEqual(mid.duration_minutes, 30)
        self.assertEqual(mid.max_attempts, 1)
        self.assertTrue(mid.proctoring_enabled)
        self.assertEqual(mid.passing_score, 60)
        self.assertEqual(draft.status, Exam.Status.DRAFT)
        self.assertEqual(draft.exam_questions.count(), 3)
        self.assertIsNone(draft.published_at)
        self.assertIsNotNone(quiz.published_at)


@override_settings(DEBUG=True)
class SeedIdempotencyAndGuardTests(TestCase):
    def test_running_twice_creates_no_duplicates(self):
        run_seed(password=SEED_PASSWORD)
        first = counts()
        run_seed(password=SEED_PASSWORD)
        self.assertEqual(counts(), first)

    def test_second_run_does_not_overwrite_existing_rows(self):
        run_seed(password=SEED_PASSWORD)
        exam = Exam.objects.get(title="Draft exam")
        Exam.objects.filter(pk=exam.pk).update(description="Edited by teacher")
        run_seed(password="Another-password-456!")
        exam.refresh_from_db()
        self.assertEqual(exam.description, "Edited by teacher")
        student = User.objects.get(email="student1@demo.local")
        self.assertTrue(student.check_password(SEED_PASSWORD))

    def test_students_option(self):
        run_seed(password=SEED_PASSWORD, students=2)
        self.assertEqual(User.objects.filter(role=User.Role.STUDENT).count(), 2)
        self.assertEqual(CourseEnrollment.objects.count(), 2)

    def test_custom_workspace_slug(self):
        run_seed(password=SEED_PASSWORD, workspace_slug="chem-two")
        self.assertTrue(Workspace.objects.filter(slug="chem-two").exists())
        self.assertFalse(Workspace.objects.filter(slug="demo-chem").exists())

    def test_password_from_environment(self):
        with mock.patch.dict(os.environ, {"DEMO_USER_PASSWORD": "Env-password-789!"}):
            run_seed()
        student = User.objects.get(email="student1@demo.local")
        self.assertTrue(student.check_password("Env-password-789!"))

    def test_fails_without_password(self):
        env = {k: v for k, v in os.environ.items() if k != "DEMO_USER_PASSWORD"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(CommandError):
                run_seed()
        self.assertEqual(Workspace.objects.count(), 0)

    def test_password_is_never_printed(self):
        output = run_seed(password=SEED_PASSWORD)
        self.assertNotIn(SEED_PASSWORD, output)

    def test_invalid_student_count(self):
        with self.assertRaises(CommandError):
            run_seed(password=SEED_PASSWORD, students=0)


@override_settings(DEBUG=False)
class SeedRefusesWhenNotDebugTests(TestCase):
    def test_refuses_and_changes_nothing(self):
        with self.assertRaises(CommandError):
            run_seed(password=SEED_PASSWORD)
        self.assertEqual(Workspace.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)


@override_settings(DEBUG=True)
class SeededExamsCanBeStartedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_seed(password=SEED_PASSWORD)
        cls.workspace = Workspace.objects.get(slug="demo-chem")

    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.get(email="student1@demo.local")
        self.client.force_login(self.student)

    def start(self, exam, body=None):
        url = reverse(
            "exam-attempt-start", kwargs={"slug": "demo-chem", "exam_id": exam.pk}
        )
        return self.client.post(url, body or {}, format="json")

    def test_student_sees_only_published_exams(self):
        url = reverse("exam-list-create", kwargs={"slug": "demo-chem"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(
            titles, {"Quiz 1: Alkanes and Alkenes", "Midterm: Aromatic compounds"}
        )

    def test_quiz_can_be_started(self):
        exam = Exam.objects.get(title="Quiz 1: Alkanes and Alkenes")
        response = self.start(exam)
        self.assertIn(response.status_code, (200, 201), response.data)
        self.assertTrue(
            ExamAttempt.objects.filter(exam=exam, student=self.student).exists()
        )

    def test_midterm_needs_consent(self):
        exam = Exam.objects.get(title="Midterm: Aromatic compounds")
        self.assertEqual(self.start(exam).status_code, 400)
        response = self.start(exam, {"consent": True})
        self.assertIn(response.status_code, (200, 201), response.data)

    def test_draft_exam_cannot_be_started(self):
        exam = Exam.objects.get(title="Draft exam")
        self.assertIn(self.start(exam).status_code, (400, 404, 409))