from rest_framework import serializers

from apps.courses.models import Course

from .models import Topic


class TopicSerializer(serializers.ModelSerializer):
    # `slug` is optional on create; the service derives it from `name`.
    slug = serializers.SlugField(max_length=150, required=False)
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.none(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Topic
        fields = ["id", "name", "slug", "course", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"name": {"max_length": 150}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workspace = self.context.get("workspace")
        if workspace is not None:
            # Scope the relation to the URL workspace so ids from other
            # workspaces are rejected as "does not exist".
            self.fields["course"].queryset = Course.objects.filter(workspace=workspace)