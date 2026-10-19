from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login
from drf_spectacular.utils import extend_schema
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, status, throttling
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from apps.workspaces.models import Workspace

from .permissions import ActiveWorkspaceSlugMixin, IsPlatformAdmin
from .serializers import (
    PasswordResetSerializer,
    MessageSerializer,
    InvitationStatusSerializer,
    SetPasswordSerializer,
    StaffLoginSerializer,
    StaffLoginResponseSerializer,
    TeacherCreateSerializer,
    TeacherCreatedSerializer,
    TeacherListResponseSerializer,
    TeacherSerializer,
    WorkspaceAdminSerializer,
)
from .services import (
    create_teacher_with_workspace,
    resend_teacher_invitation,
    start_staff_password_reset,
)
from .tokens import staff_password_token

User = get_user_model()


class StaffLoginThrottle(throttling.AnonRateThrottle):
    scope = "staff_login"


class StaffPasswordResetThrottle(throttling.AnonRateThrottle):
    scope = "staff_password_reset"


class AdminTeacherListCreateView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_teachers_list", responses=TeacherListResponseSerializer
    )
    def get(self, request):
        queryset = User.objects.filter(role=User.Role.TEACHER).select_related("workspace")
        paginator = api_settings.DEFAULT_PAGINATION_CLASS()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(TeacherSerializer(page, many=True).data)

    @extend_schema(
        operation_id="admin_teachers_create",
        request=TeacherCreateSerializer,
        responses={201: TeacherCreatedSerializer},
    )
    def post(self, request):
        serializer = TeacherCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        teacher, workspace, delivery = create_teacher_with_workspace(
            full_name=serializer.validated_data["full_name"],
            email=serializer.validated_data["email"],
            workspace_name=serializer.validated_data["workspace_name"],
            slug=serializer.validated_data["slug"],
        )
        return Response(
            {
                "teacher_id": teacher.pk,
                "workspace_id": workspace.pk,
                "slug": workspace.slug,
                "invitation_sent": delivery["sent"],
            },
            status=status.HTTP_201_CREATED,
        )


class AdminTeacherDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get_object(self, pk):
        try:
            return User.objects.select_related("workspace").get(
                pk=pk, role=User.Role.TEACHER
            )
        except User.DoesNotExist as exc:
            raise NotFound("Teacher not found.") from exc

    @extend_schema(operation_id="admin_teacher_retrieve", responses=TeacherSerializer)
    def get(self, request, pk):
        return Response(TeacherSerializer(self.get_object(pk)).data)


class AdminTeacherResendInviteView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_teacher_resend_invite",
        request=None,
        responses={200: InvitationStatusSerializer},
    )
    def post(self, request, pk):
        try:
            teacher = User.objects.get(pk=pk, role=User.Role.TEACHER)
        except User.DoesNotExist as exc:
            raise NotFound("Teacher not found.") from exc
        resend_teacher_invitation(teacher)
        return Response({"invitation_sent": True}, status=status.HTTP_200_OK)


class AdminWorkspaceListView(generics.ListAPIView):
    permission_classes = [IsPlatformAdmin]
    serializer_class = WorkspaceAdminSerializer
    queryset = Workspace.objects.all()


class AdminWorkspaceDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get_object(self, pk):
        try:
            return Workspace.objects.get(pk=pk)
        except Workspace.DoesNotExist as exc:
            raise NotFound("Workspace not found.") from exc

    @extend_schema(operation_id="admin_workspace_retrieve", responses=WorkspaceAdminSerializer)
    def get(self, request, pk):
        return Response(WorkspaceAdminSerializer(self.get_object(pk)).data)


class AdminWorkspaceSuspendView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_workspace_suspend",
        request=None,
        responses=WorkspaceAdminSerializer,
    )
    def post(self, request, pk):
        try:
            workspace = Workspace.objects.get(pk=pk)
        except Workspace.DoesNotExist as exc:
            raise NotFound("Workspace not found.") from exc
        workspace.status = Workspace.Status.SUSPENDED
        workspace.save(update_fields=["status"])
        return Response(WorkspaceAdminSerializer(workspace).data)


class AdminWorkspaceActivateView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_workspace_activate",
        request=None,
        responses=WorkspaceAdminSerializer,
    )
    def post(self, request, pk):
        try:
            workspace = Workspace.objects.get(pk=pk)
        except Workspace.DoesNotExist as exc:
            raise NotFound("Workspace not found.") from exc
        workspace.status = Workspace.Status.ACTIVE
        workspace.save(update_fields=["status"])
        return Response(WorkspaceAdminSerializer(workspace).data)


class StaffLoginView(ActiveWorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [StaffLoginThrottle]

    @extend_schema(
        operation_id="staff_login",
        request=StaffLoginSerializer,
        responses={200: StaffLoginResponseSerializer},
    )
    def post(self, request, slug):
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request._request,
            username=serializer.validated_data["login_key"],
            password=serializer.validated_data["password"],
        )
        if (
            user is None
            or user.role != User.Role.TEACHER
            or user.workspace_id != self.workspace.pk
            or not user.is_active
            or user.approval_status != User.ApprovalStatus.APPROVED
        ):
            return Response(
                {"detail": "Invalid login credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request._request, user)
        return Response({"id": user.pk, "full_name": user.full_name})


class StaffSetPasswordView(ActiveWorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        operation_id="staff_set_password",
        request=SetPasswordSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request, slug):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = User.objects.get(
                pk=user_id, role=User.Role.TEACHER, workspace=self.workspace
            )
        except (ValueError, TypeError, OverflowError, UnicodeError, User.DoesNotExist) as exc:
            raise NotFound("Invalid or expired password link.") from exc
        if not staff_password_token.check_token(user, serializer.validated_data["token"]):
            return Response(
                {"detail": "Invalid or expired password link."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password has been set."})


class StaffPasswordResetView(ActiveWorkspaceSlugMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [StaffPasswordResetThrottle]

    @extend_schema(
        operation_id="staff_password_reset_start",
        request=PasswordResetSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request, slug):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        normalized_email = User.objects.normalize_email_address(
            serializer.validated_data["email"]
        )
        user = User.objects.filter(
            email=normalized_email,
            role=User.Role.TEACHER,
            workspace=self.workspace,
            is_active=True,
        ).first()
        if user is not None:
            start_staff_password_reset(user)
        return Response({"detail": "If the account exists, a reset link has been sent."})
