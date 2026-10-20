from django.db import models
from .image_validators import validate_workspace_logo
from .storage import public_logo_storage
from .validators import validate_workspace_slug


class Workspace(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(max_length=150)
    slug = models.CharField(
        max_length=63, unique=True, validators=[validate_workspace_slug]
    )
    subdomain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    logo = models.ImageField(
        max_length=500,
        upload_to="workspace_logos/",
        storage=public_logo_storage,
        validators=[validate_workspace_logo],
        null=True,
        blank=True,
    )
    headline = models.CharField(max_length=200, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    about = models.TextField(null=True, blank=True)
    is_listed = models.BooleanField(default=False)
    payment_instructions = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workspaces"
        ordering = ["name", "id"]

    def save(self, *args, **kwargs):
        validate_workspace_slug(self.slug)
        if self.pk:
            old_slug = type(self).objects.filter(pk=self.pk).values_list(
                "slug", flat=True
            ).first()
            if old_slug is not None and old_slug != self.slug:
                raise ValueError("A workspace slug is immutable after creation.")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
