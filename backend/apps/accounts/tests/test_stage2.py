from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.accounts.services import create_teacher_with_workspace
from apps.accounts.tokens import staff_password_token
from apps.workspaces.models import Workspace

User = get_user_model()


def admin_user():
    return User.objects.create_superuser(
        email="platform@example.com", password="admin-password", full_name="Admin"
    )


class TeacherOnboardingTests(TestCase):
    def setUp(self):
        self.admin = admin_user()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def create_payload(self, slug="science"):
        return {
            "full_name": "Dr Science",
            "email": "Teacher@Example.com",
            "workspace_name": "Science Academy",
            "slug": slug,
        }

    def test_create_teacher_endpoint_creates_teacher_workspace_and_invitation(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/admin/teachers/", self.create_payload(), format="json"
            )
        self.assertEqual(response.status_code, 201, response.data)
        teacher = User.objects.get(pk=response.data["teacher_id"])
        self.assertEqual(teacher.workspace.slug, "science")
        self.assertEqual(teacher.role, User.Role.TEACHER)
        self.assertEqual(teacher.approval_status, User.ApprovalStatus.APPROVED)
        self.assertFalse(teacher.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "https://science.edunova.com/teacher/set-password/", mail.outbox[0].body
        )

    def test_creation_is_atomic_when_teacher_creation_fails(self):
        with patch.object(User.objects, "create_user", side_effect=RuntimeError("fail")):
            with self.assertRaises(RuntimeError):
                create_teacher_with_workspace(
                    full_name="Teacher",
                    email="teacher@example.com",
                    workspace_name="Science",
                    slug="science",
                )
        self.assertFalse(Workspace.objects.filter(slug="science").exists())

    def test_workspace_creation_failure_does_not_create_teacher(self):
        with patch(
            "apps.accounts.services.Workspace.objects.create",
            side_effect=RuntimeError("fail"),
        ):
            with self.assertRaises(RuntimeError):
                create_teacher_with_workspace(
                    full_name="Teacher",
                    email="teacher@example.com",
                    workspace_name="Science",
                    slug="science",
                )
        self.assertFalse(User.objects.filter(email="teacher@example.com").exists())

    def test_no_email_is_sent_before_transaction_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            create_teacher_with_workspace(
                full_name="Teacher",
                email="teacher@example.com",
                workspace_name="Science",
                slug="science",
            )
            self.assertEqual(mail.outbox, [])
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertEqual(len(mail.outbox), 1)

    def test_failed_invitation_email_keeps_created_account(self):
        with patch("apps.accounts.services.send_staff_password_email", side_effect=OSError):
            with self.captureOnCommitCallbacks(execute=True):
                teacher, workspace, delivery = create_teacher_with_workspace(
                    full_name="Teacher",
                    email="teacher@example.com",
                    workspace_name="Science",
                    slug="science",
                )
        self.assertTrue(User.objects.filter(pk=teacher.pk, workspace=workspace).exists())
        self.assertFalse(delivery["sent"])

    def test_non_admin_cannot_create_teacher(self):
        workspace = Workspace.objects.create(name="Other", slug="other")
        teacher = User.objects.create_user(
            email="teacher@example.com",
            password="teacher-password",
            full_name="Teacher",
            workspace=workspace,
            role=User.Role.TEACHER,
        )
        self.client.force_authenticate(teacher)
        response = self.client.post(
            "/api/v1/admin/teachers/", self.create_payload(), format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Workspace.objects.filter(slug="science").exists())

    def test_admin_can_resend_invitation(self):
        teacher, workspace, _ = create_teacher_with_workspace(
            full_name="Teacher",
            email="teacher@example.com",
            workspace_name="Science",
            slug="science",
        )
        response = self.client.post(
            f"/api/v1/admin/teachers/{teacher.pk}/resend-invite/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("set or reset", mail.outbox[0].body)

    def test_admin_can_list_and_change_workspace_status(self):
        workspace = Workspace.objects.create(name="Science", slug="science")
        self.assertEqual(self.client.get("/api/v1/admin/teachers/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/admin/workspaces/").status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/v1/admin/workspaces/{workspace.pk}/").status_code,
            200,
        )
        suspended = self.client.post(
            f"/api/v1/admin/workspaces/{workspace.pk}/suspend/"
        )
        self.assertEqual(suspended.status_code, 200)
        self.assertEqual(suspended.data["status"], Workspace.Status.SUSPENDED)
        activated = self.client.post(
            f"/api/v1/admin/workspaces/{workspace.pk}/activate/"
        )
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.data["status"], Workspace.Status.ACTIVE)


class StaffAuthenticationTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name="Science", slug="science")
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="teacher-password",
            full_name="Teacher",
            workspace=self.workspace,
            role=User.Role.TEACHER,
        )
        self.client = APIClient()
        self.login_url = "/api/v1/workspaces/science/staff/auth/login/"

    def test_staff_login_rejects_student_with_same_generic_failure_as_bad_password(self):
        student = User.objects.create_user(
            email="student@example.com", password="student-password",
            full_name="Student", workspace=self.workspace, role=User.Role.STUDENT,
        )
        student_response = self.client.post(
            self.login_url,
            {"login_key": student.login_key, "password": "student-password"},
            format="json",
        )
        wrong_password_response = self.client.post(
            self.login_url,
            {"login_key": self.teacher.login_key, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(student_response.status_code, 400)
        self.assertEqual(student_response.data, wrong_password_response.data)

    def test_staff_login_throttles_repeated_attempts(self):
        cache.clear()
        from apps.accounts.views import StaffLoginThrottle

        with patch.object(StaffLoginThrottle, "rate", "1/minute", create=True):
            self.client.post(self.login_url, {"login_key": "x", "password": "x"}, format="json")
            response = self.client.post(
                self.login_url, {"login_key": "x", "password": "x"}, format="json"
            )
        self.assertEqual(response.status_code, 429)

    def test_staff_password_reset_is_throttled(self):
        cache.clear()
        from apps.accounts.views import StaffPasswordResetThrottle

        url = "/api/v1/workspaces/science/staff/auth/password-reset/"
        with patch.object(StaffPasswordResetThrottle, "rate", "1/minute", create=True):
            first = self.client.post(url, {"email": self.teacher.email}, format="json")
            second = self.client.post(url, {"email": self.teacher.email}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    def test_set_password_accepts_invitation_and_token_cannot_be_reused(self):
        self.teacher.set_unusable_password()
        self.teacher.save(update_fields=["password"])
        uid = urlsafe_base64_encode(force_bytes(self.teacher.pk))
        token = staff_password_token.make_token(self.teacher)
        payload = {"uid": uid, "token": token, "new_password": "New-secure-password-123!"}
        url = "/api/v1/workspaces/science/staff/auth/set-password/"
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password(payload["new_password"]))
        reuse_response = self.client.post(url, payload, format="json")
        self.assertEqual(reuse_response.status_code, 400)

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_set_password_rejects_expired_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.teacher.pk))
        token = staff_password_token.make_token(self.teacher)
        with patch.object(
            staff_password_token,
            "_now",
            return_value=datetime.now() + timedelta(seconds=5),
        ):
            response = self.client.post(
                "/api/v1/workspaces/science/staff/auth/set-password/",
                {"uid": uid, "token": token, "new_password": "New-secure-password-123!"},
                format="json",
            )
        self.assertEqual(response.status_code, 400)

    def test_suspended_workspace_rejects_staff_auth_routes(self):
        self.workspace.status = Workspace.Status.SUSPENDED
        self.workspace.save(update_fields=["status"])
        login_response = self.client.post(
            self.login_url,
            {"login_key": self.teacher.login_key, "password": "teacher-password"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 403)
        self.assertEqual(login_response.data["detail"], "This workspace is suspended.")
        reset_response = self.client.post(
            "/api/v1/workspaces/science/staff/auth/password-reset/",
            {"email": self.teacher.email},
            format="json",
        )
        self.assertEqual(reset_response.status_code, 403)
        uid = urlsafe_base64_encode(force_bytes(self.teacher.pk))
        token = staff_password_token.make_token(self.teacher)
        set_password_response = self.client.post(
            "/api/v1/workspaces/science/staff/auth/set-password/",
            {"uid": uid, "token": token, "new_password": "New-secure-password-123!"},
            format="json",
        )
        self.assertEqual(set_password_response.status_code, 403)
