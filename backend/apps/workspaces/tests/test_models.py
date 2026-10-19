from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.workspaces.models import Workspace


class WorkspaceTests(TestCase):
    def test_slug_validator_accepts_only_normalized_single_hyphen_slugs(self):
        for slug in ("abc", "room-2", "a" * 63):
            with self.subTest(slug=slug):
                workspace = Workspace(name="Example", slug=slug)
                workspace.full_clean()

        for slug in (
            "ab",
            "Aaa",
            "-abc",
            "abc-",
            "ab--cd",
            "abc_def",
            "admin",
            "platform",
            "a" * 64,
        ):
            with self.subTest(slug=slug):
                workspace = Workspace(name="Example", slug=slug)
                with self.assertRaises(ValidationError):
                    workspace.full_clean()

    def test_slug_cannot_be_changed_after_creation(self):
        workspace = Workspace.objects.create(name="Example", slug="example")
        workspace.slug = "other"
        with self.assertRaisesMessage(ValueError, "immutable"):
            workspace.save()
