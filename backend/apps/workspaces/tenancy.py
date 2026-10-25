from django.core.exceptions import ValidationError


def validate_same_workspace(instance, *field_names):
    """Reject foreign keys that link an instance to another workspace."""
    errors = {}
    for field_name in field_names:
        if getattr(instance, f"{field_name}_id") is None:
            continue
        related = getattr(instance, field_name)
        if related.workspace_id != instance.workspace_id:
            errors[field_name] = "Must belong to the same workspace."
    if errors:
        raise ValidationError(errors)
