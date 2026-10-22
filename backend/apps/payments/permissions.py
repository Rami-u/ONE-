from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.workspaces.models import Workspace


class IsReceiptTeacherOrOwner(BasePermission):
    """
    Allow approved teachers and students belonging to the active workspace to request receipts.
    Ensures workspace isolation, approval status, and active workspace status.
    Object permission grants access to the workspace teacher or the owning student.
    """

    def has_permission(self, request, view):
        user = request.user
        workspace = getattr(view, "workspace", None)
        if not (
            user
            and user.is_authenticated
            and workspace
            and workspace.status == Workspace.Status.ACTIVE
        ):
            return False
        if user.workspace_id != workspace.pk:
            return False
        if user.approval_status != User.ApprovalStatus.APPROVED:
            return False
        return user.role in {User.Role.TEACHER, User.Role.STUDENT}

    def has_object_permission(self, request, view, obj):
        user = request.user
        workspace = getattr(view, "workspace", None)
        if not workspace or obj.workspace_id != workspace.pk:
            return False
        if user.role == User.Role.TEACHER and user.workspace_id == workspace.pk:
            return True
        return user.role == User.Role.STUDENT and obj.submitted_by_id == user.pk

