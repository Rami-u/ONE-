from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .identity import build_login_key
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "admin", "Platform admin"
        TEACHER = "teacher", "Teacher"
        ASSISTANT = "assistant", "Assistant"
        STUDENT = "student", "Student"

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    email = models.EmailField(max_length=254)
    login_key = models.CharField(max_length=320, unique=True, editable=False)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="reviewed_users",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "login_key"
    REQUIRED_FIELDS = ["email", "full_name"]

    class Meta:
        db_table = "users"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace"],
                condition=Q(role="teacher"),
                name="one_teacher_per_workspace",
            ),
            models.CheckConstraint(
                condition=(
                    Q(role="admin", workspace__isnull=True)
                    | (~Q(role="admin") & Q(workspace__isnull=False))
                ),
                name="admin_workspace_null_matches_role",
            ),
        ]
        ordering = ["full_name", "id"]

    @property
    def expected_login_key(self):
        return build_login_key(self.workspace_id, self.email)

    def save(self, *args, **kwargs):
        self.email = UserManager.normalize_email_address(self.email)
        self.login_key = self.expected_login_key
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"email", "login_key"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.login_key
