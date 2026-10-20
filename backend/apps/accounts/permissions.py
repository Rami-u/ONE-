from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts.models import User
from apps.workspaces.models import Workspace


class IsPlatformAdmin(BasePermission):
    """Allow only authenticated Platform Admin accounts."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsWorkspaceTeacher(BasePermission):
    """Allow the approved teacher to manage their own active workspace."""

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


class IsApprovedStudent(BasePermission):
    """Allow an approved student in the active workspace from the URL."""

    def has_permission(self, request, view):
        user = request.user
        workspace = getattr(view, "workspace", None)
        return bool(
            user
            and user.is_authenticated
            and user.role == User.Role.STUDENT
            and user.approval_status == User.ApprovalStatus.APPROVED
            and workspace is not None
            and workspace.status == Workspace.Status.ACTIVE
            and user.workspace_id == workspace.pk
        )


class IsWorkspaceMember(BasePermission):
    """Allow an approved teacher or student in the active URL workspace."""

    def has_permission(self, request, view):
        user = request.user
        workspace = getattr(view, "workspace", None)
        return bool(
            user
            and user.is_authenticated
            and user.role in {User.Role.TEACHER, User.Role.STUDENT}
            and user.approval_status == User.ApprovalStatus.APPROVED
            and workspace is not None
            and workspace.status == Workspace.Status.ACTIVE
            and user.workspace_id == workspace.pk
        )


class ActiveWorkspaceSlugMixin:
    """Resolve a workspace from the URL and make its active status available."""

    workspace = None
    unavailable_message = "This workspace is suspended."

    def initial(self, request, *args, **kwargs):
        from apps.workspaces.models import Workspace

        try:
            self.workspace = Workspace.objects.get(slug=kwargs["slug"])
        except Workspace.DoesNotExist as exc:
            raise NotFound("Workspace not found.") from exc
        if self.workspace.status != Workspace.Status.ACTIVE:
            raise PermissionDenied(self.unavailable_message)
        super().initial(request, *args, **kwargs)


class WorkspaceSlugMixin(ActiveWorkspaceSlugMixin):
    """Resolve an active workspace using the public-workspace error contract."""

    unavailable_message = "Workspace is unavailable."
