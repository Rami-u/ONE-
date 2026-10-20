from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import WorkspaceSlugMixin
from .views import ClientIPRateThrottle


class StudentRegisterThrottle(ClientIPRateThrottle):
    scope = "student_register"


class StudentLoginThrottle(ClientIPRateThrottle):
    scope = "student_login"


class StudentPasswordResetThrottle(ClientIPRateThrottle):
    scope = "student_password_reset"


class StudentPasswordResetConfirmThrottle(ClientIPRateThrottle):
    scope = "student_password_reset_confirm"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class StudentCSRFCookieView(WorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = None

    @extend_schema(request=None, responses={204: None})
    def get(self, request, slug):
        return Response(status=status.HTTP_204_NO_CONTENT)
