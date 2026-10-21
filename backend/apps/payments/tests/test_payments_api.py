from decimal import Decimal
from io import BytesIO
import re

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.courses.tests.helpers import create_course
from apps.enrollments.models import CourseEnrollment
from apps.enrollments.tests.helpers import create_enrollment
from apps.payments.models import PaymentSubmission
from apps.payments.storage import private_receipt_storage
from .helpers import (
    build_gif_bytes,
    build_pdf_bytes,
    build_png_bytes,
    create_payment,
)


def sample_image_file(name="receipt.png", fmt="PNG", size=(10, 10)):
    buf = BytesIO()
    img = Image.new("RGB", size, "red")
    img.save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def sample_pdf_file(name="receipt.pdf", content=b"%PDF-1.4 dummy pdf content for testing"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class PaymentSubmissionModelTests(APITestCase):
    def test_model_table_name_and_conditional_unique_constraint(self):
        self.assertEqual(PaymentSubmission._meta.db_table, "payment_submissions")
        workspace = create_workspace("school-pay-model")
        teacher = create_teacher(workspace)
        student = create_student(workspace, approval_status=User.ApprovalStatus.APPROVED)
        course = create_course(workspace, price="100.00")
        enrollment = create_enrollment(workspace, student, course)

        claim1 = PaymentSubmission.objects.create(
            workspace=workspace,
            enrollment=enrollment,
            submitted_by=student,
            amount=enrollment.price_at_enrollment,
            method=PaymentSubmission.Method.TRANSFER,
            status=PaymentSubmission.Status.SUBMITTED,
        )
        self.assertEqual(claim1.status, PaymentSubmission.Status.SUBMITTED)

        # Second submitted claim on same enrollment fails conditional unique constraint
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                PaymentSubmission.objects.create(
                    workspace=workspace,
                    enrollment=enrollment,
                    submitted_by=student,
                    amount=enrollment.price_at_enrollment,
                    method=PaymentSubmission.Method.CASH,
                    status=PaymentSubmission.Status.SUBMITTED,
                )

        # After rejection, a new submitted claim is allowed
        claim1.status = PaymentSubmission.Status.REJECTED
        claim1.save()

        claim2 = PaymentSubmission.objects.create(
            workspace=workspace,
            enrollment=enrollment,
            submitted_by=student,
            amount=enrollment.price_at_enrollment,
            method=PaymentSubmission.Method.E_WALLET,
            status=PaymentSubmission.Status.SUBMITTED,
        )
        self.assertEqual(claim2.status, PaymentSubmission.Status.SUBMITTED)


class PaymentApiTests(APITestCase):
    def setUp(self):
        self.workspace_a = create_workspace("alpha")
        self.teacher_a = create_teacher(self.workspace_a, email="teacher-a@example.com")
        self.student_a1 = create_student(
            self.workspace_a,
            email="student-a1@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.student_a2 = create_student(
            self.workspace_a,
            email="student-a2@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )

        self.workspace_b = create_workspace("beta")
        self.teacher_b = create_teacher(self.workspace_b, email="teacher-b@example.com")
        self.student_b = create_student(
            self.workspace_b,
            email="student-b@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )

        self.course_a = create_course(self.workspace_a, price="150.00", is_published=True)
        self.enrollment_a1 = create_enrollment(
            self.workspace_a,
            self.student_a1,
            self.course_a,
            status=CourseEnrollment.Status.PENDING_PAYMENT,
            price="150.00",
        )

    def test_student_submits_payment_claim_amount_derived_by_server(self):
        self.client.force_login(self.student_a1)
        receipt = sample_image_file("proof.png", "PNG")
        payload = {
            "method": "transfer",
            "note": "Ref #123456",
            "receipt_image": receipt,
            "amount": "0.01",  # Client tries to send wrong amount
        }
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data=payload,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "150.00")  # Derived from enrollment!
        self.assertEqual(response.data["status"], "submitted")
        self.assertEqual(response.data["method"], "transfer")
        self.assertTrue(response.data["has_receipt"])

        submission = PaymentSubmission.objects.get(pk=response.data["id"])
        self.assertEqual(submission.amount, Decimal("150.00"))
        self.assertEqual(submission.submitted_by, self.student_a1)

    def test_price_change_after_enrollment_does_not_change_claim_amount(self):
        # Teacher changes course price
        self.course_a.price = Decimal("300.00")
        self.course_a.save()

        self.client.force_login(self.student_a1)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "e_wallet"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "150.00")

    def test_only_one_open_claim_allowed_per_enrollment(self):
        create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.SUBMITTED,
        )

        self.client.force_login(self.student_a1)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "cash"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already submitted", response.data["detail"])

    def test_resubmission_allowed_after_rejection(self):
        create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.REJECTED,
            rejection_reason="Unclear photo",
        )

        self.client.force_login(self.student_a1)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "note": "Clearer photo"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "submitted")

    def test_cannot_submit_claim_for_already_active_enrollment(self):
        self.enrollment_a1.status = CourseEnrollment.Status.ACTIVE
        self.enrollment_a1.save()

        self.client.force_login(self.student_a1)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_student_cannot_submit_claim_for_another_students_enrollment(self):
        self.client.force_login(self.student_a2)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_from_another_workspace_cannot_submit_claim(self):
        self.client.force_login(self.student_b)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_cannot_submit_payment_claim(self):
        self.client.force_login(self.teacher_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_lists_payments_and_filters_by_status(self):
        p1 = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.SUBMITTED,
        )
        enrollment_a2 = create_enrollment(
            self.workspace_a,
            self.student_a2,
            self.course_a,
            status=CourseEnrollment.Status.ACTIVE,
        )
        p2 = create_payment(
            self.workspace_a,
            enrollment_a2,
            self.student_a2,
            status=PaymentSubmission.Status.CONFIRMED,
        )

        self.client.force_login(self.teacher_a)
        # All payments
        res_all = self.client.get("/api/v1/workspaces/alpha/payments/")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_all.data["results"]), 2)

        # Filter by status=submitted
        res_sub = self.client.get("/api/v1/workspaces/alpha/payments/?status=submitted")
        self.assertEqual(res_sub.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_sub.data["results"]), 1)
        self.assertEqual(res_sub.data["results"][0]["id"], p1.id)

    def test_student_cannot_list_payments(self):
        self.client.force_login(self.student_a1)
        response = self.client.get("/api/v1/workspaces/alpha/payments/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_workspace_teacher_cannot_list_payments(self):
        self.client.force_login(self.teacher_b)
        response = self.client.get("/api/v1/workspaces/alpha/payments/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_confirms_payment_activates_enrollment_in_same_transaction(self):
        payment = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.SUBMITTED,
        )

        self.client.force_login(self.teacher_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/confirm/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(response.data["reviewed_by_id"], self.teacher_a.id)

        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentSubmission.Status.CONFIRMED)
        self.assertEqual(payment.reviewed_by, self.teacher_a)
        self.assertIsNotNone(payment.reviewed_at)

        self.enrollment_a1.refresh_from_db()
        self.assertEqual(self.enrollment_a1.status, CourseEnrollment.Status.ACTIVE)
        self.assertIsNotNone(self.enrollment_a1.activated_at)

    def test_student_cannot_confirm_payment_including_own(self):
        payment = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.SUBMITTED,
        )

        self.client.force_login(self.student_a1)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/confirm/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_rejects_payment_enrollment_stays_pending_payment(self):
        payment = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.SUBMITTED,
        )

        self.client.force_login(self.teacher_a)
        payload = {"rejection_reason": "Receipt unreadable. Please upload clearer photo."}
        response = self.client.post(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/reject/",
            data=payload,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "rejected")
        self.assertEqual(
            response.data["rejection_reason"],
            "Receipt unreadable. Please upload clearer photo.",
        )

        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentSubmission.Status.REJECTED)
        self.assertEqual(payment.reviewed_by, self.teacher_a)
        self.assertIsNotNone(payment.reviewed_at)

        self.enrollment_a1.refresh_from_db()
        self.assertEqual(self.enrollment_a1.status, CourseEnrollment.Status.PENDING_PAYMENT)
        self.assertIsNone(self.enrollment_a1.activated_at)

    def test_reject_payment_requires_reason(self):
        payment = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.SUBMITTED,
        )

        self.client.force_login(self.teacher_a)
        response = self.client.post(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/reject/",
            data={"rejection_reason": ""},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_or_reject_already_reviewed_payment_returns_409(self):
        payment = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            status=PaymentSubmission.Status.CONFIRMED,
        )

        self.client.force_login(self.teacher_a)
        # Try to confirm again
        res_conf = self.client.post(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/confirm/"
        )
        self.assertEqual(res_conf.status_code, status.HTTP_409_CONFLICT)

        # Try to reject
        res_rej = self.client.post(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/reject/",
            data={"rejection_reason": "Too late"},
        )
        self.assertEqual(res_rej.status_code, status.HTTP_409_CONFLICT)

    def test_authorized_receipt_view_teacher_and_owning_student(self):
        receipt_file = sample_image_file("receipt.png")
        payment = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            receipt_image=receipt_file,
        )

        # Teacher of workspace A can view
        self.client.force_login(self.teacher_a)
        res_teacher = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/receipt/"
        )
        self.assertEqual(res_teacher.status_code, status.HTTP_200_OK)
        self.assertEqual(res_teacher["Content-Type"], "image/png")

        # Owning student can view
        self.client.force_login(self.student_a1)
        res_owner = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/receipt/"
        )
        self.assertEqual(res_owner.status_code, status.HTTP_200_OK)

        # Another student in workspace A cannot view
        self.client.force_login(self.student_a2)
        res_other = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/receipt/"
        )
        self.assertEqual(res_other.status_code, status.HTTP_403_FORBIDDEN)

        # User from workspace B cannot view
        self.client.force_login(self.student_b)
        res_b = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/receipt/"
        )
        self.assertEqual(res_b.status_code, status.HTTP_403_FORBIDDEN)

    def test_receipt_validation_pdf_jpeg_png_and_size_limits(self):
        self.client.force_login(self.student_a1)

        # Valid JPEG
        jpeg_file = sample_image_file("proof.jpg", "JPEG")
        res_jpeg = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": jpeg_file},
            format="multipart",
        )
        self.assertEqual(res_jpeg.status_code, status.HTTP_201_CREATED)
        PaymentSubmission.objects.all().delete()

        # Valid PDF
        pdf_file = sample_pdf_file("proof.pdf")
        res_pdf = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": pdf_file},
            format="multipart",
        )
        self.assertEqual(res_pdf.status_code, status.HTTP_201_CREATED)
        PaymentSubmission.objects.all().delete()

        # Invalid file type (text file)
        text_file = SimpleUploadedFile("bad.txt", b"plain text receipt", content_type="text/plain")
        res_bad_type = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": text_file},
            format="multipart",
        )
        self.assertEqual(res_bad_type.status_code, status.HTTP_400_BAD_REQUEST)

        # File > 5 MB
        oversized = SimpleUploadedFile(
            "large.pdf",
            b"%PDF-" + b"0" * (5 * 1024 * 1024 + 10),
            content_type="application/pdf",
        )
        res_oversized = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": oversized},
            format="multipart",
        )
        self.assertEqual(res_oversized.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receipt_pdf_with_html_name_stored_as_pdf_and_served_as_application_pdf(self):
        self.client.force_login(self.student_a1)
        pdf_html = SimpleUploadedFile(
            "receipt.html",
            b"%PDF-1.4 <script>alert('xss')</script>",
            content_type="text/html",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": pdf_html},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        submission = PaymentSubmission.objects.get(pk=res.data["id"])
        self.assertTrue(submission.receipt_image.name.endswith(".pdf"))
        self.assertNotIn("html", submission.receipt_image.name)

        # Retrieve receipt
        receipt_res = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{submission.id}/receipt/"
        )
        self.assertEqual(receipt_res.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_res["Content-Type"], "application/pdf")
        self.assertEqual(receipt_res["Content-Disposition"], "inline")

    def test_receipt_png_with_svg_name_stored_as_png_and_served_as_image_png(self):
        self.client.force_login(self.student_a1)
        png_svg = sample_image_file("x.svg", fmt="PNG")
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": png_svg},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        submission = PaymentSubmission.objects.get(pk=res.data["id"])
        self.assertTrue(submission.receipt_image.name.endswith(".png"))
        self.assertNotIn("svg", submission.receipt_image.name)

        receipt_res = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{submission.id}/receipt/"
        )
        self.assertEqual(receipt_res.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_res["Content-Type"], "image/png")
        self.assertEqual(receipt_res["Content-Disposition"], "inline")

    def test_receipt_jpeg_with_html_name_stored_as_jpg_and_served_as_image_jpeg(self):
        self.client.force_login(self.student_a1)
        jpeg_html = sample_image_file("x.html", fmt="JPEG")
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": jpeg_html},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        submission = PaymentSubmission.objects.get(pk=res.data["id"])
        self.assertTrue(submission.receipt_image.name.endswith(".jpg"))
        self.assertNotIn("html", submission.receipt_image.name)

        receipt_res = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{submission.id}/receipt/"
        )
        self.assertEqual(receipt_res.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_res["Content-Type"], "image/jpeg")
        self.assertEqual(receipt_res["Content-Disposition"], "inline")

    def test_receipt_path_traversal_name_stored_as_uuid_hex(self):
        self.client.force_login(self.student_a1)
        evil_file = sample_image_file("../../evil.png", fmt="PNG")
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": evil_file},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        submission = PaymentSubmission.objects.get(pk=res.data["id"])
        self.assertRegex(submission.receipt_image.name, r"^receipts/[0-9a-f]{32}\.png$")

    def test_receipt_legacy_old_html_served_as_octet_stream_attachment(self):
        saved_file = private_receipt_storage.save("receipts/old.html", ContentFile(b"legacy receipt"))
        payment = create_payment(
            self.workspace_a,
            self.enrollment_a1,
            self.student_a1,
            receipt_image=saved_file,
        )
        self.client.force_login(self.student_a1)
        receipt_res = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{payment.id}/receipt/"
        )
        self.assertEqual(receipt_res.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_res["Content-Type"], "application/octet-stream")
        self.assertEqual(receipt_res["Content-Disposition"], "attachment")

    def test_receipt_response_headers_nosniff_and_cache_control(self):
        self.client.force_login(self.student_a1)
        valid_png = sample_image_file("receipt.png", fmt="PNG")
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": valid_png},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        receipt_res = self.client.get(
            f"/api/v1/workspaces/alpha/payments/{res.data['id']}/receipt/"
        )
        self.assertEqual(receipt_res.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_res["X-Content-Type-Options"], "nosniff")
        self.assertEqual(receipt_res["Cache-Control"], "private, no-store")

    def test_receipt_corrupted_crc_png_returns_400(self):
        self.client.force_login(self.student_a1)
        corrupted_png = SimpleUploadedFile(
            "corrupt.png",
            build_png_bytes(100, 100, corrupt_crc=True),
            content_type="image/png",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": corrupted_png},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receipt_header_only_png_20000x20000_returns_400(self):
        self.client.force_login(self.student_a1)
        huge_png = SimpleUploadedFile(
            "huge.png",
            build_png_bytes(20000, 20000, header_only=True),
            content_type="image/png",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": huge_png},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receipt_png_exactly_5000x5000_returns_201(self):
        self.client.force_login(self.student_a1)
        limit_png = SimpleUploadedFile(
            "limit.png",
            build_png_bytes(5000, 5000, header_only=False),
            content_type="image/png",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": limit_png},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_receipt_png_5000x5001_returns_400(self):
        self.client.force_login(self.student_a1)
        oversized_dim_png = SimpleUploadedFile(
            "oversized_dim.png",
            build_png_bytes(5000, 5001, header_only=False),
            content_type="image/png",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": oversized_dim_png},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Receipt image dimensions are too large.", str(res.data))

    def test_receipt_gif_returns_400(self):
        self.client.force_login(self.student_a1)
        gif_file = SimpleUploadedFile(
            "receipt.gif",
            build_gif_bytes(),
            content_type="image/gif",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": gif_file},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receipt_pdf_exactly_5mb_returns_201(self):
        self.client.force_login(self.student_a1)
        pdf_5mb = SimpleUploadedFile(
            "receipt_5mb.pdf",
            build_pdf_bytes(5 * 1024 * 1024),
            content_type="application/pdf",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": pdf_5mb},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_receipt_pdf_5mb_plus_one_byte_returns_400(self):
        self.client.force_login(self.student_a1)
        pdf_over = SimpleUploadedFile(
            "receipt_over.pdf",
            build_pdf_bytes(5 * 1024 * 1024 + 1),
            content_type="application/pdf",
        )
        res = self.client.post(
            f"/api/v1/workspaces/alpha/enrollments/{self.enrollment_a1.id}/payments/",
            data={"method": "transfer", "receipt_image": pdf_over},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

