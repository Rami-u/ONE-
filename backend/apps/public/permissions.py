from rest_framework.permissions import AllowAny, BasePermission

from apps.accounts.models import User
from apps.workspaces.models import Workspace


class PublicAccess(AllowAny):
    """Allow unauthenticated access with any HTTP method; views are read-only by implementing only GET."""


class IsWorkspaceTeacher(BasePermission):
    """Allow the approved teacher to manage settings for their own active workspace."""

    def has_permission(self, request, view):
        user = request.user
        workspace = getattr(view, "workspace", None)
        return bool(
            user
            and user.is_authenticated
            and user.role == User.Role.TEACHER
            and user.approval_status == User.ApprovalStatus.APPROVED
            and workspace is not None
            and workspace.status == Workspace.Status.ACTIVE
            and user.workspace_id == workspace.pk
        )
