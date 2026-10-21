from decimal import Decimal

from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.courses.tests.helpers import create_course
from apps.enrollments.models import CourseEnrollment
from .helpers import create_enrollment


class CourseEnrollmentModelTests(APITestCase):
    def test_enrollment_model_table_name_and_unique_constraint(self):
        self.assertEqual(CourseEnrollment._meta.db_table, "course_enrollments")
        workspace = create_workspace("school-enr")
        student = create_student(workspace, approval_status=User.ApprovalStatus.APPROVED)
        course = create_course(workspace, title="Math 101", price="50.00")

        enrollment = CourseEnrollment.objects.create(
            workspace=workspace,
            student=student,
            course=course,
            price_at_enrollment=course.price,
        )
        self.assertEqual(enrollment.status, CourseEnrollment.Status.PENDING_PAYMENT)
        self.assertIsNone(enrollment.activated_at)

        # Unique constraint on student and course
        with self.assertRaises(IntegrityError):
            CourseEnrollment.objects.create(
                workspace=workspace,
                student=student,
                course=course,
                price_at_enrollment=course.price,
            )


class CourseEnrollmentApiTests(APITestCase):
    def setUp(self):
        self.workspace_a = create_workspace("alpha")
        self.workspace_a.payment_instructions = "Transfer to Bank XYZ Acc 12345"
        self.workspace_a.save()

        self.teacher_a = create_teacher(self.workspace_a, email="teacher-a@example.com")
        self.student_a = create_student(
            self.workspace_a,
            email="student-a@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.pending_student = create_student(
            self.workspace_a,
            email="pending@example.com",
            approval_status=User.ApprovalStatus.PENDING,
        )
        self.rejected_student = create_student(
            self.workspace_a,
            email="rejected@example.com",
            approval_status=User.ApprovalStatus.REJECTED,
        )

        self.workspace_b = create_workspace("beta")
        self.teacher_b = create_teacher(self.workspace_b, email="teacher-b@example.com")
        self.student_b = create_student(
            self.workspace_b,
            email="student-b@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )

        self.free_course = create_course(
            self.workspace_a,
            title="Free Python",
            price="0.00",
            is_published=True,
        )
        self.paid_course = create_course(
            self.workspace_a,
            title="Paid Django",
            price="500.00",
            is_published=True,
        )
        self.draft_course = create_course(
            self.workspace_a,
            title="Draft Biology",
            price="100.00",
            is_published=False,
        )
        self.course_b = create_course(
            self.workspace_b,
            title="Beta Course",
            price="200.00",
            is_published=True,
        )

    def test_enroll_in_free_course_activates_immediately(self):
        self.client.force_login(self.student_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.free_course.id}/enroll/"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "active")
        self.assertEqual(response.data["price"], "0.00")
        self.assertEqual(
            response.data["payment_instructions"],
            "Transfer to Bank XYZ Acc 12345",
        )

        enrollment = CourseEnrollment.objects.get(pk=response.data["enrollment_id"])
        self.assertEqual(enrollment.status, CourseEnrollment.Status.ACTIVE)
        self.assertIsNotNone(enrollment.activated_at)
        self.assertEqual(enrollment.price_at_enrollment, Decimal("0.00"))

    def test_enroll_in_paid_course_starts_pending_payment(self):
        self.client.force_login(self.student_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.paid_course.id}/enroll/"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending_payment")
        self.assertEqual(response.data["price"], "500.00")
        self.assertEqual(
            response.data["payment_instructions"],
            "Transfer to Bank XYZ Acc 12345",
        )

        enrollment = CourseEnrollment.objects.get(pk=response.data["enrollment_id"])
        self.assertEqual(enrollment.status, CourseEnrollment.Status.PENDING_PAYMENT)
        self.assertIsNone(enrollment.activated_at)
        self.assertEqual(enrollment.price_at_enrollment, Decimal("500.00"))

    def test_duplicate_enrollment_returns_existing_enrollment(self):
        self.client.force_login(self.student_a)
        first_res = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.paid_course.id}/enroll/"
        )
        self.assertEqual(first_res.status_code, status.HTTP_201_CREATED)
        first_id = first_res.data["enrollment_id"]

        # Second enroll attempt
        second_res = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.paid_course.id}/enroll/"
        )
        self.assertEqual(second_res.status_code, status.HTTP_200_OK)
        self.assertEqual(second_res.data["enrollment_id"], first_id)
        self.assertEqual(second_res.data["status"], "pending_payment")
        self.assertEqual(CourseEnrollment.objects.filter(student=self.student_a).count(), 1)

    def test_enroll_in_draft_course_returns_404(self):
        self.client.force_login(self.student_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.draft_course.id}/enroll/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_enrolling_in_course_of_another_workspace_is_rejected(self):
        self.client.force_login(self.student_a)
        # Passing course_b (belongs to beta) under alpha slug
        response = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.course_b.id}/enroll/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_from_workspace_a_cannot_enroll_in_workspace_b(self):
        self.client.force_login(self.student_a)
        response = self.client.post(
            f"/api/v1/workspaces/beta/courses/{self.course_b.id}/enroll/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pending_and_rejected_students_cannot_enroll(self):
        self.client.force_login(self.pending_student)
        res_pending = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.paid_course.id}/enroll/"
        )
        self.assertEqual(res_pending.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(self.rejected_student)
        res_rejected = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.paid_course.id}/enroll/"
        )
        self.assertEqual(res_rejected.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_cannot_enroll_in_courses(self):
        self.client.force_login(self.teacher_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.paid_course.id}/enroll/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_price_change_after_enrollment_does_not_change_price_at_enrollment(self):
        self.client.force_login(self.student_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/courses/{self.paid_course.id}/enroll/"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment_id = response.data["enrollment_id"]

        # Teacher changes course price
        self.paid_course.price = Decimal("999.00")
        self.paid_course.save()

        enrollment = CourseEnrollment.objects.get(pk=enrollment_id)
        self.assertEqual(enrollment.price_at_enrollment, Decimal("500.00"))

    def test_student_lists_own_enrollments(self):
        create_enrollment(
            self.workspace_a,
            self.student_a,
            self.paid_course,
            status=CourseEnrollment.Status.PENDING_PAYMENT,
            price="500.00",
        )
        create_enrollment(
            self.workspace_a,
            self.pending_student,
            self.free_course,
            status=CourseEnrollment.Status.ACTIVE,
        )

        self.client.force_login(self.student_a)
        response = self.client.get("/api/v1/workspaces/alpha/enrollments/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["course_id"], self.paid_course.id)
        self.assertEqual(results[0]["status"], "pending_payment")
        self.assertEqual(results[0]["price_at_enrollment"], "500.00")
