from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.workspaces.models import Workspace


class IsWorkspaceTeacherOrApprovedStudent(BasePermission):
    """Allow an approved teacher or approved student in the active URL workspace."""

    def has_permission(self, request, view):
        user = request.user
        workspace = getattr(view, "workspace", None)
        if not (user and user.is_authenticated and workspace and workspace.status == Workspace.Status.ACTIVE):
            return False
        if user.workspace_id != workspace.pk:
            return False
        if user.approval_status != User.ApprovalStatus.APPROVED:
            return False
        return user.role in {User.Role.TEACHER, User.Role.STUDENT}
