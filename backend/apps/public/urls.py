from django.urls import path

from .views import (
    PublicTeacherDirectoryView,
    PublicTeacherProfileView,
    WorkspaceBrandingView,
    WorkspacePublicProfileView,
    WorkspaceSettingsView,
)


urlpatterns = [
    path("public/teachers/", PublicTeacherDirectoryView.as_view(), name="public-teachers"),
    path(
        "public/teachers/<slug:slug>/",
        PublicTeacherProfileView.as_view(),
        name="public-teacher-profile",
    ),
    path("workspaces/<slug:slug>/", WorkspaceSettingsView.as_view(), name="workspace-settings"),
    path(
        "workspaces/<slug:slug>/branding/",
        WorkspaceBrandingView.as_view(),
        name="workspace-branding",
    ),
    path(
        "workspaces/<slug:slug>/public-profile/",
        WorkspacePublicProfileView.as_view(),
        name="workspace-public-profile",
    ),
]
