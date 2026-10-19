import re

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_WORKSPACE_SLUGS = frozenset(
    {
        "admin",
        "api",
        "www",
        "app",
        "static",
        "media",
        "mail",
        "support",
        "teacher",
        "login",
        "signup",
        "platform",
        "auth",
        "accounts",
        "dashboard",
        "billing",
        "docs",
        "help",
        "cdn",
        "assets",
        "files",
    }
)


@deconstructible
class WorkspaceSlugValidator:
    message = (
        "Use 3-63 lowercase letters or digits, separated by single hyphens; "
        "the slug cannot be reserved."
    )
    code = "invalid_workspace_slug"

    def __call__(self, value):
        if (
            len(value) < 3
            or len(value) > 63
            or not SLUG_PATTERN.fullmatch(value)
            or value in RESERVED_WORKSPACE_SLUGS
        ):
            raise ValidationError(self.message, code=self.code)


validate_workspace_slug = WorkspaceSlugValidator()
