from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from apps.workspaces.models import Workspace
from .helpers import create_student, create_teacher, create_workspace

User = get_user_model()


class StudentReviewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.workspace = create_workspace("science")
        self.teacher = create_teacher(self.workspace)
        self.student = create_student(self.workspace)
        self.client = APIClient()
        self.client.force_authenticate(self.teacher)
        self.base = "/api/v1/workspaces/science/students/"

    def test_teacher_lists_scoped_students_with_safe_fields_and_filters(self):
        approved = create_student(
            self.workspace,
            email="approved@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        other = create_workspace("other")
        create_student(other, email="foreign@example.com")
        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("password", str(response.data))
        self.assertNotIn("login_key", str(response.data))
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            set(response.data["results"][0]),
            {"id", "email", "full_name", "phone", "approval_status", "rejection_reason", "reviewed_at", "date_joined"},
        )
        filtered = self.client.get(self.base, {"status": "approved"})
        self.assertEqual(filtered.data["count"], 1)
        self.assertEqual(filtered.data["results"][0]["id"], approved.pk)
        invalid = self.client.get(self.base, {"status": "pending-ish"})
        self.assertEqual(invalid.status_code, 400)

    def test_student_list_is_paginated_and_ordered_by_date_then_id(self):
        for index in range(20):
            User.objects.create_user(
                email=f"student-{index}@example.com",
                password=None,
                full_name=f"Student {index}",
                workspace=self.workspace,
                role=User.Role.STUDENT,
            )
        first_page = self.client.get(self.base)
        second_page = self.client.get(self.base, {"page": 2})
        self.assertEqual(first_page.data["count"], 21)
        self.assertEqual(len(first_page.data["results"]), 20)
        self.assertEqual(len(second_page.data["results"]), 1)
        first_ids = [row["id"] for row in first_page.data["results"]]
        self.assertEqual(first_ids, sorted(first_ids, reverse=True))

    def test_student_cannot_list_approve_or_reject(self):
        student = create_student(
            self.workspace,
            email="approved@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.client.force_authenticate(student)
        self.assertEqual(self.client.get(self.base).status_code, 403)
        self.assertEqual(
            self.client.post(f"{self.base}{self.student.pk}/approve/", {}, format="json").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(f"{self.base}{self.student.pk}/reject/", {"rejection_reason": "No"}, format="json").status_code,
            403,
        )

    def test_teacher_isolated_from_other_workspace_and_guessed_student_id(self):
        other = create_workspace("other")
        foreign_student = create_student(other, email="foreign@example.com")
        self.assertEqual(self.client.get("/api/v1/workspaces/other/students/").status_code, 403)
        guessed = self.client.post(f"{self.base}{foreign_student.pk}/approve/", {}, format="json")
        self.assertEqual(guessed.status_code, 404)

        session_client = APIClient()
        login = session_client.post(
            "/api/v1/workspaces/science/staff/auth/login/",
            {"email": self.teacher.email, "password": "Teacher-strong-password-123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        foreign_list = session_client.get("/api/v1/workspaces/other/students/")
        self.assertEqual(foreign_list.status_code, 403)

    def test_approve_ignores_body_records_reviewer_and_sends_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"{self.base}{self.student.pk}/approve/",
                {"approval_status": "rejected", "reviewed_by": 999, "role": "admin"},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("password", str(response.data))
        self.assertNotIn("login_key", str(response.data))
        self.student.refresh_from_db()
        self.assertEqual(self.student.approval_status, User.ApprovalStatus.APPROVED)
        self.assertEqual(self.student.reviewed_by_id, self.teacher.pk)
        self.assertIsNotNone(self.student.reviewed_at)
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("approved", mail.outbox[0].subject.lower())

    def test_reject_requires_nonblank_reason_saves_trimmed_reason_and_notifies(self):
        missing = self.client.post(f"{self.base}{self.student.pk}/reject/", {}, format="json")
        blank = self.client.post(
            f"{self.base}{self.student.pk}/reject/", {"rejection_reason": "   "}, format="json"
        )
        too_long = self.client.post(
            f"{self.base}{self.student.pk}/reject/",
            {"rejection_reason": "x" * 1001},
            format="json",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(blank.status_code, 400)
        self.assertEqual(too_long.status_code, 400)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"{self.base}{self.student.pk}/reject/",
                {"rejection_reason": "  Missing information  "},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("password", str(response.data))
        self.assertNotIn("login_key", str(response.data))
        self.student.refresh_from_db()
        self.assertEqual(self.student.approval_status, User.ApprovalStatus.REJECTED)
        self.assertEqual(self.student.rejection_reason, "Missing information")
        self.assertEqual(self.student.reviewed_by_id, self.teacher.pk)
        self.assertIsNotNone(self.student.reviewed_at)
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())
        self.assertIn("Missing information", mail.outbox[0].body)

    def test_only_pending_students_can_be_reviewed(self):
        self.student.approval_status = User.ApprovalStatus.APPROVED
        self.student.save(update_fields=["approval_status"])
        response = self.client.post(f"{self.base}{self.student.pk}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "Only pending students can be reviewed.")

    def test_review_email_failure_logs_exception_but_keeps_success(self):
        with self.assertLogs("apps.accounts.services", level="WARNING") as logs:
            with patch(
                "apps.accounts.services.send_mail",
                side_effect=OSError("SMTP unavailable https://unsafe.example/?token=secret"),
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(
                        f"{self.base}{self.student.pk}/approve/", {}, format="json"
                    )
        self.assertEqual(response.status_code, 200)
        logged = " ".join(logs.output)
        self.assertIn(f"user_id={self.student.pk}", logged)
        self.assertIn("OSError", logged)
        self.assertIn("SMTP unavailable", logged)
        self.assertNotIn("token", logged.lower())
        self.assertNotIn("http", logged.lower())

    def test_csrf_is_required_for_session_teacher_review(self):
        client = APIClient(enforce_csrf_checks=True)
        login = client.post(
            "/api/v1/workspaces/science/staff/auth/login/",
            {"email": self.teacher.email, "password": "Teacher-strong-password-123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        csrf = client.get("/api/v1/workspaces/science/auth/csrf/")
        self.assertEqual(csrf.status_code, 204)
        csrf_token = client.cookies["csrftoken"].value
        without_header = client.post(f"{self.base}{self.student.pk}/approve/", {}, format="json")
        self.assertEqual(without_header.status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            with_header = client.post(
                f"{self.base}{self.student.pk}/approve/",
                {},
                format="json",
                HTTP_X_CSRFTOKEN=csrf_token,
            )
        self.assertEqual(with_header.status_code, 200, with_header.data)

    def test_unknown_and_suspended_workspace_teacher_routes(self):
        missing_routes = [
            ("get", "/api/v1/workspaces/missing/students/", None),
            ("post", f"/api/v1/workspaces/missing/students/{self.student.pk}/approve/", {}),
            ("post", f"/api/v1/workspaces/missing/students/{self.student.pk}/reject/", {"rejection_reason": "reason"}),
        ]
        for method, url, payload in missing_routes:
            response = getattr(self.client, method)(url, payload, format="json") if payload is not None else self.client.get(url)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data["detail"], "Workspace not found.")
        self.workspace.status = Workspace.Status.SUSPENDED
        self.workspace.save(update_fields=["status"])
        suspended_routes = [
            ("get", self.base, None),
            ("post", f"{self.base}{self.student.pk}/approve/", {}),
            ("post", f"{self.base}{self.student.pk}/reject/", {"rejection_reason": "reason"}),
        ]
        for method, url, payload in suspended_routes:
            response = getattr(self.client, method)(url, payload, format="json") if payload is not None else self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.data["detail"], "Workspace is unavailable.")
