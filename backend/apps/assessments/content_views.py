from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.response import Response

from apps.accounts.permissions import IsWorkspaceTeacher, WorkspaceSlugMixin

from .content_serializers import TopicSerializer
from .content_services import create_topic, update_topic
from .models import Topic


class WorkspaceContextMixin:
    # WorkspaceSlugMixin sets self.workspace but does not add it to the
    # serializer context, so relation querysets would not be scoped.
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace"] = self.workspace
        return context


class TopicListCreateView(WorkspaceSlugMixin, WorkspaceContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = TopicSerializer

    def get_queryset(self):
        queryset = Topic.objects.filter(workspace=self.workspace).select_related("course")
        course = self.request.query_params.get("course")
        if course is not None:
            if not course.isdigit():
                raise serializers.ValidationError({"course": ["Must be an integer id."]})
            queryset = queryset.filter(course_id=int(course))
        return queryset

    @extend_schema(
        summary="List workspace topics",
        description="Teacher only. Optionally filter by course id.",
        parameters=[OpenApiParameter("course", OpenApiTypes.INT, description="Filter by course id")],
        responses=TopicSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create a topic",
        description="Teacher only. The slug is derived from the name when omitted.",
        request=TopicSerializer,
        responses={201: TopicSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = create_topic(
            self.workspace,
            name=serializer.validated_data["name"],
            slug=serializer.validated_data.get("slug"),
            course=serializer.validated_data.get("course"),
        )
        return Response(self.get_serializer(topic).data, status=status.HTTP_201_CREATED)


class TopicDetailView(WorkspaceSlugMixin, WorkspaceContextMixin, generics.RetrieveUpdateAPIView):
    http_method_names = ["get", "patch", "head", "options"]
    lookup_url_kwarg = "topic_id"
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = TopicSerializer

    def get_queryset(self):
        return Topic.objects.filter(workspace=self.workspace).select_related("course")

    @extend_schema(
        summary="Retrieve a topic",
        responses=TopicSerializer,
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update a topic",
        description="Teacher only. Partial update of name, slug or course.",
        request=TopicSerializer,
        responses=TopicSerializer,
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        topic = update_topic(instance, serializer.validated_data)
        return Response(self.get_serializer(topic).data)