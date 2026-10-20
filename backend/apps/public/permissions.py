from rest_framework.permissions import AllowAny, BasePermission

from apps.accounts.models import User


class PublicReadOnly(AllowAny):
    """Explicitly allow unauthenticated requests to showcase endpoints."""


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
            and workspace.status == "active"
            and user.workspace_id == workspace.pk
        )
