from django.urls import path
from .views import (
    PaymentClaimSubmitView,
    PaymentConfirmView,
    PaymentListView,
    PaymentReceiptView,
    PaymentRejectView,
)

urlpatterns = [
    path(
        "workspaces/<slug:slug>/enrollments/<int:enrollment_id>/payments/",
        PaymentClaimSubmitView.as_view(),
        name="payment-claim-submit",
    ),
    path(
        "workspaces/<slug:slug>/payments/",
        PaymentListView.as_view(),
        name="payment-list",
    ),
    path(
        "workspaces/<slug:slug>/payments/<int:payment_id>/receipt/",
        PaymentReceiptView.as_view(),
        name="payment-receipt",
    ),
    path(
        "workspaces/<slug:slug>/payments/<int:payment_id>/confirm/",
        PaymentConfirmView.as_view(),
        name="payment-confirm",
    ),
    path(
        "workspaces/<slug:slug>/payments/<int:payment_id>/reject/",
        PaymentRejectView.as_view(),
        name="payment-reject",
    ),
]
