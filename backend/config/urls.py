from functools import wraps
from re import escape

from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from django.conf.urls.static import static
from django.views.static import serve as static_serve

from config.spa import spa_view
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def api_docs_when_enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.ENABLE_API_DOCS:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped

urlpatterns = [path(settings.DJANGO_ADMIN_PATH, admin.site.urls)]
urlpatterns += [path("api/v1/", include("apps.accounts.urls"))]
urlpatterns += [path("api/v1/", include("apps.public.urls"))]
urlpatterns += [path("api/v1/", include("apps.courses.urls"))]
urlpatterns += [path("api/v1/", include("apps.enrollments.urls"))]
urlpatterns += [path("api/v1/", include("apps.payments.urls"))]
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

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.BASE_DIR / "public_media",
    )

if settings.FRONTEND_DIST:
    # Single-origin deployment: Django also serves the SPA (below) plus
    # /media/ (public workspace logos) and /static/ (collected admin files).
    # The SPA catch-all must stay last so the API, schema/docs, and admin
    # URLs keep resolving first.
    reserved = sorted(
        escape(part)
        for part in {"api", "static", "media", settings.DJANGO_ADMIN_PATH.strip("/")}
    )
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            static_serve,
            {"document_root": settings.BASE_DIR / "public_media"},
        ),
        re_path(
            r"^static/(?P<path>.*)$",
            static_serve,
            {"document_root": settings.STATIC_ROOT},
        ),
        re_path(
            r"^(?!(?:%s)(?:$|/))(?P<path>.*)$" % "|".join(reserved),
            spa_view,
            name="spa",
        ),
    ]
