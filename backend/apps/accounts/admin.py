from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("login_key", "email", "full_name", "role", "workspace", "is_active")
    list_filter = ("role", "approval_status", "is_active", "workspace")
    search_fields = ("login_key", "email", "full_name")
    readonly_fields = ("login_key", "last_login", "date_joined")
    exclude = ("password",)
