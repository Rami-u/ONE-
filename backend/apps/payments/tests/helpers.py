import struct
import zlib

from apps.payments.models import PaymentSubmission


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
