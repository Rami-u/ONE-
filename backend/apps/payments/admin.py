from django.contrib import admin
from .models import PaymentSubmission


@admin.register(PaymentSubmission)
class PaymentSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "workspace",
        "enrollment",
        "submitted_by",
        "amount",
        "method",
        "status",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    ]
    list_filter = ["status", "method", "workspace"]
    search_fields = [
        "submitted_by__email",
        "submitted_by__full_name",
        "enrollment__course__title",
        "workspace__name",
    ]
