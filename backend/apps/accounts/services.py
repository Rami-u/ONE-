from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.workspaces.models import Workspace

from .tokens import staff_password_token

User = get_user_model()


def password_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = staff_password_token.make_token(user)
    base_domain = settings.PLATFORM_BASE_DOMAIN.strip(".")
    url = (
        f"{settings.PLATFORM_URL_SCHEME}://{user.workspace.slug}.{base_domain}"
        f"/teacher/set-password/"
        f"?uid={uid}&token={token}"
    )
    return url


def send_staff_password_email(user, subject="Set your teacher password"):
    link = password_link(user)
    send_mail(
        subject,
        f"Use this link to set or reset your password. It expires after the configured password reset timeout:\n\n{link}",
        None,
        [user.email],
        fail_silently=False,
    )
    return link


def create_teacher_with_workspace(*, full_name, email, workspace_name, slug):
    """Atomically create a workspace and its teacher, then invite after commit."""
    with transaction.atomic():
        workspace = Workspace.objects.create(
            name=workspace_name,
            slug=slug,
            status=Workspace.Status.ACTIVE,
        )
        teacher = User.objects.create_user(
            email=email,
            password=None,
            full_name=full_name,
            workspace=workspace,
            role=User.Role.TEACHER,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        teacher.set_unusable_password()
        teacher.save(update_fields=["password"])

    delivery = {"sent": False}

    def send_invitation():
        try:
            send_staff_password_email(teacher)
        except Exception:  # The committed account remains recoverable via resend-invite.
            return
        delivery["sent"] = True

    transaction.on_commit(send_invitation)
    return teacher, workspace, delivery


def resend_teacher_invitation(teacher):
    send_staff_password_email(teacher)


def start_staff_password_reset(user):
    send_staff_password_email(user, subject="Reset your teacher password")
