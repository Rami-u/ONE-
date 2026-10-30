from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.courses.tests.helpers import create_course


class ContentApiBase(APITestCase):
    """Two workspaces (alpha, beta) with a teacher and a course each,
    plus an approved and a pending student in alpha."""

    @classmethod
    def setUpTestData(cls):
        cls.alpha = create_workspace("alpha")
        cls.beta = create_workspace("beta")
        cls.alpha_teacher = create_teacher(cls.alpha, email="teacher@alpha.test")
        cls.beta_teacher = create_teacher(cls.beta, email="teacher@beta.test")
        cls.approved_student = create_student(
            cls.alpha,
            email="approved@alpha.test",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        cls.pending_student = create_student(
            cls.alpha,
            email="pending@alpha.test",
            approval_status=User.ApprovalStatus.PENDING,
        )
        cls.alpha_course = create_course(cls.alpha, title="Alpha course")
        cls.beta_course = create_course(cls.beta, title="Beta course")

    def login(self, user):
        self.client.force_login(user)
        return user