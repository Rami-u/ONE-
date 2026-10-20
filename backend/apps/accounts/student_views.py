import logging
import re

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .identity import build_login_key
from .models import User
from .permissions import IsWorkspaceMember, WorkspaceSlugMixin
from .serializers import MessageSerializer
from .student_serializers import (
    StudentLoginResponseSerializer,
    StudentLoginStateErrorSerializer,
    StudentLoginSerializer,
    StudentMeSerializer,
    StudentMessageSerializer,
    StudentPasswordResetConfirmSerializer,
    StudentPasswordResetSerializer,
    StudentRegisterSerializer,
    StudentRegistrationResponseSerializer,
)
from .tokens import staff_password_token
from .views import ClientIPRateThrottle

logger = logging.getLogger(__name__)


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


class StudentRegisterView(WorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [StudentRegisterThrottle]
    serializer_class = StudentRegisterSerializer

    @extend_schema(
        request=StudentRegisterSerializer,
        responses={201: StudentRegistrationResponseSerializer},
    )
    def post(self, request, slug):
        serializer = StudentRegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        login_key = build_login_key(self.workspace.pk, email)
        if User.objects.filter(login_key=login_key).exists():
            return Response(
                {"email": ["An account with this email already exists in this workspace."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                User.objects.create_user(
                    email=email,
                    password=serializer.validated_data["password"],
                    full_name=serializer.validated_data["full_name"],
                    workspace=self.workspace,
                    role=User.Role.STUDENT,
                    approval_status=User.ApprovalStatus.PENDING,
                )
        except IntegrityError:
            if User.objects.filter(login_key=login_key).exists():
                return Response(
                    {"email": ["An account with this email already exists in this workspace."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return Response(
            {
                "message": "Registration received. Your account is waiting for the teacher's approval.",
                "approval_status": User.ApprovalStatus.PENDING,
            },
            status=status.HTTP_201_CREATED,
        )


class StudentLoginView(WorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [StudentLoginThrottle]
    serializer_class = StudentLoginSerializer

    @extend_schema(
        request=StudentLoginSerializer,
        responses={
            200: StudentLoginResponseSerializer,
            400: StudentMessageSerializer,
            403: StudentLoginStateErrorSerializer,
        },
    )
    def post(self, request, slug):
        serializer = StudentLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        login_key = build_login_key(self.workspace.pk, serializer.validated_data["email"])
        user = authenticate(
            request=request._request,
            username=login_key,
            password=serializer.validated_data["password"],
        )
        if (
            user is None
            or user.role != User.Role.STUDENT
            or user.workspace_id != self.workspace.pk
            or not user.is_active
        ):
            return Response(
                {"detail": "Invalid login credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.approval_status == User.ApprovalStatus.PENDING:
            return Response(
                {
                    "code": "pending_approval",
                    "message": "Your account is waiting for the teacher's approval.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.approval_status == User.ApprovalStatus.REJECTED:
            return Response(
                {
                    "code": "account_rejected",
                    "message": "Your account was rejected.",
                    "rejection_reason": user.rejection_reason,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        login(request._request, user)
        return Response(StudentMeSerializer(user, context={"request": request}).data)


class StudentLogoutView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceMember]
    serializer_class = StudentMessageSerializer

    @extend_schema(request=None, responses={204: None})
    def post(self, request, slug):
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentMeView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceMember]
    serializer_class = StudentMeSerializer

    @extend_schema(responses=StudentMeSerializer)
    def get(self, request, slug):
        return Response(StudentMeSerializer(request.user, context={"request": request}).data)


def _student_reset_link(user, uid, token):
    base_domain = settings.PLATFORM_BASE_DOMAIN.strip(".")
    return (
        f"{settings.PLATFORM_URL_SCHEME}://{user.workspace.slug}.{base_domain}"
        f"/reset-password/?uid={uid}&token={token}"
    )


def _safe_email_exception_message(exc, *, token=None, link=None):
    message = re.sub(r"https?://\S+", "[redacted link]", str(exc))
    for secret in (token, link):
        if secret:
            message = message.replace(secret, "[redacted]")
    return message


def _send_student_reset_email(user, uid, token):
    link = _student_reset_link(user, uid, token)
    timeout_days = (settings.PASSWORD_RESET_TIMEOUT + 86_399) // 86_400
    day_label = "day" if timeout_days == 1 else "days"
    try:
        send_mail(
            "Reset your student password",
            f"Use this link to set or reset your password. It expires within {timeout_days} {day_label}:\n\n{link}",
            None,
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning(
            "Student password reset email failed user_id=%s exception_class=%s exception_message=%s",
            user.pk,
            type(exc).__name__,
            _safe_email_exception_message(exc, token=token, link=link),
        )


class StudentPasswordResetView(WorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [StudentPasswordResetThrottle]
    serializer_class = StudentPasswordResetSerializer

    @extend_schema(
        request=StudentPasswordResetSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request, slug):
        serializer = StudentPasswordResetSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        login_key = build_login_key(self.workspace.pk, serializer.validated_data["email"])
        user = User.objects.filter(
            login_key=login_key,
            workspace=self.workspace,
            role=User.Role.STUDENT,
            is_active=True,
        ).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = staff_password_token.make_token(user)
            transaction.on_commit(
                lambda user=user, uid=uid, token=token: _send_student_reset_email(
                    user, uid, token
                )
            )
        return Response({"detail": "If the account exists, a reset link has been sent."})


class StudentPasswordResetConfirmView(WorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [StudentPasswordResetConfirmThrottle]
    serializer_class = StudentPasswordResetConfirmSerializer

    @extend_schema(
        request=StudentPasswordResetConfirmSerializer,
        responses={200: MessageSerializer, 400: MessageSerializer},
    )
    def post(self, request, slug):
        serializer = StudentPasswordResetConfirmSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            with transaction.atomic():
                user = User.objects.select_for_update().filter(
                    workspace=self.workspace,
                    role=User.Role.STUDENT,
                    is_active=True,
                ).get(pk=user_id)
                if not staff_password_token.check_token(
                    user, serializer.validated_data["token"]
                ):
                    raise ValueError("Invalid token")
                try:
                    validate_password(serializer.validated_data["new_password"], user=user)
                except DjangoValidationError as exc:
                    raise serializers.ValidationError({"new_password": exc.messages}) from exc
                user.set_password(serializer.validated_data["new_password"])
                user.save(update_fields=["password"])
        except (ValueError, TypeError, OverflowError, UnicodeError, User.DoesNotExist):
            return Response(
                {"detail": "Invalid or expired password link."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Password has been set."})
