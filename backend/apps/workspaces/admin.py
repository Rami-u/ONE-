from django.contrib import admin

from .models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "is_listed", "created_at")
    list_filter = ("status", "is_listed")
    search_fields = ("name", "slug", "subdomain")
    readonly_fields = ("created_at",)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj is not None:
            return (*readonly_fields, "slug")
        return readonly_fields
