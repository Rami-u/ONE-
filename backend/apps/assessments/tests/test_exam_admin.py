from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_workspace
from apps.assessments.models import ExamQuestion
from apps.assessments.tests.helpers import create_answer, create_exam, create_exam_attempt, create_question
from apps.courses.tests.helpers import create_course


class ExamAdminTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            email="exam-admin@example.com", password="Admin-password-123!",
        )
        cls.workspace = create_workspace("exam-admin")
        cls.student = create_student(cls.workspace)
        cls.course = create_course(cls.workspace)
        cls.exam = create_exam(cls.workspace, cls.course)
        cls.question = create_question(cls.workspace)
        cls.exam_question = ExamQuestion.objects.create(workspace=cls.workspace, exam=cls.exam, question=cls.question)
        cls.attempt = create_exam_attempt(cls.workspace, cls.exam, cls.student)
        cls.answer = create_answer(cls.workspace, cls.attempt, cls.question)

    def setUp(self):
        self.client.force_login(self.admin_user)

    def assert_admin_pages(self, model_name, instance):
        for page, args in (("changelist", []), ("add", []), ("change", [instance.pk])):
            with self.subTest(page=page):
                response = self.client.get(reverse(f"admin:assessments_{model_name}_{page}", args=args))
                self.assertEqual(response.status_code, 200)

    def test_exam_admin_pages(self):
        self.assert_admin_pages("exam", self.exam)

    def test_exam_question_admin_pages(self):
        self.assert_admin_pages("examquestion", self.exam_question)

    def test_exam_attempt_admin_pages(self):
        self.assert_admin_pages("examattempt", self.attempt)

    def test_answer_admin_pages(self):
        self.assert_admin_pages("answer", self.answer)
