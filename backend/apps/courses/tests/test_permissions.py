from types import SimpleNamespace
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.courses.permissions import IsWorkspaceTeacherOrApprovedStudent
from apps.workspaces.models import Workspace


class IsWorkspaceTeacherOrApprovedStudentTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsWorkspaceTeacherOrApprovedStudent()
        self.workspace = create_workspace("school-perm-course")
        self.teacher = create_teacher(self.workspace)
        self.student = create_student(
            self.workspace,
            email="perm-student@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.other_workspace = create_workspace("other-perm-course")

    def _build_request_and_view(self, user, workspace):
        request = self.factory.get("/fake-path/")
        request.user = user
        view = SimpleNamespace(workspace=workspace)
        return request, view

    def test_anonymous_user_denied(self):
        request, view = self._build_request_and_view(AnonymousUser(), self.workspace)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_suspended_workspace_denied(self):
        self.workspace.status = Workspace.Status.SUSPENDED
        self.workspace.save()
        request, view = self._build_request_and_view(self.student, self.workspace)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_pending_student_denied(self):
        pending = create_student(
            self.workspace,
            email="pending-student@example.com",
            approval_status=User.ApprovalStatus.PENDING,
        )
        request, view = self._build_request_and_view(pending, self.workspace)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_rejected_student_denied(self):
        rejected = create_student(
            self.workspace,
            email="rejected-student@example.com",
            approval_status=User.ApprovalStatus.REJECTED,
        )
        request, view = self._build_request_and_view(rejected, self.workspace)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_student_of_another_workspace_denied(self):
        other_student = create_student(
            self.other_workspace,
            email="other-student@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        request, view = self._build_request_and_view(other_student, self.workspace)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_admin_user_without_workspace_denied(self):
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123",
        )
        request, view = self._build_request_and_view(admin_user, self.workspace)
        self.assertFalse(self.permission.has_permission(request, view))

    def test_approved_student_allowed(self):
        request, view = self._build_request_and_view(self.student, self.workspace)
        self.assertTrue(self.permission.has_permission(request, view))

    def test_teacher_allowed(self):
        request, view = self._build_request_and_view(self.teacher, self.workspace)
        self.assertTrue(self.permission.has_permission(request, view))
