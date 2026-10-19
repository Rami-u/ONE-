from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.workspaces.models import Workspace


class UserModelTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name="First", slug="first")
        self.other_workspace = Workspace.objects.create(name="Second", slug="second")

    def create_student(self, workspace=None, email="student@example.com"):
        return User.objects.create_user(
            email=email,
            password="a-secure-password",
            full_name="Student",
            workspace=workspace or self.workspace,
            role=User.Role.STUDENT,
        )

    def test_login_key_uses_workspace_and_normalized_lowercase_email(self):
        student = self.create_student(email="  Student@Example.COM ")
        self.assertEqual(student.email, "student@example.com")
        self.assertEqual(student.login_key, f"{self.workspace.pk}:student@example.com")
        self.assertEqual(student.approval_status, User.ApprovalStatus.PENDING)

        student.email = "Updated@Example.COM"
        student.save()
        self.assertEqual(student.login_key, f"{self.workspace.pk}:updated@example.com")

    def test_same_email_is_allowed_in_two_workspaces(self):
        first = self.create_student()
        second = self.create_student(workspace=self.other_workspace)
        self.assertNotEqual(first.login_key, second.login_key)

    def test_same_email_is_rejected_twice_in_one_workspace(self):
        self.create_student()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_student(email="STUDENT@example.com")

    def test_only_one_teacher_can_belong_to_a_workspace(self):
        User.objects.create_user(
            email="teacher1@example.com",
            password="a-secure-password",
            full_name="Teacher One",
            workspace=self.workspace,
            role=User.Role.TEACHER,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                email="teacher2@example.com",
                password="a-secure-password",
                full_name="Teacher Two",
                workspace=self.workspace,
                role=User.Role.TEACHER,
            )

    def test_admin_workspace_check_constraint(self):
        self.create_student()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(
                email="bad-admin@example.com",
                login_key="bad",
                full_name="Bad Admin",
                role=User.Role.ADMIN,
                workspace=self.workspace,
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(
                email="bad-student@example.com",
                login_key="bad",
                full_name="Bad Student",
                role=User.Role.STUDENT,
                workspace=None,
            )

    def test_create_superuser_sets_admin_identity_and_flags(self):
        admin = User.objects.create_superuser(
            email="Admin@Example.COM",
            login_key="admin:admin@example.com",
            password="a-secure-password",
            full_name="Platform Admin",
        )
        self.assertEqual(admin.email, "admin@example.com")
        self.assertEqual(admin.login_key, "admin:admin@example.com")
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertIsNone(admin.workspace)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password("a-secure-password"))
