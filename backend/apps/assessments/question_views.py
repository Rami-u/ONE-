from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsWorkspaceTeacher, WorkspaceSlugMixin

from .content_views import WorkspaceContextMixin
from .models import Question
from .question_serializers import QuestionSerializer
from .question_services import (
    QuestionConflictError,
    approve_question,
    archive_question,
    create_question,
    reject_question,
    update_question,
)

INT_FILTERS = {"course": "course_id", "lesson": "lesson_id", "topic": "question_topics__topic_id"}
CHOICE_FILTERS = {
    "status": Question.Status.values,
    "question_type": Question.QuestionType.values,
    "difficulty": Question.Difficulty.values,
    "source_type": Question.SourceType.values,
}
FILTER_PARAMETERS = [
    OpenApiParameter(name)
    for name in (*INT_FILTERS, *CHOICE_FILTERS, "search")
]


def _conflict(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class QuestionListCreateView(WorkspaceSlugMixin, WorkspaceContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = QuestionSerializer

    def get_queryset(self):
        queryset = Question.objects.filter(workspace=self.workspace).prefetch_related("question_topics__topic")
        params = self.request.query_params
        for name, lookup in INT_FILTERS.items():
            value = params.get(name)
            if value is not None:
                if not value.isdigit():
                    raise serializers.ValidationError({name: ["Must be an integer id."]})
                queryset = queryset.filter(**{lookup: int(value)})
        for name, allowed in CHOICE_FILTERS.items():
            value = params.get(name)
            if value is not None:
                if value not in allowed:
                    raise serializers.ValidationError({name: [f"Must be one of: {', '.join(allowed)}."]})
                queryset = queryset.filter(**{name: value})
        search = params.get("search")
        if search:
            queryset = queryset.filter(Q(stem__icontains=search))
        return queryset.distinct()

    @extend_schema(
        summary="List questions",
        description="Teacher only. Filters: status, question_type, difficulty, source_type, course, lesson, topic, search.",
        parameters=FILTER_PARAMETERS,
        responses=QuestionSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create a question",
        description="Teacher only. Created as approved unless status=draft is sent.",
        request=QuestionSerializer,
        responses={201: QuestionSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = create_question(self.workspace, serializer.validated_data)
        return Response(self.get_serializer(question).data, status=status.HTTP_201_CREATED)


class QuestionDetailView(WorkspaceSlugMixin, WorkspaceContextMixin, generics.RetrieveUpdateAPIView):
    http_method_names = ["get", "patch", "head", "options"]
    lookup_url_kwarg = "question_id"
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = QuestionSerializer

    def get_queryset(self):
        return Question.objects.filter(workspace=self.workspace).prefetch_related("question_topics__topic")

    @extend_schema(summary="Retrieve a question", responses=QuestionSerializer)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update a question",
        description="Teacher only. question_type and status cannot be changed here. 409 if archived or frozen by attempts.",
        request=QuestionSerializer,
        responses=QuestionSerializer,
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            question = update_question(instance.pk, self.workspace, serializer.validated_data)
        except QuestionConflictError as exc:
            return _conflict(exc)
        question = self.get_queryset().get(pk=question.pk)
        return Response(self.get_serializer(question).data)


class QuestionActionView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    service = None  # set by each subclass

    def post(self, request, slug, question_id):
        get_object_or_404(Question, pk=question_id, workspace=self.workspace)
        try:
            question = self.service(question_id, self.workspace, request.user)
        except QuestionConflictError as exc:
            return _conflict(exc)
        question = Question.objects.prefetch_related("question_topics__topic").get(pk=question.pk)
        return Response(QuestionSerializer(question, context={"workspace": self.workspace}).data)


@extend_schema(summary="Approve a draft question", request=None, responses=QuestionSerializer)
class QuestionApproveView(QuestionActionView):
    service = staticmethod(approve_question)


@extend_schema(summary="Reject a draft question", request=None, responses=QuestionSerializer)
class QuestionRejectView(QuestionActionView):
    service = staticmethod(reject_question)


@extend_schema(summary="Archive a question", request=None, responses=QuestionSerializer)
class QuestionArchiveView(QuestionActionView):
    service = staticmethod(archive_question)