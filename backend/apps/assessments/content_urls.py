from django.urls import path

from .content_views import TopicDetailView, TopicListCreateView

urlpatterns = [
    path("workspaces/<slug:slug>/topics/", TopicListCreateView.as_view(), name="topic-list-create"),
    path("workspaces/<slug:slug>/topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
]