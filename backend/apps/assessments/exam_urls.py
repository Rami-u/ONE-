from django.urls import path

from .exam_views import (
    ExamArchiveView,
    ExamDetailView,
    ExamListCreateView,
    ExamPublishView,
    ExamQuestionsView,
)

urlpatterns = [
    path("workspaces/<slug:slug>/exams/", ExamListCreateView.as_view(), name="exam-list-create"),
    path("workspaces/<slug:slug>/exams/<int:exam_id>/", ExamDetailView.as_view(), name="exam-detail"),
    path(
        "workspaces/<slug:slug>/exams/<int:exam_id>/questions/",
        ExamQuestionsView.as_view(),
        name="exam-questions",
    ),
    path(
        "workspaces/<slug:slug>/exams/<int:exam_id>/publish/",
        ExamPublishView.as_view(),
        name="exam-publish",
    ),
    path(
        "workspaces/<slug:slug>/exams/<int:exam_id>/archive/",
        ExamArchiveView.as_view(),
        name="exam-archive",
    ),
]