from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError

MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}


def detect_receipt_type(file):
    initial_pos = file.tell()
    header = file.read(5)
    file.seek(initial_pos)
    if header.startswith(b"%PDF-"):
        return "pdf"

    try:
        image_file = Image.open(file)
        image_file.verify()
        fmt = image_file.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        file.seek(initial_pos)
        raise ValidationError("Receipt must be a valid JPEG, PNG, or PDF file.") from exc
    finally:
        file.seek(initial_pos)

    if fmt == "JPEG":
        return "jpeg"
    elif fmt == "PNG":
        return "png"

    raise ValidationError("Receipt must be a valid JPEG, PNG, or PDF file.")


def validate_receipt_file(file):
    if file.size > MAX_RECEIPT_SIZE:
        raise ValidationError("Receipt file size must not exceed 5 MB.")

    detect_receipt_type(file)
