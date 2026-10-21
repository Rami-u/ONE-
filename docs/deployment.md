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

`backend/requirements.txt` has no WSGI server or static-file package; deployment needs `collectstatic` and a web server for `/static/`.

Map `/media/` to `backend/public_media` in the production web server.
