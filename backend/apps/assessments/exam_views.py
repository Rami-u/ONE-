from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsWorkspaceTeacher, WorkspaceSlugMixin

from .content_views import WorkspaceContextMixin
from .exam_serializers import (
    ExamQuestionListInputSerializer,
    ExamQuestionListOutputSerializer,
    ExamSerializer,
)
from .exam_services import (
    ExamConflictError,
    archive_exam,
    create_exam,
    publish_exam,
    replace_exam_questions,
    update_exam,
)
from .models import Exam, ExamQuestion


def exam_queryset(workspace):
    points = Coalesce(F("exam_questions__points_override"), F("exam_questions__question__points"))
    return (
        Exam.objects.filter(workspace=workspace)
        .select_related("course", "lesson")
        .annotate(
            question_count_annotated=Count("exam_questions", distinct=True),
            total_points_annotated=Coalesce(
                Sum(points),
                0,
                output_field=DecimalField(max_digits=8, decimal_places=2),
            ),
        )
        .order_by("-created_at", "id")
    )


def _conflict(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class ExamListCreateView(WorkspaceSlugMixin, WorkspaceContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = ExamSerializer

    def get_queryset(self):
        return exam_queryset(self.workspace)

    @extend_schema(
        summary="List exams",
        description="Teacher only (student view comes in a later part).",
        responses=ExamSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create an exam",
        description="Teacher only. Created as draft.",
        request=ExamSerializer,
        responses={201: ExamSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exam = create_exam(self.workspace, serializer.validated_data)
        exam = self.get_queryset().get(pk=exam.pk)
        return Response(self.get_serializer(exam).data, status=status.HTTP_201_CREATED)


class ExamDetailView(WorkspaceSlugMixin, WorkspaceContextMixin, generics.RetrieveUpdateAPIView):
    http_method_names = ["get", "patch", "head", "options"]
    lookup_url_kwarg = "exam_id"
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = ExamSerializer

    def get_queryset(self):
        return exam_queryset(self.workspace)

    @extend_schema(summary="Retrieve an exam", responses=ExamSerializer)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update exam settings",
        description="Teacher only. course cannot be changed. 409 when the freeze rules forbid the change.",
        request=ExamSerializer,
        responses=ExamSerializer,
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            exam = update_exam(instance.pk, self.workspace, serializer.validated_data)
        except ExamConflictError as exc:
            return _conflict(exc)
        exam = self.get_queryset().get(pk=exam.pk)
        return Response(self.get_serializer(exam).data)


def _questions_payload(exam):
    links = (
        ExamQuestion.objects.filter(exam=exam)
        .select_related("question")
        .order_by("position")
    )
    rows = [
        {
            "question_id": link.question_id,
            "position": link.position,
            "points_override": link.points_override,
            "points": link.points_override
            if link.points_override is not None
            else link.question.points,
            "stem": link.question.stem,
            "question_type": link.question.question_type,
        }
        for link in links
    ]
    return ExamQuestionListOutputSerializer({"questions": rows}).data


class ExamQuestionsView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]

    @extend_schema(
        summary="List the exam's questions in order",
        responses=ExamQuestionListOutputSerializer,
    )
    def get(self, request, slug, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id, workspace=self.workspace)
        return Response(_questions_payload(exam))

    @extend_schema(
        summary="Replace the exam's question list",
        description=(
            "Teacher only. Position is the array index plus 1. Questions must be approved, "
            "in this workspace and course. 409 if archived or published with attempts."
        ),
        request=ExamQuestionListInputSerializer,
        responses=ExamQuestionListOutputSerializer,
    )
    def put(self, request, slug, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id, workspace=self.workspace)
        serializer = ExamQuestionListInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            exam = replace_exam_questions(
                exam.pk, self.workspace, serializer.validated_data["questions"]
            )
        except ExamConflictError as exc:
            return _conflict(exc)
        return Response(_questions_payload(exam))


class ExamActionView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    service = None  # set by each subclass

    def post(self, request, slug, exam_id):
        get_object_or_404(Exam, pk=exam_id, workspace=self.workspace)
        try:
            self.service(exam_id, self.workspace)
        except ExamConflictError as exc:
            return _conflict(exc)
        exam = exam_queryset(self.workspace).get(pk=exam_id)
        return Response(ExamSerializer(exam, context={"workspace": self.workspace}).data)


@extend_schema(
    summary="Publish a draft exam",
    description="Teacher only. 400 if it has no questions or a question is no longer approved. 409 if not a draft.",
    request=None,
    responses=ExamSerializer,
)
class ExamPublishView(ExamActionView):
    service = staticmethod(publish_exam)


@extend_schema(
    summary="Archive a draft or published exam",
    request=None,
    responses=ExamSerializer,
)
class ExamArchiveView(ExamActionView):
    service = staticmethod(archive_exam)