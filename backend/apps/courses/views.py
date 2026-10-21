from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsWorkspaceTeacher, WorkspaceSlugMixin
from apps.enrollments.models import CourseEnrollment
from .models import Course
from .permissions import IsWorkspaceTeacherOrApprovedStudent
from .serializers import CourseCreateUpdateSerializer, CourseSerializer


class CourseListCreateView(WorkspaceSlugMixin, generics.ListCreateAPIView):
    permission_classes = [IsWorkspaceTeacherOrApprovedStudent]
    serializer_class = CourseSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.filter(workspace=self.workspace)
        if user.role == User.Role.STUDENT:
            queryset = queryset.filter(is_published=True).prefetch_related(
                Prefetch(
                    "enrollments",
                    queryset=CourseEnrollment.objects.filter(student=user),
                    to_attr="user_enrollment",
                )
            )
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CourseCreateUpdateSerializer
        return CourseSerializer

    @extend_schema(
        summary="List workspace courses",
        description="Students see only published courses with their enrollment status; teachers see all courses.",
        responses=CourseSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create a course",
        description="Only the workspace teacher can create courses. Course workspace is set automatically.",
        request=CourseCreateUpdateSerializer,
        responses={201: CourseSerializer},
    )
    def post(self, request, *args, **kwargs):
        if not IsWorkspaceTeacher().has_permission(request, self):
            raise PermissionDenied("Only the workspace teacher can create courses.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = serializer.save(workspace=self.workspace)
        output_serializer = CourseSerializer(course, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class CourseDetailView(WorkspaceSlugMixin, generics.RetrieveUpdateAPIView):
    http_method_names = ["get", "patch", "head", "options"]
    lookup_url_kwarg = "course_id"
    permission_classes = [IsWorkspaceTeacherOrApprovedStudent]
    serializer_class = CourseSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.filter(workspace=self.workspace)
        if user.role == User.Role.STUDENT:
            queryset = queryset.filter(is_published=True).prefetch_related(
                Prefetch(
                    "enrollments",
                    queryset=CourseEnrollment.objects.filter(student=user),
                    to_attr="user_enrollment",
                )
            )
        return queryset

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CourseCreateUpdateSerializer
        return CourseSerializer

    @extend_schema(
        summary="Retrieve a course",
        description="Teachers can retrieve any course in the workspace; students can only retrieve published courses.",
        responses=CourseSerializer,
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update a course",
        description="Only the workspace teacher can update a course.",
        request=CourseCreateUpdateSerializer,
        responses=CourseSerializer,
    )
    def patch(self, request, *args, **kwargs):
        if not IsWorkspaceTeacher().has_permission(request, self):
            raise PermissionDenied("Only the workspace teacher can update courses.")
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        course = serializer.save()
        output_serializer = CourseSerializer(course, context={"request": request})
        return Response(output_serializer.data)
