from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.workspaces.models import Workspace


class WorkspaceAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="a-secure-password",
            full_name="Platform Admin",
        )
        self.workspace = Workspace.objects.create(name="Example", slug="example")
        self.client.force_login(self.admin_user)

    def test_posting_a_changed_slug_to_change_page_keeps_original_slug(self):
        response = self.client.post(
            reverse("admin:workspaces_workspace_change", args=[self.workspace.pk]),
            {
                "name": self.workspace.name,
                "slug": "changed-slug",
                "status": self.workspace.status,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.slug, "example")
