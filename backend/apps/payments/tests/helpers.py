import struct
import tempfile
import zlib

from django.test import override_settings

from apps.payments.models import PaymentSubmission


class TemporaryMediaMixin:
    """Isolates MEDIA_ROOT to a temporary directory cleaned up after each test class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media_dir.name)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._media_override.disable()
        finally:
            if hasattr(cls, "_temp_media_dir"):
                try:
                    cls._temp_media_dir.cleanup()
                except Exception:
                    pass
            super().tearDownClass()


def build_png_bytes(width, height, corrupt_crc=False, header_only=False):
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr_chunk = (
        struct.pack(">I", len(ihdr_data))
        + b"IHDR"
        + ihdr_data
        + struct.pack(">I", ihdr_crc)
    )

    chunks = [sig, ihdr_chunk]
    if not header_only:
        compressed = zlib.compress(b"")
        idat_crc = 0xDEADBEEF if corrupt_crc else zlib.crc32(b"IDAT" + compressed)
        idat_chunk = (
            struct.pack(">I", len(compressed))
            + b"IDAT"
            + compressed
            + struct.pack(">I", idat_crc)
        )
        chunks.append(idat_chunk)

    iend_crc = zlib.crc32(b"IEND")
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    chunks.append(iend_chunk)
    return b"".join(chunks)


def build_png_no_idat_bytes(width=5, height=5):
    return build_png_bytes(width, height, header_only=True)


def build_dds_bytes():
    return b"DDS " + struct.pack("<I", 124) + (b"\x00" * 120) + b"\x00\x00\x00\x00"


def build_gif_bytes():
    return (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )


def build_pdf_bytes(size=5 * 1024 * 1024):
    header = b"%PDF-1.4\n"
    trailer = b"%%EOF\n"
    if size < len(header) + len(trailer):
        return header + trailer
    padding = b" " * (size - len(header) - len(trailer))
    return header + padding + trailer


def create_payment(
    workspace,
    enrollment,
    student,
    *,
    amount=None,
    method=PaymentSubmission.Method.TRANSFER,
    note="Test payment note",
    status=PaymentSubmission.Status.SUBMITTED,
    receipt_image=None,
    reviewed_by=None,
    reviewed_at=None,
    rejection_reason=None,
):
    if amount is None:
        amount = enrollment.price_at_enrollment
    return PaymentSubmission.objects.create(
        workspace=workspace,
        enrollment=enrollment,
        submitted_by=student,
        amount=amount,
        method=method,
        note=note,
        status=status,
        receipt_image=receipt_image,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        rejection_reason=rejection_reason,
    )
