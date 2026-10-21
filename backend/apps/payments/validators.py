from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError

MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}


def validate_receipt_file(file):
    if file.size > MAX_RECEIPT_SIZE:
        raise ValidationError("Receipt file size must not exceed 5 MB.")

    initial_pos = file.tell()
    header = file.read(5)
    file.seek(initial_pos)
    if header.startswith(b"%PDF-"):
        return

    try:
        image_file = Image.open(file)
        image_file.verify()
        fmt = image_file.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        file.seek(initial_pos)
        raise ValidationError("Receipt must be a valid JPEG, PNG, or PDF file.") from exc
    finally:
        file.seek(initial_pos)

    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Receipt must be a valid JPEG, PNG, or PDF file.")
