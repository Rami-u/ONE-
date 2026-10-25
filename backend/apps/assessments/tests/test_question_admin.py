from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_workspace
from apps.assessments.models import LessonTopic, QuestionTopic
from apps.assessments.tests.helpers import create_question, create_topic
from apps.courses.tests.helpers import create_course, create_lesson


class QuestionBankAdminTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            email="question-admin@example.com", password="Admin-password-123!",
        )
        cls.workspace = create_workspace("question-admin")
        cls.course = create_course(cls.workspace)
        cls.lesson = create_lesson(cls.workspace, cls.course)
        cls.topic = create_topic(cls.workspace)
        cls.question = create_question(cls.workspace)
        cls.lesson_topic = LessonTopic.objects.create(
            workspace=cls.workspace, lesson=cls.lesson, topic=cls.topic,
        )
        cls.question_topic = QuestionTopic.objects.create(
            workspace=cls.workspace, question=cls.question, topic=cls.topic,
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def assert_admin_pages(self, model_name, instance):
        for page, args in (("changelist", []), ("add", []), ("change", [instance.pk])):
            with self.subTest(page=page):
                response = self.client.get(reverse(f"admin:assessments_{model_name}_{page}", args=args))
                self.assertEqual(response.status_code, 200)

    def test_topic_admin_pages(self):
        self.assert_admin_pages("topic", self.topic)

    def test_lesson_topic_admin_pages(self):
        self.assert_admin_pages("lessontopic", self.lesson_topic)

    def test_question_admin_pages(self):
        self.assert_admin_pages("question", self.question)

    def test_question_topic_admin_pages(self):
        self.assert_admin_pages("questiontopic", self.question_topic)
