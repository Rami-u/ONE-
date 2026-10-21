from django.contrib import admin
from .models import CourseEnrollment


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "workspace",
        "student",
        "course",
        "status",
        "price_at_enrollment",
        "created_at",
        "activated_at",
    ]
    list_filter = ["status", "workspace"]
    search_fields = ["student__email", "student__full_name", "course__title", "workspace__name"]
