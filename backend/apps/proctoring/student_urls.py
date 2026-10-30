from django.urls import path

from .student_views import BrowserEventView, FrameUploadView

urlpatterns = []
urlpatterns += [
    path(
        "workspaces/<slug:slug>/attempts/<int:attempt_id>/proctoring/frame/",
        FrameUploadView.as_view(),
        name="proctoring-frame-upload",
    ),
    path(
        "workspaces/<slug:slug>/attempts/<int:attempt_id>/proctoring/events/",
        BrowserEventView.as_view(),
        name="proctoring-browser-event",
    ),
]
