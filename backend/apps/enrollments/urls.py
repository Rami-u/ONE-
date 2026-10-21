from django.urls import path
from .views import CourseEnrollView, StudentEnrollmentMeView

urlpatterns = [
    path(
        "workspaces/<slug:slug>/courses/<int:course_id>/enroll/",
        CourseEnrollView.as_view(),
        name="course-enroll",
    ),
    path(
        "workspaces/<slug:slug>/enrollments/me/",
        StudentEnrollmentMeView.as_view(),
        name="student-enrollments-me",
    ),
]
