from apps.accounts.models import User
from apps.workspaces.models import Workspace


def create_workspace(slug, name=None, status=Workspace.Status.ACTIVE):
    return Workspace.objects.create(name=name or slug.title(), slug=slug, status=status)


def create_teacher(workspace, *, email="teacher@example.com", password="Teacher-strong-password-123!"):
    return User.objects.create_user(
        email=email,
        password=password,
        full_name="Workspace Teacher",
        workspace=workspace,
        role=User.Role.TEACHER,
    )


def create_student(
    workspace,
    *,
    email="student@example.com",
    password="Student-strong-password-123!",
    approval_status=User.ApprovalStatus.PENDING,
    **fields,
):
    return User.objects.create_user(
        email=email,
        password=password,
        full_name="Workspace Student",
        workspace=workspace,
        role=User.Role.STUDENT,
        approval_status=approval_status,
        **fields,
    )
