from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.workspaces.models import Workspace


class PublicTeacherDirectorySerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ["slug", "name", "teacher_name", "logo", "headline"]

    @extend_schema_field(serializers.CharField())
    def get_teacher_name(self, workspace):
        teacher = workspace.public_teachers[0] if workspace.public_teachers else None
        return teacher.full_name if teacher else ""


class PublicCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_null=True, allow_blank=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)


class PublicTeacherProfileSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "slug",
            "name",
            "teacher_name",
            "logo",
            "headline",
            "bio",
            "about",
            "courses",
        ]

    @extend_schema_field(serializers.CharField())
    def get_teacher_name(self, workspace):
        teacher = workspace.public_teachers[0] if workspace.public_teachers else None
        return teacher.full_name if teacher else ""

    @extend_schema_field(PublicCourseSerializer(many=True))
    def get_courses(self, workspace):
        courses = getattr(workspace, "published_courses", None)
        if courses is None:
            courses = workspace.courses.filter(is_published=True).order_by("-created_at", "id")
        return PublicCourseSerializer(courses, many=True).data


class WorkspaceBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ["slug", "name", "logo", "headline", "status"]
        read_only_fields = fields


class WorkspaceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = [
            "slug",
            "name",
            "logo",
            "headline",
            "bio",
            "about",
            "is_listed",
            "payment_instructions",
        ]
        read_only_fields = ["slug"]
