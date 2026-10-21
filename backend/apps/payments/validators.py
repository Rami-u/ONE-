from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError

MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_RECEIPT_PIXELS = 25_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}


def detect_receipt_type(file):
    initial_pos = file.tell()
    header = file.read(5)
    file.seek(initial_pos)
    if header.startswith(b"%PDF-"):
        return "pdf"

    try:
        image_file = Image.open(file)
        if image_file.size:
            width, height = image_file.size
            if width * height > MAX_RECEIPT_PIXELS:
                raise ValidationError("Receipt image dimensions are too large.")
        image_file.verify()
        fmt = image_file.format
    except ValidationError:
        file.seek(initial_pos)
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        EOFError,
        Image.DecompressionBombError,
    ) as exc:
        file.seek(initial_pos)
        raise ValidationError("Receipt must be a valid JPEG, PNG, or PDF file.") from exc
    finally:
        file.seek(initial_pos)

    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Receipt must be a valid JPEG, PNG, or PDF file.")

    if fmt == "JPEG":
        return "jpeg"
    elif fmt == "PNG":
        return "png"
    return fmt.lower()


def validate_receipt_file(file):
    if file.size > MAX_RECEIPT_SIZE:
        raise ValidationError("Receipt file size must not exceed 5 MB.")

    detect_receipt_type(file)

