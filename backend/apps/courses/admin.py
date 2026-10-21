from django.contrib import admin
from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "workspace", "price", "is_published", "created_at"]
    list_filter = ["is_published", "workspace"]
    search_fields = ["title", "description", "workspace__name", "workspace__slug"]
