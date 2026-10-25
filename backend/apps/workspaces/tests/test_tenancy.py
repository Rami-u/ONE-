from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.courses.tests.helpers import create_course
from apps.enrollments.models import CourseEnrollment
from apps.workspaces.tenancy import validate_same_workspace


class ValidateSameWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.workspace = create_workspace("tenancy-one")
        cls.other_workspace = create_workspace("tenancy-two")
        cls.teacher = create_teacher(cls.workspace)
        cls.other_teacher = create_teacher(cls.other_workspace)
        cls.student = create_student(cls.workspace)
        cls.course = create_course(cls.workspace)
        cls.other_course = create_course(cls.other_workspace)
        cls.platform_admin = User.objects.create_superuser(
            email="admin@example.com", password=None, full_name="Platform Admin"
        )

    def test_same_workspace_passes(self):
        self.student.reviewed_by = self.teacher
        validate_same_workspace(self.student, "reviewed_by")

    def test_different_workspace_fails(self):
        self.student.reviewed_by = self.other_teacher
        with self.assertRaises(ValidationError):
            validate_same_workspace(self.student, "reviewed_by")

    def test_unset_nullable_foreign_key_is_skipped(self):
        self.student.reviewed_by = None
        with self.assertNumQueries(0):
            validate_same_workspace(self.student, "reviewed_by")

    def test_error_is_keyed_to_the_foreign_key_field(self):
        self.student.reviewed_by = self.other_teacher
        with self.assertRaises(ValidationError) as error:
            validate_same_workspace(self.student, "reviewed_by")
        self.assertEqual(set(error.exception.message_dict), {"reviewed_by"})

    def test_tenant_object_foreign_key_uses_its_workspace_id(self):
        enrollment = CourseEnrollment(
            workspace=self.workspace, course=self.other_course, student=self.student
        )
        with self.assertRaises(ValidationError) as error:
            validate_same_workspace(enrollment, "course", "student")
        self.assertEqual(set(error.exception.message_dict), {"course"})

    def test_all_mismatched_foreign_keys_are_reported(self):
        enrollment = CourseEnrollment(
            workspace=self.other_workspace, course=self.course, student=self.student
        )
        with self.assertRaises(ValidationError) as error:
            validate_same_workspace(enrollment, "course", "student")
        self.assertEqual(set(error.exception.message_dict), {"course", "student"})

    def test_user_without_a_workspace_cannot_be_linked(self):
        self.student.reviewed_by = self.platform_admin
        with self.assertRaises(ValidationError) as error:
            validate_same_workspace(self.student, "reviewed_by")
        self.assertEqual(set(error.exception.message_dict), {"reviewed_by"})
