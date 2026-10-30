from django.db.models import Count, DecimalField, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsApprovedStudent, IsWorkspaceTeacher, WorkspaceSlugMixin
from apps.enrollments.models import CourseEnrollment

from .content_views import WorkspaceContextMixin
from .exam_serializers import (
    ExamQuestionListInputSerializer,
    ExamQuestionListOutputSerializer,
    ExamSerializer,
    StudentExamSerializer,
)
from .exam_services import (
    ExamConflictError,
    archive_exam,
    create_exam,
    publish_exam,
    replace_exam_questions,
    update_exam,
)
from .models import Exam, ExamAttempt, ExamQuestion


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


def student_exam_queryset(workspace, student):
    """Published exams in courses where the student has an active enrollment."""
    active_courses = CourseEnrollment.objects.filter(
        workspace=workspace,
        student=student,
        status=CourseEnrollment.Status.ACTIVE,
    ).values("course_id")
    attempts_used = (
        ExamAttempt.objects.filter(exam=OuterRef("pk"), student=student)
        .order_by()
        .values("exam")
        .annotate(c=Count("pk"))
        .values("c")
    )
    in_progress = (
        ExamAttempt.objects.filter(
            exam=OuterRef("pk"),
            student=student,
            status=ExamAttempt.Status.IN_PROGRESS,
        )
        .order_by("-attempt_number")
        .values("pk")[:1]
    )
    return (
        exam_queryset(workspace)
        .filter(status=Exam.Status.PUBLISHED, course_id__in=active_courses)
        .annotate(
            attempts_used_annotated=Coalesce(
                Subquery(attempts_used, output_field=IntegerField()), 0
            ),
            in_progress_attempt_id_annotated=Subquery(in_progress, output_field=IntegerField()),
        )
    )


def _conflict(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class ExamRoleMixin:
    """Teacher gets the full exam; an approved student gets the limited card."""

    def get_permissions(self):
        if self.request.method in {"POST", "PATCH"}:
            return [IsWorkspaceTeacher()]
        user = self.request.user
        if user.is_authenticated and user.role == User.Role.STUDENT:
            return [IsApprovedStudent()]
        return [IsWorkspaceTeacher()]

    def is_student(self):
        return self.request.user.role == User.Role.STUDENT

    def get_queryset(self):
        if self.is_student():
            return student_exam_queryset(self.workspace, self.request.user)
        return exam_queryset(self.workspace)

    def get_serializer_class(self):
        if self.request.method == "GET" and self.is_student():
            return StudentExamSerializer
        return ExamSerializer


class ExamListCreateView(
    WorkspaceSlugMixin, WorkspaceContextMixin, ExamRoleMixin, generics.ListCreateAPIView
):
    permission_classes = [IsWorkspaceTeacher]

    @extend_schema(
        summary="List exams",
        description=(
            "Teacher: all exams. Approved student: only published exams in courses with an "
            "active enrollment, without questions or passing_score."
        ),
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
        exam = exam_queryset(self.workspace).get(pk=exam.pk)
        return Response(self.get_serializer(exam).data, status=status.HTTP_201_CREATED)


class ExamDetailView(
    WorkspaceSlugMixin, WorkspaceContextMixin, ExamRoleMixin, generics.RetrieveUpdateAPIView
):
    http_method_names = ["get", "patch", "head", "options"]
    lookup_url_kwarg = "exam_id"
    permission_classes = [IsWorkspaceTeacher]

    @extend_schema(
        summary="Retrieve an exam",
        description="Students get the limited card, and 404 if the exam is not available to them.",
        responses=ExamSerializer,
    )
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
        exam = exam_queryset(self.workspace).get(pk=exam.pk)
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