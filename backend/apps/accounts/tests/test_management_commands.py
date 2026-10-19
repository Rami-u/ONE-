from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User


class CreatesuperuserCommandTests(TestCase):
    def test_createsuperuser_accepts_admin_login_key_non_interactively(self):
        email = "command-admin@example.com"

        call_command(
            "createsuperuser",
            login_key=f"admin:{email}",
            email=email,
            full_name="Command Admin",
            interactive=False,
            stdout=StringIO(),
        )

        user = User.objects.get(email=email)
        self.assertEqual(user.login_key, f"admin:{email}")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertIsNone(user.workspace)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
