from django.urls import path

from .question_views import (
    QuestionApproveView,
    QuestionArchiveView,
    QuestionDetailView,
    QuestionListCreateView,
    QuestionRejectView,
)

urlpatterns = [
    path("workspaces/<slug:slug>/questions/", QuestionListCreateView.as_view(), name="question-list-create"),
    path("workspaces/<slug:slug>/questions/<int:question_id>/", QuestionDetailView.as_view(), name="question-detail"),
    path("workspaces/<slug:slug>/questions/<int:question_id>/approve/", QuestionApproveView.as_view(), name="question-approve"),
    path("workspaces/<slug:slug>/questions/<int:question_id>/reject/", QuestionRejectView.as_view(), name="question-reject"),
    path("workspaces/<slug:slug>/questions/<int:question_id>/archive/", QuestionArchiveView.as_view(), name="question-archive"),
]