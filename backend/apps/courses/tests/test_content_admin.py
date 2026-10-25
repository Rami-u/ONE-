from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.tests.helpers import create_workspace
from apps.courses.tests.helpers import (
    create_course,
    create_lesson,
    create_lesson_asset,
    create_section,
)


class ContentAdminTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            email="content-admin@example.com",
            password="Admin-strong-password-123!",
            full_name="Platform Admin",
        )
        cls.workspace = create_workspace("content-admin")
        cls.course = create_course(cls.workspace)
        cls.section = create_section(cls.workspace, cls.course)
        cls.lesson = create_lesson(cls.workspace, cls.course, section=cls.section)
        cls.asset = create_lesson_asset(cls.workspace, cls.lesson)

    def setUp(self):
        self.client.force_login(self.admin_user)

    def assert_admin_pages_load(self, model_name, instance):
        urls = [
            reverse(f"admin:courses_{model_name}_changelist"),
            reverse(f"admin:courses_{model_name}_add"),
            reverse(f"admin:courses_{model_name}_change", args=[instance.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_section_admin_pages(self):
        self.assert_admin_pages_load("coursesection", self.section)

    def test_lesson_admin_pages(self):
        self.assert_admin_pages_load("lesson", self.lesson)

    def test_asset_admin_pages(self):
        self.assert_admin_pages_load("lessonasset", self.asset)
