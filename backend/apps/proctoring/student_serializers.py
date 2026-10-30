from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

ALLOWED_FRAME_TYPES = ("image/jpeg", "image/png", "image/webp")


class FrameUploadSerializer(serializers.Serializer):
    frame = serializers.FileField(
        help_text="One webcam frame as a JPEG, PNG or WebP image.",
    )

    def validate_frame(self, value):
        if value.size > settings.PROCTORING_FRAME_MAX_BYTES:
            raise serializers.ValidationError("The image is too large.")
        if value.content_type not in ALLOWED_FRAME_TYPES:
            raise serializers.ValidationError("Unsupported image type.")
        return value


class BrowserEventSerializer(serializers.Serializer):
    """A browser signal that can be attached to an in-progress attempt."""

    event_type = serializers.ChoiceField(choices=("tab_switch",))
    occurred_at = serializers.DateTimeField(default=timezone.now)


class FrameUploadResponseSerializer(serializers.Serializer):
    events_recorded = serializers.IntegerField()


class BrowserEventResponseSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
