from django.urls import path
from .views import CourseDetailView, CourseListCreateView

urlpatterns = [
    path(
        "workspaces/<slug:slug>/courses/",
        CourseListCreateView.as_view(),
        name="course-list-create",
    ),
    path(
        "workspaces/<slug:slug>/courses/<int:course_id>/",
        CourseDetailView.as_view(),
        name="course-detail",
    ),
]
