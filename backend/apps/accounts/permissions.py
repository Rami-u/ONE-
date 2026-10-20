from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotFound, PermissionDenied


class IsPlatformAdmin(BasePermission):
    """Allow only authenticated Platform Admin accounts."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
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
