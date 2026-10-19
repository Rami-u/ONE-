from functools import wraps

from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def api_docs_when_enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.ENABLE_API_DOCS:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped

urlpatterns = [path(settings.DJANGO_ADMIN_PATH, admin.site.urls)]
urlpatterns += [
    path(
        "api/schema/",
        api_docs_when_enabled(SpectacularAPIView.as_view()),
        name="schema",
    ),
    path(
        "api/docs/",
        api_docs_when_enabled(SpectacularSwaggerView.as_view(url_name="schema")),
        name="swagger-ui",
    ),
]
