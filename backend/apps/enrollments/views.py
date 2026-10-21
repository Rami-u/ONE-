from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsApprovedStudent, WorkspaceSlugMixin
from apps.courses.models import Course
from .models import CourseEnrollment
from .serializers import CourseEnrollResponseSerializer, StudentEnrollmentListSerializer
from .services import enroll_student_in_course


class CourseEnrollView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsApprovedStudent]
    serializer_class = CourseEnrollResponseSerializer

    @extend_schema(
        summary="Enroll in a course",
        description=(
            "Approved students can enroll in a published course. "
            "Free courses become active immediately; paid courses become pending_payment. "
            "Enrolling twice returns the existing enrollment."
        ),
        request=None,
        responses={200: CourseEnrollResponseSerializer, 201: CourseEnrollResponseSerializer},
    )
    def post(self, request, slug, course_id):
        course = Course.objects.filter(workspace=self.workspace, is_published=True).filter(pk=course_id).first()
        if course is None:
            raise NotFound("Course not found.")

        enrollment, created = enroll_student_in_course(request.user, course, self.workspace)
        serializer = CourseEnrollResponseSerializer({
            "enrollment_id": enrollment.id,
            "status": enrollment.status,
            "price": enrollment.price_at_enrollment,
            "payment_instructions": self.workspace.payment_instructions,
        })
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=http_status)


class StudentEnrollmentMeView(WorkspaceSlugMixin, generics.ListAPIView):
    permission_classes = [IsApprovedStudent]
    serializer_class = StudentEnrollmentListSerializer

    def get_queryset(self):
        return CourseEnrollment.objects.filter(
            workspace=self.workspace,
            student=self.request.user,
        ).select_related("course")

    @extend_schema(
        summary="List student's enrollments",
        description="Returns the approved student's enrollments and their statuses in this workspace.",
        responses=StudentEnrollmentListSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
