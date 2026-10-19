from django.contrib import admin

from .models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "is_listed", "created_at")
    list_filter = ("status", "is_listed")
    search_fields = ("name", "slug", "subdomain")
    readonly_fields = ("created_at",)
