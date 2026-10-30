from django.conf import settings
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