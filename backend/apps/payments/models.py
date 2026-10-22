from django.db import models
from .storage import private_receipt_storage
from .validators import validate_receipt_file


class PaymentSubmission(models.Model):
    class Method(models.TextChoices):
        TRANSFER = "transfer", "Transfer"
        E_WALLET = "e_wallet", "E-wallet"
        CASH = "cash", "Cash"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="payment_submissions",
    )
    enrollment = models.ForeignKey(
        "enrollments.CourseEnrollment",
        on_delete=models.PROTECT,
        related_name="payment_submissions",
    )
    submitted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="submitted_payments",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
    )
    note = models.TextField(null=True, blank=True)
    receipt_image = models.FileField(
        upload_to="receipts/",
        storage=private_receipt_storage,
        null=True,
        blank=True,
        validators=[validate_receipt_file],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="reviewed_payments",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "payment_submissions"
        ordering = ["-submitted_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment"],
                condition=models.Q(status="submitted"),
                name="unique_submitted_claim_per_enrollment",
            )
        ]

    def __str__(self):
        return f"Payment {self.id} for Enrollment {self.enrollment_id} ({self.status})"
