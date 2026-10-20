import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.workspaces.models import Workspace

from .tokens import staff_password_token

User = get_user_model()
logger = logging.getLogger(__name__)


def _safe_email_exception_message(exc):
    message = re.sub(r"https?://\S+", "[redacted link]", str(exc))
    return re.sub(
        r"(?i)(token|password)=([^\s&]+)",
        r"\1=[redacted]",
        message,
    )


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
    timeout_days = (settings.PASSWORD_RESET_TIMEOUT + 86_399) // 86_400
    day_label = "day" if timeout_days == 1 else "days"
    send_mail(
        subject,
        f"Use this link to set or reset your password. It expires within {timeout_days} {day_label}:\n\n{link}",
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
            logger.warning(
                "Teacher invitation delivery failed for user_id=%s.", teacher.pk
            )
            return
        delivery["sent"] = True

    transaction.on_commit(send_invitation)
    return teacher, workspace, delivery


def resend_teacher_invitation(teacher):
    try:
        send_staff_password_email(teacher)
    except Exception:
        logger.warning(
            "Teacher invitation resend failed for user_id=%s.", teacher.pk
        )
        return False
    return True


def start_staff_password_reset(user):
    try:
        send_staff_password_email(user, subject="Reset your teacher password")
    except Exception:
        logger.warning(
            "Staff password reset email delivery failed for user_id=%s.", user.pk
        )
        return False
    return True


class StudentReviewConflict(APIException):
    status_code = 409
    default_detail = "Only pending students can be reviewed."
    default_code = "student_not_pending"


def review_student(*, student_id, workspace, reviewer, approval_status, rejection_reason=None):
    """Review a pending student and notify them only after the change commits."""
    with transaction.atomic():
        try:
            student = User.objects.select_for_update().filter(
                workspace=workspace,
                role=User.Role.STUDENT,
            ).get(pk=student_id)
        except User.DoesNotExist as exc:
            raise NotFound("Student not found.") from exc
        if student.approval_status != User.ApprovalStatus.PENDING:
            raise StudentReviewConflict()

        student.approval_status = approval_status
        student.reviewed_by = reviewer
        student.reviewed_at = timezone.now()
        student.rejection_reason = (
            rejection_reason if approval_status == User.ApprovalStatus.REJECTED else None
        )
        student.save(
            update_fields=[
                "approval_status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
            ]
        )

        def send_notification():
            if approval_status == User.ApprovalStatus.APPROVED:
                subject = "Your student account was approved"
                body = f"Your account for {workspace.name} has been approved. You can now sign in."
            else:
                subject = "Your student account was rejected"
                body = (
                    f"Your account for {workspace.name} was rejected.\n\n"
                    f"Reason: {rejection_reason}"
                )
            try:
                send_mail(subject, body, None, [student.email], fail_silently=False)
            except Exception as exc:
                logger.warning(
                    "Student review email failed user_id=%s exception_class=%s exception_message=%s",
                    student.pk,
                    type(exc).__name__,
                    _safe_email_exception_message(exc),
                )

        transaction.on_commit(send_notification)
    return student
