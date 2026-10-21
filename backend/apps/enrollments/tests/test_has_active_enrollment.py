from types import SimpleNamespace
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.courses.tests.helpers import create_course
from apps.enrollments.models import CourseEnrollment
from apps.enrollments.permissions import HasActiveEnrollment
from apps.enrollments.tests.helpers import create_enrollment
from apps.workspaces.models import Workspace


class HasActiveEnrollmentTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.permission = HasActiveEnrollment()

        self.workspace = create_workspace("school-perm")
        self.teacher = create_teacher(self.workspace)
        self.student = create_student(
            self.workspace,
            email="perm-student@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.course = create_course(self.workspace, title="Perm Course")

        self.other_workspace = create_workspace("other-perm")
        self.other_student = create_student(
            self.other_workspace,
            email="other-perm@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )

    def _build_request_and_view(self, user, workspace, course_id=None):
        request = self.factory.get("/fake-path/")
        request.user = user
        view = SimpleNamespace(
            workspace=workspace,
            kwargs={"course_id": course_id} if course_id is not None else {},
        )
        return request, view

    def test_anonymous_user_denied(self):
        from django.contrib.auth.models import AnonymousUser

        request, view = self._build_request_and_view(
            AnonymousUser(), self.workspace, self.course.id
        )
        self.assertFalse(self.permission.has_permission(request, view))

    def test_suspended_workspace_denied(self):
        self.workspace.status = Workspace.Status.SUSPENDED
        self.workspace.save()

        create_enrollment(
            self.workspace,
            self.student,
            self.course,
            status=CourseEnrollment.Status.ACTIVE,
        )
        request, view = self._build_request_and_view(
            self.student, self.workspace, self.course.id
        )
        self.assertFalse(self.permission.has_permission(request, view))

    def test_teacher_allowed(self):
        request, view = self._build_request_and_view(
            self.teacher, self.workspace, self.course.id
        )
        self.assertTrue(self.permission.has_permission(request, view))
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.course)
        )

    def test_student_from_another_workspace_denied(self):
        request, view = self._build_request_and_view(
            self.other_student, self.workspace, self.course.id
        )
        self.assertFalse(self.permission.has_permission(request, view))

    def test_unapproved_student_denied(self):
        unapproved = create_student(
            self.workspace,
            email="unapproved@example.com",
            approval_status=User.ApprovalStatus.PENDING,
        )
        request, view = self._build_request_and_view(
            unapproved, self.workspace, self.course.id
        )
        self.assertFalse(self.permission.has_permission(request, view))

    def test_student_with_no_enrollment_denied(self):
        request, view = self._build_request_and_view(
            self.student, self.workspace, self.course.id
        )
        self.assertFalse(self.permission.has_permission(request, view))
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.course)
        )

    def test_student_with_pending_payment_denied(self):
        create_enrollment(
            self.workspace,
            self.student,
            self.course,
            status=CourseEnrollment.Status.PENDING_PAYMENT,
        )
        request, view = self._build_request_and_view(
            self.student, self.workspace, self.course.id
        )
        self.assertFalse(self.permission.has_permission(request, view))
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.course)
        )

    def test_student_with_withdrawn_enrollment_denied(self):
        create_enrollment(
            self.workspace,
            self.student,
            self.course,
            status=CourseEnrollment.Status.WITHDRAWN,
        )
        request, view = self._build_request_and_view(
            self.student, self.workspace, self.course.id
        )
        self.assertFalse(self.permission.has_permission(request, view))
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.course)
        )

    def test_student_with_active_enrollment_granted(self):
        create_enrollment(
            self.workspace,
            self.student,
            self.course,
            status=CourseEnrollment.Status.ACTIVE,
        )
        request, view = self._build_request_and_view(
            self.student, self.workspace, self.course.id
        )
        self.assertTrue(self.permission.has_permission(request, view))
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.course)
        )

    def test_object_permission_with_nested_course_attribute(self):
        create_enrollment(
            self.workspace,
            self.student,
            self.course,
            status=CourseEnrollment.Status.ACTIVE,
        )
        request, view = self._build_request_and_view(self.student, self.workspace)
        lesson_mock = SimpleNamespace(course=self.course)
        self.assertTrue(
            self.permission.has_object_permission(request, view, lesson_mock)
        )
