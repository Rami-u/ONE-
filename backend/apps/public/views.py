from django.db.models import Prefetch
from rest_framework import filters, generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.models import User
from apps.courses.models import Course
from apps.accounts.permissions import IsWorkspaceTeacher, WorkspaceSlugMixin
from apps.workspaces.models import Workspace
from .permissions import PublicAccess
from .serializers import (
    PublicTeacherDirectorySerializer,
    PublicTeacherProfileSerializer,
    WorkspaceBrandingSerializer,
    WorkspaceSettingsSerializer,
)


def workspace_with_teacher_queryset():
    teacher_users = User.objects.filter(role=User.Role.TEACHER).only(
        "id", "full_name", "workspace_id"
    )
    return Workspace.objects.prefetch_related(
        Prefetch("users", queryset=teacher_users, to_attr="public_teachers"),
        Prefetch(
            "courses",
            queryset=Course.objects.filter(is_published=True).order_by("-created_at", "id"),
            to_attr="published_courses",
        ),
    )


class PublicTeacherDirectoryView(generics.ListAPIView):
    permission_classes = [PublicAccess]
    serializer_class = PublicTeacherDirectorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "headline"]

    def get_queryset(self):
        return workspace_with_teacher_queryset().filter(
            status=Workspace.Status.ACTIVE,
            is_listed=True,
            users__role=User.Role.TEACHER,
        ).distinct()


class PublicTeacherProfileView(generics.RetrieveAPIView):
    permission_classes = [PublicAccess]
    serializer_class = PublicTeacherProfileSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return workspace_with_teacher_queryset().filter(
            status=Workspace.Status.ACTIVE,
            is_listed=True,
            users__role=User.Role.TEACHER,
        ).distinct()


class WorkspaceBrandingView(WorkspaceSlugMixin, APIView):
    permission_classes = [PublicAccess]
    serializer_class = WorkspaceBrandingSerializer

    @extend_schema(responses=WorkspaceBrandingSerializer)
    def get(self, request, slug):
        serializer = WorkspaceBrandingSerializer(
            self.workspace, context={"request": request}
        )
        return Response(serializer.data)


class WorkspacePublicProfileView(WorkspaceSlugMixin, APIView):
    permission_classes = [PublicAccess]
    serializer_class = PublicTeacherProfileSerializer

    @extend_schema(responses=PublicTeacherProfileSerializer)
    def get(self, request, slug):
        workspace = workspace_with_teacher_queryset().get(pk=self.workspace.pk)
        serializer = PublicTeacherProfileSerializer(
            workspace, context={"request": request}
        )
        return Response(serializer.data)


class WorkspaceSettingsView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = WorkspaceSettingsSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(responses=WorkspaceSettingsSerializer)
    def get(self, request, slug):
        serializer = WorkspaceSettingsSerializer(
            self.workspace, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(request=WorkspaceSettingsSerializer, responses=WorkspaceSettingsSerializer)
    def patch(self, request, slug):
        serializer = WorkspaceSettingsSerializer(
            self.workspace,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
