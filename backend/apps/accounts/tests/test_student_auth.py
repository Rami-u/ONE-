from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient, APITestCase

from apps.accounts.tokens import staff_password_token
from apps.workspaces.models import Workspace
from .helpers import create_student, create_teacher, create_workspace

User = get_user_model()


class StudentAuthenticationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.workspace = create_workspace("science", "Science Academy")
        self.teacher = create_teacher(self.workspace)
        self.client = APIClient()
        self.base = "/api/v1/workspaces/science/auth/"
        self.register_url = f"{self.base}register/"
        self.login_url = f"{self.base}login/"
        self.reset_url = f"{self.base}password-reset/"
        self.confirm_url = f"{self.reset_url}confirm/"

    def register(self, **overrides):
        payload = {
            "email": "Student@Example.com",
            "password": "Student-strong-password-123!",
            "full_name": "Student Example",
        }
        payload.update(overrides)
        return self.client.post(self.register_url, payload, format="json")

    def login(self, email, password, slug="science"):
        return self.client.post(
            f"/api/v1/workspaces/{slug}/auth/login/",
            {"email": email, "password": password},
            format="json",
        )

    def test_registration_creates_pending_student_without_session(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["approval_status"], User.ApprovalStatus.PENDING)
        student = User.objects.get(email="student@example.com", workspace=self.workspace)
        self.assertEqual(student.role, User.Role.STUDENT)
        self.assertTrue(student.check_password("Student-strong-password-123!"))
        self.assertNotIn("sessionid", response.cookies)

    def test_registration_ignores_privileged_and_unknown_fields(self):
        response = self.register(
            role="teacher",
            workspace=999999,
            approval_status="approved",
            phone="+100000000",
            login_key="admin:attacker@example.com",
            unexpected="ignored",
        )
        self.assertEqual(response.status_code, 201, response.data)
        student = User.objects.get(email="student@example.com", workspace=self.workspace)
        self.assertEqual(student.role, User.Role.STUDENT)
        self.assertEqual(student.approval_status, User.ApprovalStatus.PENDING)
        self.assertIsNone(student.phone)

    def test_duplicate_email_same_workspace_includes_teacher_email(self):
        create_student(self.workspace)
        response = self.register()
        teacher_response = self.register(email=self.teacher.email)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(teacher_response.status_code, 400)

    def test_login_key_integrity_race_returns_duplicate_email_error(self):
        from unittest.mock import Mock

        precheck = Mock()
        precheck.exists.return_value = False
        race_check = Mock()
        race_check.exists.return_value = True
        with patch.object(User.objects, "filter", side_effect=[precheck, race_check]):
            with patch.object(User.objects, "create_user", side_effect=IntegrityError("unique login_key")):
                response = self.register(email="race@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_same_email_can_register_in_another_workspace(self):
        other = create_workspace("other")
        response = self.client.post(
            "/api/v1/workspaces/other/auth/register/",
            {
                "email": "Student@Example.com",
                "password": "Student-strong-password-123!",
                "full_name": "Other Student",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(User.objects.filter(email="student@example.com", workspace=other).exists())

    def test_registration_rejects_weak_password_and_invalid_fields(self):
        weak = self.register(password="password")
        missing = self.client.post(self.register_url, {"email": "a@example.com"}, format="json")
        wrong_type = self.register(full_name=["not", "a", "string"])
        self.assertEqual(weak.status_code, 400)
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(wrong_type.status_code, 400)

    def test_student_post_bodies_reject_missing_and_wrong_typed_fields(self):
        missing_login = self.client.post(self.login_url, {}, format="json")
        wrong_login = self.client.post(
            self.login_url, {"email": ["bad"], "password": "x"}, format="json"
        )
        missing_reset = self.client.post(self.reset_url, {}, format="json")
        wrong_reset = self.client.post(self.reset_url, {"email": ["bad"]}, format="json")
        missing_confirm = self.client.post(self.confirm_url, {}, format="json")
        wrong_confirm = self.client.post(
            self.confirm_url,
            {"uid": ["bad"], "token": "bad", "new_password": "Reset-strong-password-456!"},
            format="json",
        )
        self.assertTrue(
            all(
                response.status_code == 400
                for response in (
                    missing_login,
                    wrong_login,
                    missing_reset,
                    wrong_reset,
                    missing_confirm,
                    wrong_confirm,
                )
            )
        )

    def test_full_registration_approval_login_me_logout_probe(self):
        registered = self.register(email="flow@example.com")
        self.assertEqual(registered.status_code, 201)
        pending_login = self.login("flow@example.com", "Student-strong-password-123!")
        self.assertEqual(pending_login.status_code, 403)
        student = User.objects.get(email="flow@example.com", workspace=self.workspace)
        teacher_client = APIClient()
        teacher_client.force_authenticate(self.teacher)
        with self.captureOnCommitCallbacks(execute=True):
            approved = teacher_client.post(
                f"/api/v1/workspaces/science/students/{student.pk}/approve/", {}, format="json"
            )
        self.assertEqual(approved.status_code, 200)
        successful_login = self.login("flow@example.com", "Student-strong-password-123!")
        self.assertEqual(successful_login.status_code, 200)
        self.assertEqual(self.client.get(f"{self.base}me/").status_code, 200)
        self.assertEqual(self.client.post(f"{self.base}logout/").status_code, 204)
        self.assertEqual(self.client.get(f"{self.base}me/").status_code, 403)

    def test_login_success_returns_safe_me_payload_and_session(self):
        student = create_student(
            self.workspace,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        response = self.login(student.email, "Student-strong-password-123!")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("sessionid", response.cookies)
        self.assertEqual(response.data["workspace"], {"slug": "science", "name": "Science Academy"})
        self.assertNotIn("login_key", response.data)
        self.assertNotIn("password", response.data)

    def test_wrong_password_unknown_email_and_teacher_credentials_are_identical(self):
        cases = [
            self.login("unknown@example.com", "wrong"),
            self.login("student@example.com", "wrong"),
            self.login(self.teacher.email, "Teacher-strong-password-123!"),
        ]
        self.assertTrue(all(response.status_code == 400 for response in cases))
        self.assertTrue(all(response.data == {"detail": "Invalid login credentials."} for response in cases))

    def test_student_credentials_remain_rejected_by_staff_login(self):
        student = create_student(
            self.workspace,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        response = self.client.post(
            "/api/v1/workspaces/science/staff/auth/login/",
            {"email": student.email, "password": "Student-strong-password-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Invalid login credentials."})

    def test_pending_and_rejected_are_revealed_only_after_correct_password(self):
        pending = create_student(self.workspace, email="pending@example.com")
        rejected = create_student(
            self.workspace,
            email="rejected@example.com",
            approval_status=User.ApprovalStatus.REJECTED,
            rejection_reason="Incomplete application",
        )
        pending_wrong = self.login(pending.email, "incorrect")
        pending_correct = self.login(pending.email, "Student-strong-password-123!")
        rejected_correct = self.login(rejected.email, "Student-strong-password-123!")
        self.assertEqual(pending_wrong.status_code, 400)
        self.assertEqual(pending_correct.status_code, 403)
        self.assertEqual(pending_correct.data["code"], "pending_approval")
        self.assertEqual(rejected_correct.status_code, 403)
        self.assertEqual(rejected_correct.data["code"], "account_rejected")
        self.assertEqual(rejected_correct.data["rejection_reason"], "Incomplete application")

    def test_foreign_workspace_and_inactive_student_use_generic_login_failure(self):
        other = create_workspace("other")
        student = create_student(
            self.workspace,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        foreign = self.login(student.email, "Student-strong-password-123!", slug="other")
        student.is_active = False
        student.save(update_fields=["is_active"])
        inactive = self.login(student.email, "Student-strong-password-123!")
        self.assertEqual(foreign.status_code, 400)
        self.assertEqual(inactive.status_code, 400)
        self.assertEqual(foreign.data, inactive.data)
        self.assertEqual(foreign.data, {"detail": "Invalid login credentials."})

    def test_me_logout_and_teacher_me_use_workspace_membership(self):
        student = create_student(
            self.workspace,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.login(student.email, "Student-strong-password-123!")
        me = self.client.get(f"{self.base}me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["role"], User.Role.STUDENT)
        logout_response = self.client.post(f"{self.base}logout/")
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(self.client.get(f"{self.base}me/").status_code, 403)

        teacher_client = APIClient()
        teacher_login = teacher_client.post(
            "/api/v1/workspaces/science/staff/auth/login/",
            {"email": self.teacher.email, "password": "Teacher-strong-password-123!"},
            format="json",
        )
        self.assertEqual(teacher_login.status_code, 200)
        teacher_me = teacher_client.get(f"{self.base}me/")
        self.assertEqual(teacher_me.status_code, 200)
        self.assertEqual(teacher_me.data["role"], User.Role.TEACHER)
        self.assertEqual(teacher_client.post(f"{self.base}logout/").status_code, 204)
        self.assertEqual(teacher_client.get(f"{self.base}me/").status_code, 403)

    def test_csrf_endpoint_sets_cookie_and_returns_no_content(self):
        response = self.client.get(f"{self.base}csrf/")
        self.assertEqual(response.status_code, 204)
        self.assertIn("csrftoken", response.cookies)

    def test_password_reset_response_is_same_for_student_unknown_and_teacher(self):
        student = create_student(self.workspace)
        with self.captureOnCommitCallbacks(execute=True):
            known = self.client.post(self.reset_url, {"email": student.email}, format="json")
            unknown = self.client.post(self.reset_url, {"email": "unknown@example.com"}, format="json")
            teacher = self.client.post(self.reset_url, {"email": self.teacher.email}, format="json")
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(known.data, teacher.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_email_is_sent_after_commit_with_configured_link(self):
        student = create_student(self.workspace)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.reset_url, {"email": student.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://science.edunova.com/reset-password/?uid=", mail.outbox[0].body)
        self.assertIn("expires within 3 days", mail.outbox[0].body)

    def test_password_reset_confirm_happy_path_is_single_use_and_login_works(self):
        student = create_student(
            self.workspace,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        uid = urlsafe_base64_encode(force_bytes(student.pk))
        payload = {
            "uid": uid,
            "token": staff_password_token.make_token(student),
            "new_password": "Reset-strong-password-456!",
        }
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.post(self.confirm_url, payload, format="json").status_code, 400)
        self.assertEqual(self.login(student.email, payload["new_password"]).status_code, 200)

    def test_reset_confirm_rejects_foreign_teacher_expired_and_weak_links(self):
        other = create_workspace("other")
        other_student = create_student(other, email="foreign@example.com")
        uid_other = urlsafe_base64_encode(force_bytes(other_student.pk))
        teacher_uid = urlsafe_base64_encode(force_bytes(self.teacher.pk))
        good_password = "Reset-strong-password-456!"
        foreign = self.client.post(
            self.confirm_url,
            {"uid": uid_other, "token": staff_password_token.make_token(other_student), "new_password": good_password},
            format="json",
        )
        teacher = self.client.post(
            self.confirm_url,
            {"uid": teacher_uid, "token": staff_password_token.make_token(self.teacher), "new_password": good_password},
            format="json",
        )
        student = create_student(self.workspace, email="reset@example.com")
        uid_student = urlsafe_base64_encode(force_bytes(student.pk))
        token = staff_password_token.make_token(student)
        weak = self.client.post(
            self.confirm_url,
            {"uid": uid_student, "token": token, "new_password": "password"},
            format="json",
        )
        self.assertEqual(foreign.status_code, 400)
        self.assertEqual(teacher.status_code, 400)
        self.assertEqual(weak.status_code, 400)
        self.assertEqual(foreign.data, teacher.data)
        invalid_uid = self.client.post(
            self.confirm_url,
            {"uid": urlsafe_base64_encode(force_bytes(999999)), "token": "bad", "new_password": good_password},
            format="json",
        )
        invalid_token = self.client.post(
            self.confirm_url,
            {"uid": uid_student, "token": "bad", "new_password": good_password},
            format="json",
        )
        self.assertEqual(invalid_uid.status_code, 400)
        self.assertEqual(invalid_token.status_code, 400)
        self.assertEqual(invalid_uid.data, invalid_token.data)
        self.assertEqual(invalid_uid.data, foreign.data)

        cache.clear()
        with override_settings(PASSWORD_RESET_TIMEOUT=1):
            expired_student = create_student(self.workspace, email="expired@example.com")
            expired_uid = urlsafe_base64_encode(force_bytes(expired_student.pk))
            expired_token = staff_password_token.make_token(expired_student)
            with patch.object(
                staff_password_token,
                "_now",
                return_value=datetime.now() + timedelta(seconds=5),
            ):
                expired = self.client.post(
                    self.confirm_url,
                    {"uid": expired_uid, "token": expired_token, "new_password": good_password},
                    format="json",
                )
        self.assertEqual(expired.status_code, 400)

    def test_pending_student_can_reset_but_still_cannot_log_in(self):
        student = create_student(self.workspace)
        uid = urlsafe_base64_encode(force_bytes(student.pk))
        payload = {
            "uid": uid,
            "token": staff_password_token.make_token(student),
            "new_password": "Reset-strong-password-456!",
        }
        self.assertEqual(self.client.post(self.confirm_url, payload, format="json").status_code, 200)
        login_response = self.login(student.email, payload["new_password"])
        self.assertEqual(login_response.status_code, 403)
        self.assertEqual(login_response.data["code"], "pending_approval")

        rejected = create_student(
            self.workspace,
            email="rejected-reset@example.com",
            approval_status=User.ApprovalStatus.REJECTED,
            rejection_reason="Not eligible",
        )
        rejected_payload = {
            "uid": urlsafe_base64_encode(force_bytes(rejected.pk)),
            "token": staff_password_token.make_token(rejected),
            "new_password": "Reset-strong-password-456!",
        }
        self.assertEqual(self.client.post(self.confirm_url, rejected_payload, format="json").status_code, 200)
        rejected.refresh_from_db()
        self.assertEqual(rejected.approval_status, User.ApprovalStatus.REJECTED)
        rejected_login = self.login(rejected.email, rejected_payload["new_password"])
        self.assertEqual(rejected_login.status_code, 403)
        self.assertEqual(rejected_login.data["code"], "account_rejected")

    def test_reset_email_failure_is_logged_and_request_succeeds(self):
        student = create_student(self.workspace)
        with self.assertLogs("apps.accounts.student_views", level="WARNING") as logs:
            with patch(
                "apps.accounts.student_views.send_mail",
                side_effect=OSError(
                    "mail transport unavailable token=secret password=private "
                    "https://unsafe.example/reset?token=secret"
                ),
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(self.reset_url, {"email": student.email}, format="json")
        self.assertEqual(response.status_code, 200)
        joined = " ".join(logs.output)
        self.assertIn(f"user_id={student.pk}", joined)
        self.assertIn("OSError", joined)
        self.assertIn("mail transport unavailable", joined)
        self.assertNotIn("secret", joined)
        self.assertNotIn("private", joined)
        self.assertNotIn("?uid=", joined)
        self.assertNotIn("token=secret", joined.lower())
        self.assertNotIn("password=private", joined.lower())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="127.0.0.1",
        EMAIL_PORT=1,
        EMAIL_USE_TLS=False,
        EMAIL_HOST_USER="broken-user",
        EMAIL_HOST_PASSWORD="broken-password",
    )
    def test_password_reset_with_broken_email_configuration_still_succeeds(self):
        student = create_student(self.workspace)
        with self.assertLogs("apps.accounts.student_views", level="WARNING"):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.reset_url, {"email": student.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"detail": "If the account exists, a reset link has been sent."})

    def test_unknown_and_suspended_workspace_contract_for_student_routes(self):
        routes = [
            ("get", "csrf/", None),
            ("post", "register/", {}),
            ("post", "login/", {}),
            ("post", "logout/", {}),
            ("get", "me/", None),
            ("post", "password-reset/", {}),
            ("post", "password-reset/confirm/", {}),
        ]
        for method, path, data in routes:
            with self.subTest(path=path, workspace="unknown"):
                response = getattr(self.client, method)(
                    f"/api/v1/workspaces/missing/auth/{path}", data, format="json"
                ) if data is not None else getattr(self.client, method)(f"/api/v1/workspaces/missing/auth/{path}")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.data["detail"], "Workspace not found.")

        self.workspace.status = Workspace.Status.SUSPENDED
        self.workspace.save(update_fields=["status"])
        for method, path, data in routes:
            with self.subTest(path=path, workspace="suspended"):
                response = getattr(self.client, method)(
                    f"{self.base}{path}", data, format="json"
                ) if data is not None else getattr(self.client, method)(f"{self.base}{path}")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.data["detail"], "Workspace is unavailable.")

    def test_workspace_a_session_cannot_use_workspace_b_me_and_suspension_blocks_open_session(self):
        other = create_workspace("other")
        student = create_student(
            self.workspace,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.login(student.email, "Student-strong-password-123!")
        foreign_me = self.client.get("/api/v1/workspaces/other/auth/me/")
        self.assertEqual(foreign_me.status_code, 403)
        self.workspace.status = Workspace.Status.SUSPENDED
        self.workspace.save(update_fields=["status"])
        suspended_me = self.client.get(f"{self.base}me/")
        self.assertEqual(suspended_me.status_code, 403)
        self.assertEqual(suspended_me.data["detail"], "Workspace is unavailable.")

    def test_each_student_throttle_returns_429(self):
        cases = [
            ("register/", {"email": "none@example.com", "password": "Student-strong-password-123!", "full_name": "None"}, 10),
            ("login/", {"email": "none@example.com", "password": "wrong"}, 5),
            ("password-reset/", {"email": "none@example.com"}, 3),
            ("password-reset/confirm/", {"uid": "bad", "token": "bad", "new_password": "Reset-strong-password-456!"}, 5),
        ]
        for path, payload, limit in cases:
            with self.subTest(path=path):
                cache.clear()
                response = None
                for _ in range(limit + 1):
                    response = self.client.post(f"{self.base}{path}", payload, format="json")
                self.assertEqual(response.status_code, 429)
