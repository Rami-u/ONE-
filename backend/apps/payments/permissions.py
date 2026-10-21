from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.workspaces.models import Workspace


class CanViewReceiptPermission(BasePermission):
    """
    Allow approved teachers and students belonging to the active workspace to request receipts.
    Ensures workspace isolation, approval status, and active workspace status.
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
