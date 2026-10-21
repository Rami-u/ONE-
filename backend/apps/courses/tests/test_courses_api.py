from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.enrollments.tests.helpers import create_enrollment
from apps.workspaces.models import Workspace
from .helpers import create_course


class CourseModelTests(APITestCase):
    def test_course_model_properties_and_table_name(self):
        self.assertEqual(Course._meta.db_table, "courses")
        workspace = create_workspace("school-model")
        course = Course.objects.create(
            workspace=workspace,
            title="Algebra Basics",
            price=Decimal("49.99"),
        )
        self.assertEqual(str(course), "Algebra Basics")
        self.assertFalse(course.is_published)
        self.assertIsNotNone(course.created_at)


class CourseApiTests(APITestCase):
    def setUp(self):
        self.workspace_a = create_workspace("alpha")
        self.teacher_a = create_teacher(self.workspace_a, email="teacher-a@example.com")
        self.student_a = create_student(
            self.workspace_a,
            email="student-a@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )

        self.workspace_b = create_workspace("beta")
        self.teacher_b = create_teacher(self.workspace_b, email="teacher-b@example.com")
        self.student_b = create_student(
            self.workspace_b,
            email="student-b@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )

        self.published_course = create_course(
            self.workspace_a,
            title="Published Course",
            price="100.00",
            is_published=True,
        )
        self.draft_course = create_course(
            self.workspace_a,
            title="Draft Course",
            price="50.00",
            is_published=False,
        )

    def test_teacher_lists_all_courses_including_drafts(self):
        self.client.force_login(self.teacher_a)
        response = self.client.get("/api/v1/workspaces/alpha/courses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [c["title"] for c in response.data["results"]]
        self.assertIn("Published Course", titles)
        self.assertIn("Draft Course", titles)
        self.assertEqual(len(response.data["results"]), 2)

    def test_student_lists_only_published_courses_with_enrollment_status(self):
        create_enrollment(
            self.workspace_a,
            self.student_a,
            self.published_course,
            status=CourseEnrollment.Status.ACTIVE,
        )

        self.client.force_login(self.student_a)
        response = self.client.get("/api/v1/workspaces/alpha/courses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Published Course")
        self.assertEqual(results[0]["enrollment_status"], "active")

    def test_student_not_enrolled_has_null_enrollment_status(self):
        self.client.force_login(self.student_a)
        response = self.client.get("/api/v1/workspaces/alpha/courses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["enrollment_status"])

    def test_student_cannot_create_course(self):
        self.client.force_login(self.student_a)
        payload = {
            "title": "Hacked Course",
            "price": "10.00",
            "is_published": True,
        }
        response = self.client.post("/api/v1/workspaces/alpha/courses/", data=payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_creates_course_with_automatic_workspace(self):
        self.client.force_login(self.teacher_a)
        payload = {
            "title": "Physics 101",
            "description": "Introductory mechanics",
            "price": "75.00",
            "is_published": True,
        }
        response = self.client.post("/api/v1/workspaces/alpha/courses/", data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Physics 101")
        self.assertEqual(response.data["price"], "75.00")
        self.assertTrue(response.data["is_published"])

        created = Course.objects.get(pk=response.data["id"])
        self.assertEqual(created.workspace, self.workspace_a)

    def test_teacher_cannot_create_course_with_negative_price(self):
        self.client.force_login(self.teacher_a)
        payload = {
            "title": "Invalid Price Course",
            "price": "-10.00",
        }
        response = self.client.post("/api/v1/workspaces/alpha/courses/", data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_retrieves_draft_course(self):
        self.client.force_login(self.teacher_a)
        response = self.client.get(f"/api/v1/workspaces/alpha/courses/{self.draft_course.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.draft_course.id)

    def test_student_retrieves_published_course_but_draft_returns_404(self):
        self.client.force_login(self.student_a)
        res_pub = self.client.get(f"/api/v1/workspaces/alpha/courses/{self.published_course.id}/")
        self.assertEqual(res_pub.status_code, status.HTTP_200_OK)
        self.assertEqual(res_pub.data["id"], self.published_course.id)

        res_draft = self.client.get(f"/api/v1/workspaces/alpha/courses/{self.draft_course.id}/")
        self.assertEqual(res_draft.status_code, status.HTTP_404_NOT_FOUND)

    def test_teacher_updates_course(self):
        self.client.force_login(self.teacher_a)
        payload = {
            "title": "Updated Title",
            "is_published": True,
            "price": "120.00",
        }
        response = self.client.patch(
            f"/api/v1/workspaces/alpha/courses/{self.draft_course.id}/",
            data=payload,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.draft_course.refresh_from_db()
        self.assertEqual(self.draft_course.title, "Updated Title")
        self.assertTrue(self.draft_course.is_published)
        self.assertEqual(self.draft_course.price, Decimal("120.00"))

    def test_student_cannot_update_course(self):
        self.client.force_login(self.student_a)
        payload = {"title": "Student Edit"}
        response = self.client.patch(
            f"/api/v1/workspaces/alpha/courses/{self.published_course.id}/",
            data=payload,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_workspace_course_isolation(self):
        # Student from workspace B accessing workspace A courses
        self.client.force_login(self.student_b)
        res_list = self.client.get("/api/v1/workspaces/alpha/courses/")
        self.assertEqual(res_list.status_code, status.HTTP_403_FORBIDDEN)

        res_get = self.client.get(f"/api/v1/workspaces/alpha/courses/{self.published_course.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_403_FORBIDDEN)

        # Teacher from workspace B accessing workspace A courses
        self.client.force_login(self.teacher_b)
        res_list_teacher = self.client.get("/api/v1/workspaces/alpha/courses/")
        self.assertEqual(res_list_teacher.status_code, status.HTTP_403_FORBIDDEN)

        # Guessing course ID from workspace A on workspace B URL
        res_cross_id = self.client.get(f"/api/v1/workspaces/beta/courses/{self.published_course.id}/")
        self.assertEqual(res_cross_id.status_code, status.HTTP_404_NOT_FOUND)

    def test_suspended_workspace_blocks_course_access(self):
        self.workspace_a.status = Workspace.Status.SUSPENDED
        self.workspace_a.save()

        self.client.force_login(self.teacher_a)
        response = self.client.get("/api/v1/workspaces/alpha/courses/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Workspace is unavailable.")
