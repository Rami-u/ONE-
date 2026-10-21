from django.conf import settings
from django.test import SimpleTestCase

from config.settings import env


class SessionAndCSRFSettingsTests(SimpleTestCase):
    def test_session_and_csrf_cookie_settings(self):
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertIs(settings.SESSION_COOKIE_HTTPONLY, True)
        self.assertEqual(
            settings.SESSION_COOKIE_SECURE,
            env.bool("DJANGO_SESSION_COOKIE_SECURE", default=True),
        )
        self.assertIs(settings.CSRF_COOKIE_HTTPONLY, False)
        self.assertEqual(
            settings.CSRF_TRUSTED_ORIGINS,
            env.list(
                "CSRF_TRUSTED_ORIGINS", default=["https://*.edunova.com"]
            ),
        )
        self.assertIsNone(getattr(settings, "SESSION_COOKIE_DOMAIN", None))
        self.assertIsNone(getattr(settings, "CSRF_COOKIE_DOMAIN", None))
