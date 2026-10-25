from django.contrib import admin
from .models import Course, CourseSection, Lesson, LessonAsset


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "workspace", "price", "is_published", "created_at"]
    list_filter = ["is_published", "workspace"]
    search_fields = ["title", "description", "workspace__name", "workspace__slug"]


@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "workspace"]
    list_filter = ["workspace"]
    search_fields = ["title", "course__title", "workspace__name", "workspace__slug"]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "workspace"]
    list_filter = ["workspace"]
    search_fields = ["title", "course__title", "workspace__name", "workspace__slug"]


@admin.register(LessonAsset)
class LessonAssetAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "workspace", "extraction_status"]
    list_filter = ["workspace", "extraction_status"]
    search_fields = ["title", "lesson__title", "workspace__name", "workspace__slug"]
