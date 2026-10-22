from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.courses.models import Course
from apps.workspaces.models import Workspace
from .models import CourseEnrollment


class HasActiveEnrollment(BasePermission):
    """
    Permission requiring an active enrollment for students accessing course content.
    Teachers of the workspace are granted access to manage content.

    Later content views must expose course_id in the URL or set view.course before permissions run.
    """

    def _resolve_course_id(self, view, obj=None):
        if obj is not None:
            if isinstance(obj, Course):
                return obj.id
            if hasattr(obj, "course_id"):
                return obj.course_id
            if hasattr(obj, "course") and obj.course:
                return obj.course.id

        view_kwargs = getattr(view, "kwargs", {}) or {}
        val = view_kwargs.get("course_id")
        if val is not None:
            return val

        course = getattr(view, "course", None)
        if course is not None:
            return getattr(course, "id", None)
        return getattr(view, "course_id", None)

    def has_permission(self, request, view):
        user = request.user
        workspace = getattr(view, "workspace", None)
        if not (user and user.is_authenticated and workspace and workspace.status == Workspace.Status.ACTIVE):
            return False
        if user.workspace_id != workspace.pk:
            return False
        if user.approval_status != User.ApprovalStatus.APPROVED:
            return False

        if user.role == User.Role.TEACHER:
            return True

        if user.role != User.Role.STUDENT:
            return False

        course_id = self._resolve_course_id(view)
        if course_id is None:
            return False

        return CourseEnrollment.objects.filter(
            workspace=workspace,
            student=user,
            course_id=course_id,
            status=CourseEnrollment.Status.ACTIVE,
        ).exists()

    def has_object_permission(self, request, view, obj):
        user = request.user
        workspace = getattr(view, "workspace", None)
        if not (user and user.is_authenticated and workspace and workspace.status == Workspace.Status.ACTIVE):
            return False
        if user.workspace_id != workspace.pk:
            return False
        if user.approval_status != User.ApprovalStatus.APPROVED:
            return False

        if user.role == User.Role.TEACHER:
            return True

        if user.role != User.Role.STUDENT:
            return False

        course_id = self._resolve_course_id(view, obj)
        if course_id is None:
            return False

        return CourseEnrollment.objects.filter(
            workspace=workspace,
            student=user,
            course_id=course_id,
            status=CourseEnrollment.Status.ACTIVE,
        ).exists()
