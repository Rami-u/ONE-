from django.urls import path

from .attempt_views import AttemptDetailView, StartAttemptView, SubmitAttemptView

urlpatterns = [
    path(
        "workspaces/<slug:slug>/exams/<int:exam_id>/attempts/start/",
        StartAttemptView.as_view(),
        name="exam-attempt-start",
    ),
    path(
        "workspaces/<slug:slug>/attempts/<int:attempt_id>/submit/",
        SubmitAttemptView.as_view(),
        name="exam-attempt-submit",
    ),
    path(
        "workspaces/<slug:slug>/attempts/<int:attempt_id>/",
        AttemptDetailView.as_view(),
        name="exam-attempt-detail",
    ),
]
