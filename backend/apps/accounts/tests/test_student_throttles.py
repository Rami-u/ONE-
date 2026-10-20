from types import SimpleNamespace

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.accounts.student_views import (
    StudentLoginThrottle,
    StudentPasswordResetConfirmThrottle,
    StudentPasswordResetThrottle,
    StudentRegisterThrottle,
)


class StudentThrottleTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = SimpleNamespace()

    def test_each_student_scope_allows_its_limit_then_throttles(self):
        cases = (
            (StudentRegisterThrottle, 10),
            (StudentLoginThrottle, 5),
            (StudentPasswordResetThrottle, 3),
            (StudentPasswordResetConfirmThrottle, 5),
        )
        for throttle_class, limit in cases:
            with self.subTest(scope=throttle_class.scope):
                cache.clear()
                throttle = throttle_class()
                request = self.factory.post("/", REMOTE_ADDR="198.51.100.20")
                for _ in range(limit):
                    self.assertTrue(throttle.allow_request(request, self.view))
                self.assertFalse(throttle.allow_request(request, self.view))
