# Production Deployment Checklist

This file is read only when preparing a deployment and is not needed for normal stages.

Set these in the server's `backend/.env`; never copy `.env.example` as-is. Variable names come from `backend/.env.example`.

| Variable | Dev example | Production |
|---|---|---|
| `DJANGO_SECRET_KEY` | `replace-with-a-long-random-secret` | Generate a new long random secret. |
| `DJANGO_DEBUG` | `True` | `False` |
| `DJANGO_ENABLE_API_DOCS` | `True` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | `.<domain>,<domain>`; the leading dot covers every teacher sub-domain. |
| `CSRF_TRUSTED_ORIGINS` | `https://*.edunova.com` | `https://*.<domain>` |
| `PLATFORM_BASE_DOMAIN`, `PLATFORM_URL_SCHEME` | `edunova.com`, `https` | Your real domain, `https`. |
| `DJANGO_SESSION_COOKIE_SECURE` | `False` for local HTTP | `True` |
| `DJANGO_ADMIN_PATH` | `platform-admin/` | Use a non-guessable path. |
| `DRF_NUM_PROXIES` | `0` | Set to `1` only when exactly one trusted proxy is in front of Django. |
| `EMAIL_BACKEND` | `.env.example` explicitly sets the console backend | Switch to `django.core.mail.backends.smtp.EmailBackend` or delete the line to use the non-debug SMTP default. Configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Local PostgreSQL values | Set real database connection details and credentials. |

Never set `SESSION_COOKIE_DOMAIN` (AGENTS.md section 7).

Not configurable from `.env` yet: run `DJANGO_DEBUG=False ... python manage.py check --deploy` with a production-like environment. It currently warns that `SECURE_SSL_REDIRECT` is not enabled, `SECURE_HSTS_SECONDS` is unset, and `CSRF_COOKIE_SECURE` is not enabled; record these as pre-deployment TODOs.

Shared cache for throttling (pre-deployment TODO): the default cache is per process, so throttle limits multiply by the number of workers. The recommended fix is Django `DatabaseCache` with `python manage.py createcachetable`; Redis is an alternative and needs approval to add a dependency. A reverse-proxy limit on login routes complements DRF throttling but does not replace it; `DRF_NUM_PROXIES` must also be correct. See README's “Production: shared cache for throttling” subsection.

`backend/requirements.txt` has no WSGI server; running Django in production needs an application server such as `waitress` or `gunicorn` (a package addition that needs team approval).

## Serving the React frontend (single origin)

The React app in `frontend/` is the same product on the main domain and every teacher sub-domain. The simplest production shape is **one origin**: Django serves the built SPA itself, so the API, session cookies, admin, and UI all live on one domain and no CORS configuration is needed anywhere.

Setup on the server:

1. On the build machine, produce the frontend bundle with the real domain baked in:

   ```
   cd frontend
   VITE_PLATFORM_BASE_DOMAIN=<your-domain> npm run build
   ```

   `VITE_PLATFORM_BASE_DOMAIN` is read at build time and compiled into the JS, so it must be the production domain (`edunova.com`), not `localhost`. The output lands in `frontend/dist/`.

2. Point Django at it in `backend/.env`:

   ```
   FRONTEND_DIST=frontend/dist
   ```

3. Run `python manage.py collectstatic` so the Django admin assets exist in `backend/staticfiles/`.

With `FRONTEND_DIST` set, `backend/config/urls.py` (see `backend/config/spa.py`) serves:

| Path | Source | Caching |
|---|---|---|
| `/api/v1/…`, `/api/schema/`, `/api/docs/`, admin path | Django apps (unchanged) | — |
| `/static/…` | `backend/staticfiles` (admin assets) | by Django `static` serve |
| `/media/…` | `backend/public_media` (workspace logos) | by Django `static` serve |
| `assets/…` files in the bundle, e.g. `/assets/index-*.js` | `frontend/dist` hashed bundle files | 1 year, immutable |
| everything else (GET) | `frontend/dist/index.html` — the client router picks the screen | no-cache |

Non-GET requests to unknown paths answer `405`, unknown `/api/…` still answers `404`, and dist paths are checked to stay inside the dist tree, so the catch-all cannot read anything outside it.

DNS: point `<domain>` and the wildcard `*.<domain>` A records at the server; TLS must cover the wildcard too. Workspace links that emails generate come from `PLATFORM_BASE_DOMAIN`.

This serving mode is deliberately dependency-free (no white-noise/nginx requirement). For high-traffic deployments, offload `/assets/`, `/static/`, and `/media/` to a reverse proxy or CDN in front of Django using the same path table above; Django then keeps serving the API and `index.html`.

Alternative shape: host the SPA separately (e.g. static hosting with sub-domain routing) and reverse-proxy `/api/v1` to Django; keep `CSRF_TRUSTED_ORIGINS`, `DJANGO_ALLOWED_HOSTS`, and `PLATFORM_BASE_DOMAIN` aligned so cookies remain first-party. All shapes above rely on the SPA being reached through the workspace sub-domains, because the slug is read from `window.location.hostname`.
