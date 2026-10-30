from django.contrib import admin

from apps.proctoring.models import ProctoringEvent, ProctoringEvidence


class ReadOnlyAdmin(admin.ModelAdmin):
    """Proctoring rows are created by the pipeline and reviewed by teachers only."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProctoringEvent)
class ProctoringEventAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "workspace",
        "attempt",
        "event_type",
        "severity",
        "occurred_at",
        "review_status",
    )
    list_filter = ("event_type", "severity", "review_status")
    list_select_related = ("workspace", "attempt")
    ordering = ("-occurred_at",)


@admin.register(ProctoringEvidence)
class ProctoringEvidenceAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "workspace",
        "event",
        "evidence_type",
        "mime_type",
        "file_size",
        "retention_expires_at",
    )
    list_filter = ("evidence_type",)
    list_select_related = ("workspace", "event")
    exclude = ("storage_key",)
    ordering = ("-created_at",)