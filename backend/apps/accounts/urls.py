from django.urls import path

from .student_views import (
    StudentCSRFCookieView,
    StudentLoginView,
    StudentLogoutView,
    StudentMeView,
    StudentPasswordResetConfirmView,
    StudentPasswordResetView,
    StudentRegisterView,
)
from .views import (
    AdminTeacherDetailView,
    AdminTeacherListCreateView,
    AdminTeacherResendInviteView,
    AdminWorkspaceActivateView,
    AdminWorkspaceDetailView,
    AdminWorkspaceListView,
    AdminWorkspaceSuspendView,
    StaffLoginView,
    StaffPasswordResetView,
    StaffSetPasswordView,
)

urlpatterns = [
    path("workspaces/<slug:slug>/auth/csrf/", StudentCSRFCookieView.as_view(), name="student-csrf"),
    path("workspaces/<slug:slug>/auth/register/", StudentRegisterView.as_view(), name="student-register"),
    path("workspaces/<slug:slug>/auth/login/", StudentLoginView.as_view(), name="student-login"),
    path("workspaces/<slug:slug>/auth/logout/", StudentLogoutView.as_view(), name="student-logout"),
    path("workspaces/<slug:slug>/auth/me/", StudentMeView.as_view(), name="student-me"),
    path("workspaces/<slug:slug>/auth/password-reset/", StudentPasswordResetView.as_view(), name="student-password-reset"),
    path("workspaces/<slug:slug>/auth/password-reset/confirm/", StudentPasswordResetConfirmView.as_view(), name="student-password-reset-confirm"),
    path("admin/teachers/", AdminTeacherListCreateView.as_view(), name="admin-teachers"),
    path("admin/teachers/<int:pk>/", AdminTeacherDetailView.as_view(), name="admin-teacher-detail"),
    path("admin/teachers/<int:pk>/resend-invite/", AdminTeacherResendInviteView.as_view(), name="admin-teacher-resend-invite"),
    path("admin/workspaces/", AdminWorkspaceListView.as_view(), name="admin-workspaces"),
    path("admin/workspaces/<int:pk>/", AdminWorkspaceDetailView.as_view(), name="admin-workspace-detail"),
    path("admin/workspaces/<int:pk>/suspend/", AdminWorkspaceSuspendView.as_view(), name="admin-workspace-suspend"),
    path("admin/workspaces/<int:pk>/activate/", AdminWorkspaceActivateView.as_view(), name="admin-workspace-activate"),
    path("workspaces/<slug:slug>/staff/auth/login/", StaffLoginView.as_view(), name="staff-login"),
    path("workspaces/<slug:slug>/staff/auth/set-password/", StaffSetPasswordView.as_view(), name="staff-set-password"),
    path("workspaces/<slug:slug>/staff/auth/password-reset/", StaffPasswordResetView.as_view(), name="staff-password-reset"),
]
