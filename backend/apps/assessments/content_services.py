from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from rest_framework import serializers

from .models import Topic

TOPIC_SLUG_MAX_LENGTH = 150


def _unique_topic_slug(workspace, name):
    """Derive a slug from `name`, adding -2, -3, ... on a collision."""
    base = slugify(name)[:TOPIC_SLUG_MAX_LENGTH] or "topic"
    existing = set(
        Topic.objects.filter(workspace=workspace, slug__startswith=base).values_list("slug", flat=True)
    )
    if base not in existing:
        return base
    counter = 2
    while True:
        suffix = f"-{counter}"
        candidate = f"{base[: TOPIC_SLUG_MAX_LENGTH - len(suffix)]}{suffix}"
        if candidate not in existing:
            return candidate
        counter += 1


def _django_errors_to_drf(exc):
    if hasattr(exc, "message_dict"):
        return serializers.ValidationError(exc.message_dict)
    return serializers.ValidationError({"non_field_errors": exc.messages})


def create_topic(workspace, *, name, slug=None, course=None):
    with transaction.atomic():
        explicit_slug = bool(slug)
        topic = Topic(
            workspace=workspace,
            course=course,
            name=name,
            slug=slug if explicit_slug else _unique_topic_slug(workspace, name),
        )
        try:
            topic.full_clean()
            with transaction.atomic():
                topic.save()
        except DjangoValidationError as exc:
            raise _django_errors_to_drf(exc) from exc
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"slug": ["A topic with this slug already exists in this workspace."]}
            ) from exc
    return topic


def update_topic(topic, validated_data):
    with transaction.atomic():
        for field, value in validated_data.items():
            setattr(topic, field, value)
        try:
            topic.full_clean()
            with transaction.atomic():
                topic.save()
        except DjangoValidationError as exc:
            raise _django_errors_to_drf(exc) from exc
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"slug": ["A topic with this slug already exists in this workspace."]}
            ) from exc
    return topic