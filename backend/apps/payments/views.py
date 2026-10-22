from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsApprovedStudent, IsWorkspaceTeacher, WorkspaceSlugMixin
from apps.enrollments.models import CourseEnrollment
from .models import PaymentSubmission
from .permissions import CanViewReceiptPermission
from .serializers import (
    PaymentClaimCreateSerializer,
    PaymentRejectSerializer,
    PaymentSubmissionSerializer,
)
from .services import (
    PaymentConflictError,
    confirm_payment,
    reject_payment,
    submit_payment_claim,
)


class PaymentClaimSubmitView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsApprovedStudent]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = PaymentClaimCreateSerializer

    @extend_schema(
        summary="Submit payment claim",
        description=(
            "Submit a manual payment claim for an enrollment. "
            "Amount is derived strictly by the server from price_at_enrollment. "
            "Optional receipt file (JPEG, PNG, or PDF, at most 5 MB)."
        ),
        request=PaymentClaimCreateSerializer,
        responses={201: PaymentSubmissionSerializer},
    )
    def post(self, request, slug, enrollment_id):
        enrollment = CourseEnrollment.objects.filter(
            workspace=self.workspace,
            student=request.user,
        ).filter(pk=enrollment_id).first()
        if enrollment is None:
            raise NotFound("Enrollment not found.")

        serializer = PaymentClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submission = submit_payment_claim(
                enrollment=enrollment,
                student=request.user,
                method=serializer.validated_data["method"],
                note=serializer.validated_data.get("note"),
                receipt_image=serializer.validated_data.get("receipt_image"),
            )
        except PaymentConflictError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        output_serializer = PaymentSubmissionSerializer(submission)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class PaymentListView(WorkspaceSlugMixin, generics.ListAPIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = PaymentSubmissionSerializer

    def get_queryset(self):
        queryset = PaymentSubmission.objects.filter(
            workspace=self.workspace
        ).select_related("enrollment__course", "submitted_by", "reviewed_by")
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    @extend_schema(
        summary="List workspace payment submissions",
        description="Workspace teacher can list payment submissions, filterable by status.",
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=["submitted", "confirmed", "rejected"],
                description="Filter payments by review status.",
            ),
        ],
        responses=PaymentSubmissionSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PaymentReceiptView(WorkspaceSlugMixin, APIView):
    permission_classes = [CanViewReceiptPermission]

    @extend_schema(
        summary="View payment receipt",
        description=(
            "Authorized endpoint to download/view a payment receipt. "
            "Accessible only to the workspace teacher or the student who submitted the claim."
        ),
        responses={
            (200, "application/pdf"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="Receipt PDF document",
            ),
            (200, "image/png"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="Receipt PNG image",
            ),
            (200, "image/jpeg"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="Receipt JPEG image",
            ),
        },
    )
    def get(self, request, slug, payment_id):
        user = request.user
        if not (user and user.is_authenticated):
            raise PermissionDenied("Authentication required.")

        payment = PaymentSubmission.objects.filter(
            workspace=self.workspace
        ).filter(pk=payment_id).first()
        if payment is None:
            raise NotFound("Payment not found.")

        is_teacher = (
            user.role == User.Role.TEACHER
            and user.approval_status == User.ApprovalStatus.APPROVED
            and user.workspace_id == self.workspace.pk
        )
        is_owner = (
            user.role == User.Role.STUDENT
            and user.approval_status == User.ApprovalStatus.APPROVED
            and user.workspace_id == self.workspace.pk
            and payment.submitted_by_id == user.pk
        )

        if not (is_teacher or is_owner):
            raise PermissionDenied("You do not have permission to view this receipt.")

        if not payment.receipt_image:
            raise NotFound("Receipt not found.")

        try:
            file_handle = payment.receipt_image.open("rb")
        except (FileNotFoundError, OSError) as exc:
            raise NotFound("Receipt file not found on disk.") from exc

        ext = (
            payment.receipt_image.name.rsplit(".", 1)[-1].lower()
            if "." in payment.receipt_image.name
            else ""
        )
        content_type_map = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
        }

        if ext in content_type_map:
            content_type = content_type_map[ext]
            disposition = "inline"
        else:
            content_type = "application/octet-stream"
            disposition = "attachment"

        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = disposition
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class PaymentConfirmView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = PaymentSubmissionSerializer

    @extend_schema(
        summary="Confirm payment claim",
        description="Teacher confirms a submitted payment claim. Enrollment is activated in the same transaction.",
        request=None,
        responses={200: PaymentSubmissionSerializer},
    )
    def post(self, request, slug, payment_id):
        try:
            payment = confirm_payment(payment_id, self.workspace, request.user)
        except PaymentConflictError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        if payment is None:
            raise NotFound("Payment not found.")

        serializer = PaymentSubmissionSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaymentRejectView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceTeacher]
    serializer_class = PaymentRejectSerializer

    @extend_schema(
        summary="Reject payment claim",
        description="Teacher rejects a submitted payment claim with a reason. Enrollment stays pending_payment.",
        request=PaymentRejectSerializer,
        responses={200: PaymentSubmissionSerializer},
    )
    def post(self, request, slug, payment_id):
        serializer = PaymentRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = reject_payment(
                payment_id,
                self.workspace,
                request.user,
                serializer.validated_data["rejection_reason"],
            )
        except PaymentConflictError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        if payment is None:
            raise NotFound("Payment not found.")

        output_serializer = PaymentSubmissionSerializer(payment)
        return Response(output_serializer.data, status=status.HTTP_200_OK)
