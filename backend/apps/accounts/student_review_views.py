from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .permissions import IsWorkspaceTeacher, WorkspaceSlugMixin
from .services import review_student
from .student_serializers import (
    StudentRejectSerializer,
    StudentReviewListSerializer,
    StudentReviewConflictSerializer,
    StudentReviewSerializer,
)

User = get_user_model()


class StudentListView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = StudentReviewSerializer

    @extend_schema(responses=StudentReviewListSerializer)
    def get(self, request, slug):
        queryset = User.objects.filter(
            workspace=self.workspace,
            role=User.Role.STUDENT,
        ).order_by("-date_joined", "-id")
        requested_status = request.query_params.get("status")
        if requested_status is not None:
            valid_statuses = {choice for choice, _label in User.ApprovalStatus.choices}
            if requested_status not in valid_statuses:
                raise ValidationError({"status": ["Select a valid choice."]})
            queryset = queryset.filter(approval_status=requested_status)
        paginator = api_settings.DEFAULT_PAGINATION_CLASS()
        page = paginator.paginate_queryset(queryset, request, view=self)
        results = StudentReviewSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(results.data)


class StudentApproveView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = StudentReviewSerializer

    @extend_schema(
        request=None,
        responses={200: StudentReviewSerializer, 409: StudentReviewConflictSerializer},
    )
    def post(self, request, slug, student_id):
        student = review_student(
            student_id=student_id,
            workspace=self.workspace,
            reviewer=request.user,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        serializer = StudentReviewSerializer(student, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentRejectView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = StudentRejectSerializer

    @extend_schema(
        request=StudentRejectSerializer,
        responses={200: StudentReviewSerializer, 409: StudentReviewConflictSerializer},
    )
    def post(self, request, slug, student_id):
        serializer = StudentRejectSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        student = review_student(
            student_id=student_id,
            workspace=self.workspace,
            reviewer=request.user,
            approval_status=User.ApprovalStatus.REJECTED,
            rejection_reason=serializer.validated_data["rejection_reason"].strip(),
        )
        response_serializer = StudentReviewSerializer(student, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)
