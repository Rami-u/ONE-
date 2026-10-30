"""Serve the built React SPA from Django in production.

When the FRONTEND_DIST environment variable points at the frontend build
output (e.g. ../frontend/dist), Django becomes a single-origin deployment:
the API, the platform admin, and the SPA are all served from one domain (and
the workspace subdomains of it), so session cookies keep working without any
CORS configuration and no extra static-file process is needed.

Motivation for the details:
- The exact low-order exception of the SPA routing: any GET whose target is
  not an API/admin/static/media path and not a real file in the dist tree is
  answered with index.html so the client-side router can handle it.
- Hashed asset filenames (assets/*) are immutable and get one-year caching;
  index.html is always revalidated so a new deploy is picked up immediately.
- Paths are resolved and required to stay inside the dist tree, so the
  catch-all can never be used to read files elsewhere on the server.

Local development keeps FRONTEND_DIST unset: the Vite dev server stays the
way to run the frontend and Django 404s for non-API paths as before.
"""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseNotAllowed


def resolve_dist() -> tuple[Path, Path]:
    """Return (dist_root, index.html path) or 404 with a clear reason."""
    configured = getattr(settings, "FRONTEND_DIST", None)
    if configured is None:
        raise Http404("Frontend serving is not configured (FRONTEND_DIST is unset).")
    root = Path(configured).resolve()
    index = root / "index.html"
    if not index.is_file():
        raise Http404("Frontend build output not found (no index.html in FRONTEND_DIST).")
    return root, index


def spa_view(request, path=""):
    """Serve one file of the built SPA, falling back to index.html."""
    if request.method not in {"GET", "HEAD"}:
        return HttpResponseNotAllowed(["GET", "HEAD"])

    root, index = resolve_dist()

    file_to_serve: Path | None = None
    if path:
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            file_to_serve = candidate

    if file_to_serve is not None and path.startswith("assets/"):
        # Vite emits content-hashed filenames under assets/, safe to cache.
        return FileResponse(
            file_to_serve.open("rb"),
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    return FileResponse(index.open("rb"), headers={"Cache-Control": "no-cache"})
