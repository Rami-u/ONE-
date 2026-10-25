from django.contrib import admin

from .models import LessonTopic, Question, QuestionTopic, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "workspace"]
    list_filter = ["workspace"]
    search_fields = ["name", "slug", "workspace__name", "workspace__slug"]


@admin.register(LessonTopic)
class LessonTopicAdmin(admin.ModelAdmin):
    list_display = ["id", "lesson", "topic", "workspace"]
    list_filter = ["workspace"]
    search_fields = ["lesson__title", "topic__name", "workspace__name", "workspace__slug"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["id", "stem", "workspace", "status"]
    list_filter = ["workspace", "status"]
    search_fields = ["stem", "workspace__name", "workspace__slug"]


@admin.register(QuestionTopic)
class QuestionTopicAdmin(admin.ModelAdmin):
    list_display = ["id", "question", "topic", "workspace"]
    list_filter = ["workspace"]
    search_fields = ["question__stem", "topic__name", "workspace__name", "workspace__slug"]
