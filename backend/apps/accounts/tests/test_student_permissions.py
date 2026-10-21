from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from apps.accounts.permissions import (
    IsApprovedStudent,
    IsWorkspaceMember,
    IsWorkspaceTeacher,
)
from apps.workspaces.models import Workspace


class StubUser:
    is_authenticated = True

    def __init__(self, role, approval_status, workspace_id):
        self.role = role
        self.approval_status = approval_status
        self.workspace_id = workspace_id


class WorkspacePermissionTests(SimpleTestCase):
    permission_users = {
        IsWorkspaceTeacher: ("teacher", "approved"),
        IsApprovedStudent: ("student", "approved"),
        IsWorkspaceMember: ("student", "approved"),
    }

    def check_permission(self, permission_class, user, workspace=None):
        request = SimpleNamespace(user=user)
        view = SimpleNamespace(workspace=workspace or SimpleNamespace(
            pk=10, status=Workspace.Status.ACTIVE
        ))
        return permission_class().has_permission(request, view)

    def test_each_permission_allows_its_valid_workspace_user(self):
        for permission_class, (role, approval_status) in self.permission_users.items():
            with self.subTest(permission=permission_class.__name__):
                user = StubUser(role, approval_status, workspace_id=10)
                self.assertTrue(self.check_permission(permission_class, user))

    def test_each_permission_rejects_suspended_workspace(self):
        workspace = SimpleNamespace(pk=10, status=Workspace.Status.SUSPENDED)
        for permission_class, (role, approval_status) in self.permission_users.items():
            with self.subTest(permission=permission_class.__name__):
                user = StubUser(role, approval_status, workspace_id=10)
                self.assertFalse(self.check_permission(permission_class, user, workspace))

    def test_each_permission_rejects_another_workspace(self):
        for permission_class, (role, approval_status) in self.permission_users.items():
            with self.subTest(permission=permission_class.__name__):
                user = StubUser(role, approval_status, workspace_id=11)
                self.assertFalse(self.check_permission(permission_class, user))

    def test_each_permission_rejects_wrong_role(self):
        for permission_class, (_, approval_status) in self.permission_users.items():
            with self.subTest(permission=permission_class.__name__):
                user = StubUser("assistant", approval_status, workspace_id=10)
                self.assertFalse(self.check_permission(permission_class, user))

    def test_each_permission_rejects_pending_student(self):
        for permission_class in self.permission_users:
            with self.subTest(permission=permission_class.__name__):
                user = StubUser("student", "pending", workspace_id=10)
                self.assertFalse(self.check_permission(permission_class, user))

    def test_each_permission_rejects_anonymous_user(self):
        for permission_class in self.permission_users:
            with self.subTest(permission=permission_class.__name__):
                self.assertFalse(self.check_permission(permission_class, AnonymousUser()))
