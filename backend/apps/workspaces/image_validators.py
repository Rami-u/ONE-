from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError


MAX_LOGO_SIZE = 2 * 1024 * 1024
ALLOWED_LOGO_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_workspace_logo(image):
    if image.size > MAX_LOGO_SIZE:
        raise ValidationError("Logo files must be 2 MB or smaller.")

    try:
        image_file = Image.open(image)
        image_file.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("Upload a valid JPEG, PNG, or WebP image.") from exc

    if image_file.format not in ALLOWED_LOGO_FORMATS:
        raise ValidationError("Upload a valid JPEG, PNG, or WebP image.")

    image.seek(0)
